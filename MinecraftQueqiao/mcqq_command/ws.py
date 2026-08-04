from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQServer
from ..mcqq_main import ws_event_handler
from ..mcqq_ws import ws_manager

sv_mcqq_refresh = SV("鹊桥ws相关指令")


@sv_mcqq_refresh.on_prefix("刷新ws连接")
async def refresh_ws_connections(bot: Bot, ev: Event) -> None:
    logger.info(
        f"[MCQueQiao] 用户 {ev.user_id} 触发刷新 WS 连接列表"
    )

    # 停止所有现有连接
    await ws_manager.stop_all()

    # 读取全局配置
    reconnect_interval: int = mcqq_config.get_config(
        "reconnect_interval"
    ).data
    max_retries: int = mcqq_config.get_config(
        "max_reconnect_times"
    ).data

    # 从数据库重新加载启用的服务器
    servers = await MCQQServer.get_all_enabled()
    if not servers:
        logger.warning("[MCQueQiao] 没有启用的服务器配置，跳过连接")
        await bot.send("刷新完成，但当前没有启用的服务器配置")
        return

    logger.info(
        f"[MCQueQiao] 找到 {len(servers)} 个启用的服务器配置"
    )

    await ws_manager.start_all(
        servers=servers,
        reconnect_interval=reconnect_interval,
        max_retries=max_retries,
        message_handler=ws_event_handler,
    )

    await bot.send(
        f"WS 连接已刷新，已为 {len(servers)} 个服务器建立连接"
    )