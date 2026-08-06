from typing import Any

from gsuid_core.logger import logger
from gsuid_core.server import on_core_shutdown, on_core_start

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQServer
from ..mcqq_main import ws_event_handler
from ..mcqq_ws import ws_manager


async def handle_ws_message(server_name: str, raw_message: str) -> None:
    """处理从鹊桥 WebSocket 接收到的消息"""
    await ws_event_handler(server_name, raw_message)


@on_core_start
async def init_mcqq_connections() -> None:
    """初始化 ws 连接"""
    logger.info("[MCQueQiao] 开始初始化鹊桥 WebSocket 连接...")

    # 读取全局配置
    reconnect_interval: int = mcqq_config.get_config(
        "reconnect_interval"
    ).data
    max_retries: int = mcqq_config.get_config(
        "max_reconnect_times"
    ).data

    # 从数据库加载启用的服务器
    servers = await MCQQServer.get_all_enabled()
    if not servers:
        logger.warning("[MCQueQiao] 没有启用的服务器配置，跳过连接")
        return

    logger.info(
        f"[MCQueQiao] 找到 {len(servers)} 个启用的服务器配置"
    )

    # 统计双模式分布
    client_count = sum(1 for s in servers if s.ws_mode != "server")
    server_count = sum(1 for s in servers if s.ws_mode == "server")
    logger.info(
        f"[MCQueQiao] 模式分布: 正向 {client_count} 个, "
        f"反向 {server_count} 个"
    )

    await ws_manager.start_all(
        servers=servers,
        reconnect_interval=reconnect_interval,
        max_retries=max_retries,
        message_handler=handle_ws_message,
    )


@on_core_shutdown
async def shutdown_mcqq_connections() -> None:
    """停止 ws 连接。"""
    logger.info("[MCQueQiao] 正在关闭所有 WebSocket 连接...")
    await ws_manager.stop_all()


async def send_broadcast(
    server_name: str,
    text: str | list[dict[str, Any]],
    echo: str = "",
) -> bool:
    """向指定服务器发送广播消息"""
    client = ws_manager.get_client(server_name)
    if client is None:
        logger.error(
            f"[MCQueQiao] 未找到服务器 '{server_name}' 的连接"
        )
        return False

    if client.queqiao_version == "v1":
        # v1
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text)
        message: dict[str, Any] = {
            "api": "send_msg",
            "data": {"message": text},
            "echo": echo,
        }
    else:
        # v2
        components = text if isinstance(text, list) else [{"text": text}]
        message = {
            "api": "broadcast",
            "data": {"message": components},
            "echo": echo,
        }

    logger.info(
        f"[MCQueQiao] [{server_name}] 正在发送广播消息: {text}"
    )
    return await ws_manager.send_to_server(server_name, message)
