"""WS 事件分发：假人过滤 → 游戏内指令回调 → 订阅过滤 → 推送群聊。"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, List

from gsuid_core.bot import Bot
from gsuid_core.gss import gss
from gsuid_core.logger import logger
from gsuid_core.models import Event, Message
from gsuid_core.segment import MessageSegment

from ...mcqq_config import mcqq_config
from ...mcqq_database import MCQQBind, MCQQServer
from ...utils.helpers.prefix_rules import (
    has_rules,
    is_blacklisted,
    is_fake_player,
    match_and_trim_prefix,
)
from ...utils.utils.cicode import parse_cicode
from .formatters import format_event_message

IngameHandler = Callable[[str, str, str], Awaitable[bool]]
_ingame_handlers: List[IngameHandler] = []


def register_ingame_handler(fn: IngameHandler) -> None:
    if fn not in _ingame_handlers:
        _ingame_handlers.append(fn)


async def try_ingame_command(
    server_name: str, player_name: str, raw: str
) -> bool:
    for fn in _ingame_handlers:
        if await fn(server_name, player_name, raw):
            return True
    return False


async def ws_event_handler(server_name: str, raw_message: str) -> None:
    try:
        data: dict[str, Any] = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.info(f"[MCQueQiao] [{server_name}] 收到非 JSON 消息: {raw_message}")
        return

    post_type = data.get("post_type", "")
    if post_type == "response":
        logger.debug(
            f"[MCQueQiao] [{server_name}] 收到API响应: "
            f"api={data.get('api')}, "
            f"status={data.get('status')}, "
            f"echo={data.get('echo')}"
        )
        return

    player = data.get("player", {})
    player_name = (
        player.get("nickname", "") if isinstance(player, dict) else ""
    )
    if not player_name:
        player_name = str(data.get("player_name", data.get("nickname", "")))

    if player_name:
        fake_filter = mcqq_config.get_config("fake_player_filter").data
        if is_fake_player(str(player_name), fake_filter):
            logger.debug(f"[MC·转发过滤] '{player_name}' 位于假人列表中，跳过推送")
            return

    sub_type = str(data.get("sub_type", ""))

    if sub_type == "player_chat":
        raw_chat = str(data.get("message", ""))
        if player_name and raw_chat:
            if await try_ingame_command(server_name, str(player_name), raw_chat):
                logger.info(
                    f"[MC·游戏内指令] [{server_name}] 玩家 '{player_name}' "
                    f"执行了指令 '{raw_chat}'"
                )
                return

    if sub_type == "player_command":
        raw_cmd = str(data.get("command", data.get("message", "")))
        if player_name and raw_cmd:
            if await try_ingame_command(server_name, str(player_name), raw_cmd):
                logger.info(
                    f"[MC·游戏内指令] [{server_name}] 玩家 '{player_name}' "
                    f"执行了指令 '{raw_cmd}'"
                )
                return

    display_name = None
    server = await MCQQServer.get_by_name(server_name)
    if server is not None:
        display_name = server.display_name or server.server_name

    show_server_name: bool = mcqq_config.get_config("show_server_name").data
    text = format_event_message(data, sub_type, show_server_name, display_name)
    if text is None:
        logger.debug(
            f"[MCQueQiao] [{server_name}] 未处理的事件: "
            f"sub_type={sub_type}, "
            f"event={data.get('event_name')}"
        )
        return

    if sub_type == "player_chat":
        whitelist = mcqq_config.get_config("mc_to_qq_whitelist").data
        blacklist = mcqq_config.get_config("mc_to_qq_blacklist").data
        raw_message_text = str(data.get("message", ""))

        if has_rules(whitelist):
            matched, _ = match_and_trim_prefix(raw_message_text, whitelist)
            if not matched:
                logger.debug(
                    f"[MC·转发过滤] '{raw_message_text}' 未在白名单内，跳过推送"
                )
                return
        elif is_blacklisted(raw_message_text, blacklist):
            logger.debug(f"[MC·转发过滤] '{raw_message_text}' 触发黑名单，跳过推送")
            return

    await push_to_qq_group(server_name, text)


async def push_to_qq_group(server_name: str, text: str) -> None:
    binds = await MCQQBind.get_by_server_name(server_name)
    if not binds:
        logger.warning(f"[MC·消息转发] '{server_name}' 未绑定群聊，消息推送失败")
        return

    if not gss.active_bot:
        logger.warning("[MC·消息转发] 无连接中 Bot，消息推送失败")
        return

    for bind in binds:
        await _send_to_bind(bind, text)


async def _send_to_bind(bind: MCQQBind, text: str) -> None:
    ev = Event(
        bot_id=bind.bot_id,
        user_id="0",
        bot_self_id=bind.bot_self_id,
        user_type=bind.user_type or "group",  # type: ignore
        group_id=bind.group_id,
        msg_id=bind.msg_id or "",
    )

    if not bind.ws_bot_id or bind.ws_bot_id not in gss.active_bot:
        logger.error(
            f"[MCQueQiao] 机器人 {bind.ws_bot_id} 不存在，"
            f"无法发送消息到群 {bind.group_id}"
        )
        return

    BOT = gss.active_bot[bind.ws_bot_id]
    bot = Bot(BOT, ev)

    clean_text, image_urls = parse_cicode(text)
    segments: list[Message] = []
    if clean_text.strip():
        segments.append(MessageSegment.text(clean_text))
    for url in image_urls:
        segments.append(MessageSegment.image(url))
    if not segments:
        segments.append(MessageSegment.text(text))

    try:
        await bot.send(segments)
        logger.info(
            f"[MCQueQiao] [{bind.server_name}] 已推送消息到群 "
            f"{bind.group_id}: {text}"
        )
    except Exception as e:
        logger.error(
            f"[MCQueQiao] [{bind.server_name}] 推送消息到群 "
            f"{bind.group_id} 失败: {e}"
        )
