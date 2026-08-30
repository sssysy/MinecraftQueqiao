from typing import Any

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import Plugins, SV

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.group_name import get_group_name
from ..utils.helpers.prefix_match import is_blacklisted, match_and_trim_prefix
from ..utils.helpers.user_name import resolve_user_name

sv_mcqq_chat = SV("MC鹊桥聊天转发")


@sv_mcqq_chat.on_message()
async def qq_to_mc_forward(bot: Bot, ev: Event) -> None:
    """群消息转发到MC服务器"""
    # 延迟导入，避免 mcqq_core <-> mcqq_main 循环导入
    from ..mcqq_core import send_broadcast

    if not mcqq_config.get_config("qq_to_mc_enabled").data:
        return

    # 只处理群消息
    if ev.user_type != "group" or not ev.group_id:
        return

    # 按序解析 content 各消息片段，保留原始顺序，避免混发时丢段
    segments: list[dict[str, Any]] = []  # kind: text / at / file / image
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
            # data 形如 "文件名|url"
            name, _, file_url = str(data).partition("|")
            segments.append(
                {
                    "kind": "file",
                    "text": f"[文件 - {name.strip()}]",
                    "url": file_url.strip() if file_url else "",
                }
            )

    # 没有任何可转发内容（纯表情/纯语音等被忽略的片段不会进入 segments）则跳过
    if not segments:
        return

    # 纯 at 消息：整条仅含 @ 目标，无法携带前缀，直接放行
    is_pure_at = has_at and all(s["kind"] == "at" for s in segments)

    # 白名单与黑名单检查（仅对含文本的消息生效；纯 at 消息免过滤）
    whitelist = mcqq_config.get_config("qq_to_mc_whitelist").data
    blacklist = mcqq_config.get_config("qq_to_mc_blacklist").data
    has_whitelist = bool(whitelist) if isinstance(whitelist, str) else any(bool(p) for p in (whitelist or []))

    if has_whitelist and not is_pure_at:
        # 白名单生效：定位首个文本片段并根据前缀/正则匹配与去除
        for i, s in enumerate(segments):
            if s["kind"] == "text":
                matched, new_text = match_and_trim_prefix(s["text"], whitelist)
                if not matched:
                    return
                s["text"] = new_text
                if not s["text"]:
                    del segments[i]
                break
        else:
            # 无文本片段（纯图片/纯文件）且非纯 at：未带前缀则跳过
            return
        if not segments:
            return
    elif not is_pure_at:
        # 白名单为空：黑名单生效
        has_blacklist = bool(blacklist) if isinstance(blacklist, str) else any(bool(p) for p in (blacklist or []))
        if has_blacklist:
            for s in segments:
                if s["kind"] == "text" and is_blacklisted(s["text"], blacklist):
                    logger.debug(
                        f"[MCQueQiao] 群 {ev.group_id} 消息命中黑名单 '{s['text']}'，跳过转发"
                    )
                    return

    # 查询与当前群号绑定的MC服务器
    binds = await MCQQBind.get_by_group_id(ev.group_id)
    if not binds:
        logger.debug(
            f"[MCQueQiao] 群 {ev.group_id} 未绑定任何MC服务器，跳过转发"
        )
        return

    # 获取发送者昵称
    sender_nickname = ev.sender.get("nickname", "") or ev.user_id
    group_id = ev.group_id

    # 获取群名称（数据库查询，未找到则不显示群名前缀）
    group_name = await get_group_name(group_id)

    # 解析 @ 目标昵称（从 CoreUser 缓存查询，展示为 昵称(id)，查不到则退回 (id)）
    for s in segments:
        if s["kind"] == "at":
            name = await resolve_user_name(ev.bot_id, s["uid"], group_id)
            s["text"] = f"@{name}({s['uid']})" if name else f"(@{s['uid']})"

    for bind in binds:
        # 查询该服务器是否开启 ChatImage 图片显示
        server = await MCQQServer.get_by_name(bind.server_name)
        chatimage_enabled = bool(server and server.chatimage_enabled)

        # 按序组装：群名 + <昵称> + 各片段（图片按 ChatImage 是否开启处理）
        formatted: list[dict[str, Any]] = []
        if group_name:
            formatted.append({"text": f"[{group_name}] ", "color": "yellow"})
        formatted.append(
            {"text": f"<{sender_nickname}> ", "color": "white"}
        )
        for s in segments:
            if s["kind"] == "image":
                url = s.get("url", "")
                if chatimage_enabled:
                    formatted.append(
                        {
                            "text": f"[[CICode,url={url},name=图片]]",
                            "color": "white",
                        }
                    )
                else:
                    formatted.append(
                        {
                            "text": "[图片]",
                            "color": "green",
                            "underlined": True,
                            "clickEvent": {
                                "action": "open_url",
                                "value": url,
                            },
                            "hoverEvent": {
                                "action": "show_text",
                                "value": [{"text": "点击在浏览器中查看图片"}],
                            },
                        }
                    )
            elif s["kind"] == "file":
                url = s.get("url", "")
                if url:
                    formatted.append(
                        {
                            "text": s["text"],
                            "color": "aqua",
                            "underlined": True,
                            "clickEvent": {
                                "action": "open_url",
                                "value": url,
                            },
                            "hoverEvent": {
                                "action": "show_text",
                                "value": [{"text": "点击在浏览器中查看/下载文件"}],
                            },
                        }
                    )
                else:
                    formatted.append({"text": s["text"], "color": "white"})
            else:
                formatted.append({"text": s["text"], "color": "white"})

        success = await send_broadcast(bind.server_name, formatted)
        if success:
            logger.info(
                f"[MCQueQiao] 已将群消息转发到服务器 "
                f"'{bind.server_name}': {formatted}"
            )
        else:
            logger.error(
                f"[MCQueQiao] 转发群消息到服务器 "
                f"'{bind.server_name}' 失败"
            )