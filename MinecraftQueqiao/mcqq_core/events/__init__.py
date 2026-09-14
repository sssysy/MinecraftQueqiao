from .dispatch import (
    register_ingame_handler,
    try_ingame_command,
    ws_event_handler,
)
from .formatters import format_event_message

__all__ = [
    "ws_event_handler",
    "handle_ws_message",
    "register_ingame_handler",
    "try_ingame_command",
    "format_event_message",
]


async def handle_ws_message(server_name: str, raw_message: str) -> None:
    await ws_event_handler(server_name, raw_message)
