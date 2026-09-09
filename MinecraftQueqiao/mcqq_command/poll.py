from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_poll import refresh_poll_jobs

sv_mcqq_poll = SV("鹊桥定时公告指令", pm=3)


@sv_mcqq_poll.on_fullmatch("刷新定时公告")
async def refresh_poll_command(bot: Bot, ev: Event) -> None:
    """mc刷新定时公告: 重新读取数据库并注册定时公告任务"""
    try:
        total_enabled, registered_count, details = await refresh_poll_jobs()
    except Exception as e:
        logger.error(f"[MC·定时公告] 刷新定时公告失败: {e}")
        await bot.send(f"刷新定时公告失败: {e}")
        return

    failed_items = [item for item in details if item.get("status") != "registered"]
    if not failed_items:
        lines = [
            "定时公告刷新",
            f" - 启用任务：{total_enabled} 个",
            f"注册成功：{registered_count} 个",
        ]
    else:
        failed_count = len(failed_items)
        lines = [
            "定时公告刷新",
            f" - 启用任务：{total_enabled} 个",
            f" - 注册成功：{registered_count} 个",
            f"注册失败：{failed_count} 个",
            " - 失败列表：",
        ]
        for idx, item in enumerate(failed_items, 1):
            reason = item.get("desc", "未知原因")
            lines.append(f"  - {idx} | {reason}")

    await bot.send("\n".join(lines))

