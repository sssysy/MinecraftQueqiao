"""QQ → MC 消息转发。"""

from __future__ import annotations

from typing import Any, Dict, List

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.component import clickable_text, chat_image_code
from ..utils.helpers.group_name import get_group_name
from ..utils.helpers.prefix_rules import (
    has_rules,
    is_blacklisted,
    match_and_trim_prefix,
)
from ..utils.helpers.user_name import resolve_user_name
from .api import send_broadcast

sv_mcqq_chat = SV("MC鹊桥聊天转发")


@sv_mcqq_chat.on_message()
async def qq_to_mc_forward(bot: Bot, ev: Event) -> None:
    if not mcqq_config.get_config("qq_to_mc_enabled").data:
        return
    if ev.user_type != "group" or not ev.group_id:
        return

    segments: List[Dict[str, Any]] = []
    has_at = False
    for seg in ev.content:
        mtype, data = seg.type, seg.data
        if mtype == "text" and data:
            segments.append({"kind": "text", "text": str(data)})
        elif mtype == "at" and data:
            has_at = True
            segments.append({"kind": "at", "uid": str(data)})
        elif mtype == "image" and data:
            segments.append({"kind": "image", "url": str(data)})
        elif mtype == "file" and data:
            name, _, file_url = str(data).partition("|")
            segments.append(
                {
                    "kind": "file",
                    "text": f"[文件 | {name.strip()}]",
                    "url": file_url.strip() if file_url else "",
                }
            )

    if not segments:
        return

    is_pure_at = has_at and all(s["kind"] == "at" for s in segments)

    whitelist = mcqq_config.get_config("qq_to_mc_whitelist").data
    blacklist = mcqq_config.get_config("qq_to_mc_blacklist").data

    if has_rules(whitelist) and not is_pure_at:
        new_segments: List[Dict[str, Any]] = []
        trimmed = False
        for s in segments:
            if s["kind"] == "text" and not trimmed:
                matched, new_text = match_and_trim_prefix(s["text"], whitelist)
                if not matched:
                    return
                trimmed = True
                if new_text:
                    new_segments.append({**s, "text": new_text})
                continue
            new_segments.append(s)
        if not trimmed and not is_pure_at:
            return
        segments = new_segments
        if not segments:
            return
    elif not is_pure_at and has_rules(blacklist):
        for s in segments:
            if s["kind"] == "text" and is_blacklisted(s["text"], blacklist):
                logger.debug(
                    f"[MC·消息转发] 群 {ev.group_id} 消息命中黑名单 '{s['text']}'，跳过转发"
                )
                return

    binds = await MCQQBind.get_by_group_id(ev.group_id)
    if not binds:
        logger.debug(f"[MC·消息转发] 群 {ev.group_id} 未绑定任何MC服务器，跳过转发")
        return

    sender_nickname = ev.sender.get("nickname", "") or ev.user_id
    group_id = ev.group_id
    group_name = await get_group_name(group_id)

    for s in segments:
        if s["kind"] == "at":
            name = await resolve_user_name(ev.bot_id, s["uid"], group_id)
            s["text"] = f"@{name}({s['uid']})" if name else f"(@{s['uid']})"

    for bind in binds:
        server = await MCQQServer.get_by_name(bind.server_name)
        chatimage_enabled = bool(server and server.chatimage_enabled)

        formatted: List[Dict[str, Any]] = []
        if group_name:
            formatted.append(
                {"text": f"<{sender_nickname} ({group_name})> ", "color": "white"}
            )
        else:
            formatted.append({"text": f"<{sender_nickname}> ", "color": "white"})

        for s in segments:
            if s["kind"] == "image":
                url = s.get("url", "")
                if chatimage_enabled:
                    formatted.append(chat_image_code(url))
                else:
                    formatted.append(
                        clickable_text("[图片]", url, "点击查看图片", color="green")
                    )
            elif s["kind"] == "file":
                url = s.get("url", "")
                if url:
                    formatted.append(
                        clickable_text(s["text"], url, "点击查看文件", color="aqua")
                    )
                else:
                    formatted.append({"text": s["text"], "color": "white"})
            else:
                formatted.append({"text": s["text"], "color": "white"})

        success = await send_broadcast(bind.server_name, formatted)
        if success:
            logger.debug(f"[MC·消息转发] 已转发至 '{bind.server_name}'")
        else:
            logger.error(f"[MC·消息转发] 转发至 '{bind.server_name}' 失败")
