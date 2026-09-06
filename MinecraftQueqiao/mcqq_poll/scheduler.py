import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from gsuid_core.aps import scheduler
from gsuid_core.logger import logger

from ..mcqq_core import send_broadcast
from ..mcqq_database import MCQQPoll, MCQQServer
from ..mcqq_ws import ws_manager
from ..utils.helpers.component import parse_text_or_json_component

TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


def parse_schedule_rule(rule_str: str) -> Tuple[str, Optional[Any], str]:
    """智能解析推送时间/间隔规则

    支持格式：
    1. 留空 / 0 / none -> 不推送 ("none", None, "未配置/不推送")
    2. Unix 时间戳 (秒级如 1756555200 或毫秒级如 1756555200000) / ISO 日期字符串 -> 一次性推送 ("timestamp", DateTrigger, "一次性推送: YYYY-mm-dd HH:MM:SS") 或 ("expired", dt, "已过期: ...")
    3. Cron 表达式 (标准 5 段如 "0 8 * * *" 或 "*/30 * * * *") -> 循环推送 ("cron", CronTrigger, "Cron循环: ...")

    Returns:
        (rule_type: str, trigger_or_dt: Optional[Any], description: str)
    """
    rule = rule_str.strip()
    if not rule or rule.lower() in ("0", "none", "null", "false"):
        return ("none", None, "未配置推送规则")

    # 1. 尝试判定是否为纯数字时间戳
    if rule.isdigit():
        ts = int(rule)
        if ts > 10**11:
            ts = ts / 1000.0
        dt = datetime.fromtimestamp(ts, tz=TZ_SHANGHAI)
        now = datetime.now(tz=TZ_SHANGHAI)
        if dt <= now:
            return ("expired", dt, f"已过期 ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
        trigger = DateTrigger(run_date=dt, timezone=TZ_SHANGHAI)
        return ("timestamp", trigger, f"一次性推送 ({dt.strftime('%Y-%m-%d %H:%M:%S')})")

    # 2. 尝试判定是否为 ISO / 常见格式日期字符串
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            dt_naive = datetime.strptime(rule, fmt)
            dt = dt_naive.replace(tzinfo=TZ_SHANGHAI)
            now = datetime.now(tz=TZ_SHANGHAI)
            if dt <= now:
                return ("expired", dt, f"已过期 ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
            trigger = DateTrigger(run_date=dt, timezone=TZ_SHANGHAI)
            return ("timestamp", trigger, f"一次性推送 ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
        except ValueError:
            pass

    # 3. 尝试判定是否为 Cron 表达式 (标准 5 段 crontab)
    try:
        trigger = CronTrigger.from_crontab(rule, timezone=TZ_SHANGHAI)
        return ("cron", trigger, f"Cron循环 ({rule})")
    except Exception:
        pass

    return ("invalid", None, f"格式无效或无法识别: {rule}")


async def send_poll_message(poll_id: int, server_name: str, content: str) -> bool:
    """向指定服务器（或全部服务器）发送定时公告消息，支持富文本 JSON 格式"""
    formatted_msg = parse_text_or_json_component(
        content, default_color="white", default_prefix="[定时公告] "
    )

    # 确定目标服务器列表（留空或 all 则发送给全部已启用/已连接服务器）
    target_servers: List[str] = []
    if not server_name or server_name in ("all", "全部"):
        servers = await MCQQServer.get_all_enabled()
        if servers:
            target_servers = [s.server_name for s in servers]
        else:
            target_servers = ws_manager.get_connected_servers()
    else:
        target_servers = [server_name]

    if not target_servers:
        logger.warning(f"[MCQueQiao] 定时公告 [ID:{poll_id}] 未找到可推送的目标服务器")
        return False

    success = True
    for s_name in target_servers:
        try:
            ok = await send_broadcast(s_name, formatted_msg)
            if ok:
                logger.info(
                    f"[MCQueQiao] 定时公告 [ID:{poll_id}] 成功推送至服务器 [{s_name}]"
                )
            else:
                logger.warning(
                    f"[MCQueQiao] 定时公告 [ID:{poll_id}] 推送至服务器 [{s_name}] 失败（服务器未连接或离线）"
                )
                success = False
        except Exception as e:
            logger.error(
                f"[MCQueQiao] 定时公告 [ID:{poll_id}] 推送至 [{s_name}] 异常: {e}"
            )
            success = False

    return success


async def refresh_poll_jobs() -> Tuple[int, int, List[Dict[str, Any]]]:
    """重新从数据库加载并注册所有定时公告任务

    Returns:
        (total_enabled: int, registered_count: int, details: List[dict])
    """
    # 1. 清理已有属于 mcqq_poll 的任务
    existing_jobs = scheduler.get_jobs()
    removed_count = 0
    for job in existing_jobs:
        if job.id.startswith("mcqq_poll_"):
            try:
                scheduler.remove_job(job.id)
                removed_count += 1
            except Exception as e:
                logger.error(f"[MCQueQiao] 移除旧定时任务 {job.id} 失败: {e}")

    logger.debug(f"[MCQueQiao] 已清理 {removed_count} 个旧定时公告任务")

    # 2. 从数据库读取所有已启用的公告
    polls = await MCQQPoll.get_all_enabled()
    registered_count = 0
    details: List[Dict[str, Any]] = []

    for poll in polls:
        rule_type, trigger, desc = parse_schedule_rule(poll.schedule_rule)
        job_id = f"mcqq_poll_{poll.id}"
        detail_item: Dict[str, Any] = {
            "id": poll.id,
            "server_name": poll.server_name,
            "content": poll.content,
            "schedule_rule": poll.schedule_rule,
            "rule_type": rule_type,
            "desc": desc,
            "status": "skipped",
            "next_run_time": None,
            "remark": poll.remark,
        }

        if rule_type in ("timestamp", "cron") and trigger is not None:
            try:
                job = scheduler.add_job(
                    func=send_poll_message,
                    trigger=trigger,
                    id=job_id,
                    name=f"MCQQ定时公告_{poll.id}",
                    args=[poll.id, poll.server_name, poll.content],
                    replace_existing=True,
                )
                registered_count += 1
                detail_item["status"] = "registered"
                if job.next_run_time:
                    detail_item["next_run_time"] = job.next_run_time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                logger.info(
                    f"[MCQueQiao] 成功注册定时公告 [ID:{poll.id}] ({poll.server_name}) - {desc} - 下次运行: {detail_item['next_run_time']}"
                )
            except Exception as e:
                detail_item["status"] = f"error: {e}"
                detail_item["desc"] = f"注册失败: {e}"
                logger.error(f"[MCQueQiao] 注册定时公告 [ID:{poll.id}] 失败: {e}")
        else:
            logger.info(
                f"[MCQueQiao] 定时公告 [ID:{poll.id}] 未注册: {desc}"
            )

        details.append(detail_item)

    return len(polls), registered_count, details

