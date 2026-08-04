from typing import Any

from gsuid_core.logger import logger
from gsuid_core.server import on_core_shutdown, on_core_start

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQServer
from ..mcqq_main import ws_event_handler
from ..mcqq_ws import ws_manager


async def handle_ws_message(server_name: str, raw_message: str) -> None:
    """处理从鹊桥 WebSocket 接收到的消息。

    委托给 mcqq_main.ws_event_handler 进行事件分发。
    """
    await ws_event_handler(server_name, raw_message)


@on_core_start
async def init_mcqq_connections() -> None:
    """Core 启动时初始化所有鹊桥 WebSocket 连接。"""
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

    await ws_manager.start_all(
        servers=servers,
        reconnect_interval=reconnect_interval,
        max_retries=max_retries,
        message_handler=handle_ws_message,
    )


@on_core_shutdown
async def shutdown_mcqq_connections() -> None:
    """Core 关闭时停止所有鹊桥 WebSocket 连接。"""
    logger.info("[MCQueQiao] 正在关闭所有 WebSocket 连接...")
    await ws_manager.stop_all()


async def send_broadcast(
    server_name: str,
    text: str | list[dict[str, Any]],
    echo: str = "",
) -> bool:
    """向指定服务器发送广播消息。

    根据服务器的鹊桥版本自动选择消息格式：
    - v2: 使用 broadcast API，消息为 Minecraft 文本组件格式
    - v1: 使用 send_msg API，消息为简单字符串

    Args:
        server_name: 目标服务器名称
        text: 要发送的文本内容。可以是纯字符串（v1），
            也可以是 Minecraft 文本组件列表（v2，用于着色）
        echo: 回声标识，用于匹配响应（可选）

    Returns:
        bool: 发送成功返回 True，失败返回 False
    """
    client = ws_manager.get_client(server_name)
    if client is None:
        logger.error(
            f"[MCQueQiao] 未找到服务器 '{server_name}' 的连接"
        )
        return False

    if client.queqiao_version == "v1":
        # v1: 使用 send_msg API，接受简单字符串
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text)
        message: dict[str, Any] = {
            "api": "send_msg",
            "data": {"message": text},
            "echo": echo,
        }
    else:
        # v2: 使用 broadcast API，消息为 Minecraft 文本组件
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
