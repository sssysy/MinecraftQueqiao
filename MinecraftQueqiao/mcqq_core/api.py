"""鹊桥 V2 WebSocket API 封装。"""

from __future__ import annotations

from typing import Any, List, Optional, Union

from gsuid_core.logger import logger
from gsuid_core.server import on_core_start

from ..mcqq_config import mcqq_config
from ..utils.helpers.component import parse_text_or_json_component
from ..utils.helpers.prefix_rules import is_command_blacklisted
from .events import handle_ws_message
from .ws import ws_manager

ComponentInput = Union[str, List[dict], dict]


@on_core_start
async def init_mcqq_connections() -> None:
    ws_manager.set_message_handler(handle_ws_message)
    logger.info(
        "[MC·Websocket] 鹊桥反向 WebSocket 服务端已就绪 "
        "(端点: /minecraft/ws/{server_name})"
    )


def _as_components(
    content: ComponentInput,
    *,
    default_color: str = "white",
    default_prefix: Optional[str] = None,
    bold: bool = False,
) -> List[dict]:
    if isinstance(content, str):
        parsed = parse_text_or_json_component(
            content, default_color=default_color, default_prefix=default_prefix, bold=bold
        )
        return parsed if isinstance(parsed, list) else [parsed]
    if isinstance(content, dict):
        return [content]
    return list(content)


def _rcon_timeout() -> float:
    try:
        return float(mcqq_config.get_config("rcon_timeout").data)
    except Exception:
        return 8.0


async def send_broadcast(
    server_name: str,
    text: ComponentInput,
    echo: str = "",
) -> bool:
    components = _as_components(text, default_color="white")
    message = {
        "api": "broadcast",
        "data": {"message": components},
        "echo": echo,
    }
    return await ws_manager.send_json(server_name, message)


async def send_title(
    server_name: str,
    title: ComponentInput,
    subtitle: Optional[ComponentInput] = None,
    fade_in: int = 20,
    stay: int = 70,
    fade_out: int = 20,
    echo: str = "",
) -> bool:
    title_obj = _as_components(title, default_color="yellow", bold=True)
    data: dict[str, Any] = {
        "title": title_obj,
        "fade_in": fade_in,
        "stay": stay,
        "fade_out": fade_out,
    }
    if subtitle is not None:
        data["subtitle"] = _as_components(subtitle, default_color="white")

    message = {
        "api": "send_title",
        "data": data,
        "echo": echo,
    }
    return await ws_manager.send_json(server_name, message)


async def send_action_bar(
    server_name: str,
    message: ComponentInput,
    echo: str = "",
) -> bool:
    components = _as_components(message, default_color="aqua")
    msg_payload = {
        "api": "send_actionbar",
        "data": {"message": components},
        "echo": echo,
    }
    return await ws_manager.send_json(server_name, msg_payload)


async def send_private_msg(
    server_name: str,
    player_name: str,
    message: ComponentInput,
    *,
    uuid: Optional[str] = None,
    echo: str = "",
) -> tuple[bool, Any]:
    """鹊桥 V2 send_private_msg：发给单个玩家。"""
    components = _as_components(message, default_color="white")
    data: dict[str, Any] = {"message": components}
    if uuid:
        data["uuid"] = uuid
    else:
        data["nickname"] = player_name
    return await ws_manager.request(
        server_name=server_name,
        api="send_private_msg",
        data=data,
        timeout=_rcon_timeout(),
    )


async def send_rcon_command(
    server_name: str,
    command: str,
    timeout: Optional[float] = None,
) -> tuple[bool, Any]:
    blacklist = mcqq_config.get_config("command_blacklist").data
    if is_command_blacklisted(command, blacklist):
        logger.warning(
            f"[MC·RCON] [{server_name}] 指令 '{command}' 命中黑名单，跳过传递"
        )
        return False, "黑名单指令！"

    if timeout is None:
        timeout = _rcon_timeout()

    return await ws_manager.request(
        server_name=server_name,
        api="send_rcon_command",
        data={"command": command},
        timeout=timeout,
    )
