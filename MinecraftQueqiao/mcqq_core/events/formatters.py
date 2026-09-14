"""鹊桥 V2 事件文本格式化。只认 V2 sub_type，无旧别名。"""

from __future__ import annotations

from typing import Any, Callable, Optional

from gsuid_core.logger import logger

from ...mcqq_config import mcqq_config
from ...utils.helpers.prefix_rules import match_and_trim_prefix

# 订阅配置里的中文标签
EVENT_LABEL = {
    "player_chat": "玩家聊天",
    "player_join": "玩家加入",
    "player_quit": "玩家退出",
    "player_death": "玩家死亡",
    "player_command": "玩家命令",
    "player_achievement": "玩家成就",
}


def _player_name(data: dict[str, Any]) -> str:
    player = data.get("player", {})
    if isinstance(player, dict):
        return str(player.get("nickname") or "Unknown")
    return str(data.get("player_name") or "Unknown")


def _display_server(data: dict[str, Any], display_name: Optional[str]) -> str:
    return display_name or str(data.get("server_name") or "Unknown")


def _fmt_chat(
    data: dict[str, Any], show_server_name: bool, display_name: Optional[str]
) -> str:
    player_name = _player_name(data)
    message = str(data.get("message", ""))
    chat_whitelist = mcqq_config.get_config("mc_to_qq_whitelist").data
    if chat_whitelist:
        matched, new_message = match_and_trim_prefix(message, chat_whitelist)
        if matched:
            message = new_message
    server = _display_server(data, display_name)
    if show_server_name:
        return f"<{player_name} ({server})> {message}"
    return f"<{player_name}> {message}"


def _fmt_death(
    data: dict[str, Any], show_server_name: bool, display_name: Optional[str]
) -> str:
    player_name = _player_name(data)
    death = data.get("death", {})
    death_text = ""
    if isinstance(death, dict):
        death_text = death.get("text", "") or ""
    if not death_text:
        death_text = str(data.get("message") or f"{player_name} 死亡了")
    prefix = f"[{_display_server(data, display_name)}] " if show_server_name else ""
    return f"{prefix}{death_text}"


def _fmt_join(
    data: dict[str, Any], show_server_name: bool, display_name: Optional[str]
) -> str:
    player_name = _player_name(data)
    prefix = f"[{_display_server(data, display_name)}] " if show_server_name else ""
    return f"{prefix}{player_name} 加入了游戏"


def _fmt_quit(
    data: dict[str, Any], show_server_name: bool, display_name: Optional[str]
) -> str:
    player_name = _player_name(data)
    prefix = f"[{_display_server(data, display_name)}] " if show_server_name else ""
    return f"{prefix}{player_name} 离开了游戏"


def _fmt_achievement(
    data: dict[str, Any], show_server_name: bool, display_name: Optional[str]
) -> str:
    player_name = _player_name(data)
    achievement = data.get("achievement", {})
    achievement_text = ""
    if isinstance(achievement, dict):
        translate = achievement.get("translate")
        if isinstance(translate, dict):
            achievement_text = translate.get("text", "") or ""
    if achievement_text:
        if not achievement_text.startswith("["):
            achievement_text = f"[{achievement_text}]"
    else:
        achievement_text = "[成就]"
    prefix = f"[{_display_server(data, display_name)}] " if show_server_name else ""
    return f"{prefix}{player_name} 获得成就 {achievement_text}"


def _fmt_command(
    data: dict[str, Any], show_server_name: bool, display_name: Optional[str]
) -> str:
    player_name = _player_name(data)
    command = data.get("command", data.get("message", ""))
    prefix = f"[{_display_server(data, display_name)}] " if show_server_name else ""
    return f"{prefix}{player_name} 执行: {command}"


_FORMATTERS: dict[
    str, Callable[[dict[str, Any], bool, Optional[str]], str]
] = {
    "player_chat": _fmt_chat,
    "player_death": _fmt_death,
    "player_join": _fmt_join,
    "player_quit": _fmt_quit,
    "player_achievement": _fmt_achievement,
    "player_command": _fmt_command,
}


def format_event_message(
    data: dict[str, Any],
    sub_type: str,
    show_server_name: bool = True,
    display_name: str | None = None,
) -> str | None:
    formatter = _FORMATTERS.get(sub_type)
    if formatter is None:
        return None

    subscribed = mcqq_config.get_config("subscribe_events").data
    label = EVENT_LABEL.get(sub_type)
    if label is None or label not in subscribed:
        logger.debug(f"[MCQueQiao] 事件 {sub_type} 未在订阅列表中，跳过")
        return None

    return formatter(data, show_server_name, display_name)
