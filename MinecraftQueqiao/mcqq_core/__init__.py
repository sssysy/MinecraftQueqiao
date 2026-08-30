from typing import Any, List, Optional, Tuple, Union

from gsuid_core.logger import logger
from gsuid_core.server import on_core_start

from ..mcqq_config import mcqq_config
from ..mcqq_main import ws_event_handler
from ..mcqq_ws import ws_manager


async def handle_ws_message(server_name: str, raw_message: str) -> None:
    """处理从鹊桥 WebSocket 接收到的消息"""
    await ws_event_handler(server_name, raw_message)


@on_core_start
async def init_mcqq_connections() -> None:
    """初始化鹊桥 WebSocket 事件分发器"""
    ws_manager.set_message_handler(handle_ws_message)
    logger.info(
        "[MCQueQiao] 鹊桥反向 WebSocket 服务端已就绪 "
        "(端点: /minecraft/ws/{server_name} 或 /minecraft/ws)"
    )


async def send_broadcast(
    server_name: str,
    text: Union[str, List[dict]],
    echo: str = "",
) -> bool:
    """向指定服务器发送聊天栏广播消息 (broadcast API)"""
    if isinstance(text, str):
        components = [{"text": text, "color": "white"}]
    else:
        components = text

    message = {
        "api": "broadcast",
        "data": {"message": components},
        "echo": echo,
    }
    return await ws_manager.send_json(server_name, message)


async def send_title(
    server_name: str,
    title: Union[str, dict],
    subtitle: Optional[Union[str, dict]] = None,
    fade_in: int = 20,
    stay: int = 70,
    fade_out: int = 20,
    echo: str = "",
) -> bool:
    """向指定服务器发送屏幕大标题消息 (send_title API)"""
    title_obj = (
        {"text": title, "color": "yellow", "bold": True}
        if isinstance(title, str)
        else title
    )
    data: dict[str, Any] = {
        "title": title_obj,
        "fade_in": fade_in,
        "stay": stay,
        "fade_out": fade_out,
    }
    if subtitle is not None:
        subtitle_obj = (
            {"text": subtitle, "color": "white"}
            if isinstance(subtitle, str)
            else subtitle
        )
        data["subtitle"] = subtitle_obj

    message = {
        "api": "send_title",
        "data": data,
        "echo": echo,
    }
    return await ws_manager.send_json(server_name, message)


async def send_rcon_command(
    server_name: str,
    command: str,
    timeout: Optional[float] = None,
) -> Tuple[bool, Any]:
    """通过 WebSocket 异步发送 RCON 命令并等待执行结果 (send_rcon_command API)

    Returns:
        (success: bool, result_text_or_error: str)
    """
    if timeout is None:
        try:
            timeout = float(mcqq_config.get_config("rcon_timeout").data)
        except Exception:
            timeout = 8.0

    return await ws_manager.request(
        server_name=server_name,
        api="send_rcon_command",
        data={"command": command},
        timeout=timeout,
    )


async def get_server_status_api(
    server_name: str,
    timeout: float = 4.0,
) -> Tuple[bool, Any]:
    """通过 WebSocket 异步调用鹊桥 get_status API 获取服务器原生状态数据

    Returns:
        (success: bool, data_or_error: Any)
    """
    return await ws_manager.request(
        server_name=server_name,
        api="get_status",
        data={},
        timeout=timeout,
    )

