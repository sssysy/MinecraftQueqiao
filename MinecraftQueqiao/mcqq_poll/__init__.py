from gsuid_core.logger import logger
from gsuid_core.server import on_core_start

from .scheduler import (
    get_poll_jobs_status,
    parse_schedule_rule,
    refresh_poll_jobs,
    send_poll_message,
)


@on_core_start
async def init_mcqq_poll_scheduler() -> None:
    """Bot 启动时自动初始化并加载定时公告任务"""
    logger.info("[MCQueQiao] 正在初始化定时公告任务调度...")
    try:
        total, registered, _ = await refresh_poll_jobs()
        logger.info(
            f"[MCQueQiao] 定时公告初始化完成: 共读取 {total} 条启用配置，成功注册 {registered} 个定时任务"
        )
    except Exception as e:
        logger.error(f"[MCQueQiao] 初始化定时公告任务失败: {e}")


__all__ = [
    "refresh_poll_jobs",
    "get_poll_jobs_status",
    "parse_schedule_rule",
    "send_poll_message",
]
