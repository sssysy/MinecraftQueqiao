from gsuid_core.logger import logger
from gsuid_core.server import on_core_start

from .scheduler import (
    parse_schedule_rule,
    refresh_poll_jobs,
    send_poll_message,
)


@on_core_start
async def init_mcqq_poll_scheduler() -> None:
    """Bot 启动时自动初始化并加载定时公告任务"""
    logger.info("[MC·定时公告] 初始化定时公告...")
    try:
        total, registered, _ = await refresh_poll_jobs()
        logger.info(
            f"[MC·定时公告] 定时公告初始化完毕，启用 {total} 个，注册成功 {registered} 个"
        )
    except Exception as e:
        logger.error(f"[MC·定时公告] 初始化定时公告任务失败: {e}")


__all__ = [
    "refresh_poll_jobs",
    "parse_schedule_rule",
    "send_poll_message",
]
