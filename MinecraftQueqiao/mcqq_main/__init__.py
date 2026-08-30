import json
from typing import Any

from gsuid_core.bot import Bot
from gsuid_core.gss import gss
from gsuid_core.logger import logger
from gsuid_core.models import Event, Message
from gsuid_core.segment import MessageSegment

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.prefix_match import is_blacklisted, match_and_trim_prefix
from ..utils.utils.cicode import parse_cicode

from . import forwarder


async def ws_event_handler(server_name: str, raw_message: str) -> None:
    """WS 消息事件分发入口"""
    try:
        data: dict[str, Any] = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.info(f"[MCQueQiao] [{server_name}] 收到非 JSON 消息: {raw_message}")
        return

    post_type = data.get("post_type", "")

    if post_type == "response":
        # API 响应消息，仅日志记录
        logger.debug(
            f"[MCQueQiao] [{server_name}] 收到API响应: "
            f"api={data.get('api')}, "
            f"status={data.get('status')}, "
            f"echo={data.get('echo')}"
        )
        return

    # 事件消息（message / notice）
    sub_type = data.get("sub_type", "")

    # 查询服务器配置（外显名）与全局前缀开关
    display_name = None
    server = await MCQQServer.get_by_name(server_name)
    if server is not None:
        display_name = server.display_name or server.server_name

    show_server_name: bool = mcqq_config.get_config("show_server_name").data

    text = format_event_message(data, sub_type, show_server_name, display_name)
    if text is None:
        # 未识别的事件类型或对应开关关闭
        logger.debug(
            f"[MCQueQiao] [{server_name}] 未处理的事件: "
            f"sub_type={sub_type}, "
            f"event={data.get('event_name')}"
        )
        return

    logger.debug(
        f"[MCQueQiao] [{server_name}] 事件分发: "
        f"sub_type={sub_type}, "
        f"text={text}"
    )

    # 消息过滤：仅对玩家聊天消息生效
    # 白名单优先；白名单为空时黑名单生效
    if sub_type in ("player_chat", "chat"):
        whitelist = mcqq_config.get_config("mc_to_qq_whitelist").data
        blacklist = mcqq_config.get_config("mc_to_qq_blacklist").data
        raw_message = str(data.get("message", ""))

        has_whitelist = bool(whitelist) if isinstance(whitelist, str) else any(bool(p) for p in (whitelist or []))
        if has_whitelist:
            matched, _ = match_and_trim_prefix(raw_message, whitelist)
            if not matched:
                logger.debug(
                    f"[MCQueQiao] [{server_name}] 玩家聊天内容未匹配白名单 "
                    f"{whitelist}，跳过推送"
                )
                return
        else:
            # 白名单为空：黑名单生效
            if is_blacklisted(raw_message, blacklist):
                logger.debug(
                    f"[MCQueQiao] [{server_name}] 玩家聊天内容匹配黑名单 "
                    f"{blacklist}，跳过推送"
                )
                return

    await push_to_qq_group(server_name, text)


def format_event_message(
    data: dict[str, Any],
    sub_type: str,
    show_server_name: bool = True,
    display_name: str | None = None,
) -> str | None:
    """格式化消息文本。"""
    # 将 sub_type 映射到事件名（订阅列表中的取值）
    sub_type_to_event = {
        "player_chat": "玩家聊天",
        "chat": "玩家聊天",
        "player_achievement": "玩家成就",
        "player_death": "玩家死亡",
        "death": "玩家死亡",
        "player_join": "玩家加入",
        "join": "玩家加入",
        "player_quit": "玩家退出",
        "quit": "玩家退出",
        "player_command": "玩家命令",
    }

    event_name = sub_type_to_event.get(sub_type)
    if event_name is None:
        return None

    # 检查对应事件类型是否在订阅列表中
    subscribed = mcqq_config.get_config("subscribe_events").data
    if event_name not in subscribed:
        logger.debug(f"[MCQueQiao] 事件 {sub_type} 未在订阅列表中，跳过")
        return None

    server_name = display_name or data.get("server_name", "Unknown")
    player = data.get("player", {})
    player_name = player.get("nickname", "Unknown") if isinstance(player, dict) else "Unknown"

    # 服务器名称前缀，关闭显示时为空
    prefix = f"[{server_name}] " if show_server_name else ""

    if sub_type in ("player_chat", "chat"):
        message = str(data.get("message", ""))
        # 若配置了白名单，去除触发前缀（正则匹配则保留原文本）
        chat_whitelist = mcqq_config.get_config("mc_to_qq_whitelist").data
        has_whitelist = bool(chat_whitelist) if isinstance(chat_whitelist, str) else any(bool(p) for p in (chat_whitelist or []))
        if has_whitelist:
            matched, new_message = match_and_trim_prefix(message, chat_whitelist)
            if matched:
                message = new_message
        return f"{prefix}<{player_name}> {message}"

    if sub_type in ("player_death", "death"):
        death = data.get("death", {})
        death_text = ""
        if isinstance(death, dict):
            death_text = death.get("text", "") or ""
        if not death_text:
            death_text = data.get("message", f"{player_name} 死亡了")
        return f"{prefix}{death_text}"

    if sub_type in ("player_join", "join"):
        return f"{prefix}{player_name} 加入了游戏"

    if sub_type in ("player_quit", "quit"):
        return f"{prefix}{player_name} 离开了游戏"

    if sub_type in ("player_achievement",):
        achievement = data.get("achievement", {})
        achievement_text = ""
        if isinstance(achievement, dict):
            # v0.4.1+ 使用 translate.text
            translate = achievement.get("translate")
            if isinstance(translate, dict):
                achievement_text = translate.get("text", "") or ""
            # v0.4.0 及以下使用 text
            if not achievement_text:
                achievement_text = achievement.get("text", "") or ""
        if not achievement_text:
            achievement_text = f"{player_name} 获得了成就"
        return f"{prefix}{achievement_text}"

    if sub_type in ("player_command",):
        command = data.get("command", data.get("message", ""))
        return f"{prefix}<{player_name}> 执行了命令: {command}"

    return None


async def push_to_qq_group(server_name: str, text: str) -> None:
    """消息推送到服务器绑定的群"""
    binds = await MCQQBind.get_by_server_name(server_name)
    if not binds:
        logger.debug(
            f"[MCQueQiao] 服务器 '{server_name}' 未绑定任何群组，跳过推送"
        )
        return

    if not gss.active_bot:
        logger.warning("[MCQueQiao] 没有活跃的 Bot 连接，无法推送消息")
        return

    for bind in binds:
        await _send_to_bind(bind, text)


async def _send_to_bind(bind: MCQQBind, text: str) -> None:
    """按绑定行中的连接信息向指定群发送消息"""
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

    # 解析 CICode 图片，转为 QQ 图片段
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