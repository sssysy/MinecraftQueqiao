import json
from typing import Any

from gsuid_core.bot import Bot
from gsuid_core.gss import gss
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQBind

from . import forwarder

async def ws_event_handler(server_name: str, raw_message: str) -> None:
    """WS 消息事件分发入口。

    接收来自 mcqq_core 委托的 WS 消息，解析 JSON 后按 type/sub_type
    分发到对应的格式化函数，并推送到关联的 QQ 群。

    Args:
        server_name: 服务器名称
        raw_message: 原始 WS 消息字符串
    """
    if not mcqq_config.get_config("mc_to_qq_enabled").data:
        return

    try:
        data: dict[str, Any] = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.info(f"[MCQueQiao] [{server_name}] 收到非 JSON 消息: {raw_message}")
        return

    post_type = data.get("post_type", "")

    if post_type == "response":
        # API 响应消息，仅日志记录
        logger.info(
            f"[MCQueQiao] [{server_name}] 收到API响应: "
            f"api={data.get('api')}, "
            f"status={data.get('status')}, "
            f"echo={data.get('echo')}"
        )
        return

    # 事件消息（message / notice）
    sub_type = data.get("sub_type", "")
    text = format_event_message(data, sub_type)
    if text is None:
        # 未识别的事件类型或对应开关关闭
        logger.debug(
            f"[MCQueQiao] [{server_name}] 未处理的事件: "
            f"sub_type={sub_type}, "
            f"event={data.get('event_name')}"
        )
        return

    logger.info(
        f"[MCQueQiao] [{server_name}] 事件分发: "
        f"sub_type={sub_type}, "
        f"text={text}"
    )

    await push_to_qq_group(server_name, text)


def format_event_message(data: dict[str, Any], sub_type: str) -> str | None:
    """根据事件子类型格式化消息文本。

    同时兼容 v2 协议（sub_type 带 player_ 前缀）和 v1 协议。

    Args:
        data: 事件数据字典
        sub_type: 事件子类型

    Returns:
        格式化后的消息文本，如果事件类型不匹配或对应开关关闭则返回 None
    """
    # 将 v2 sub_type 映射到配置键名
    sub_type_to_config = {
        "player_chat": "subscribe_player_chat",
        "player_achievement": "subscribe_player_achievement",
        "player_death": "subscribe_player_death",
        "player_join": "subscribe_player_join",
        "player_quit": "subscribe_player_quit",
        "player_command": "subscribe_player_command",
        # v1 兼容
        "chat": "subscribe_player_chat",
        "death": "subscribe_player_death",
        "join": "subscribe_player_join",
        "quit": "subscribe_player_quit",
        "player_command": "subscribe_player_command",
    }

    config_key = sub_type_to_config.get(sub_type)
    if config_key is None:
        return None

    # 检查对应事件类型的订阅开关
    if not mcqq_config.get_config(config_key).data:
        logger.debug(f"[MCQueQiao] 事件 {sub_type} 的开关已关闭，跳过")
        return None

    server_name = data.get("server_name", "Unknown")
    player = data.get("player", {})
    player_name = player.get("nickname", "Unknown") if isinstance(player, dict) else "Unknown"

    if sub_type in ("player_chat", "chat"):
        message = data.get("message", "")
        return f"[{server_name}] <{player_name}> {message}"

    if sub_type in ("player_death", "death"):
        death = data.get("death", {})
        death_text = ""
        if isinstance(death, dict):
            death_text = death.get("text", "") or ""
        if not death_text:
            death_text = data.get("message", f"{player_name} 死亡了")
        return f"[{server_name}] {death_text}"

    if sub_type in ("player_join", "join"):
        return f"[{server_name}] {player_name} 加入了游戏"

    if sub_type in ("player_quit", "quit"):
        return f"[{server_name}] {player_name} 离开了游戏"

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
        return f"[{server_name}] {achievement_text}"

    if sub_type in ("player_command",):
        command = data.get("command", data.get("message", ""))
        return f"[{server_name}] <{player_name}> 执行了命令: {command}"

    return None


async def push_to_qq_group(server_name: str, text: str) -> None:
    """将格式化后的消息推送到服务器绑定的 QQ 群。

    通过绑定表（MCQQBind）中记录的 ws_bot_id / bot_id / bot_self_id /
    group_id 精确定位对应的活跃 Bot 与群，避免遍历所有 Bot 导致发往错误群。

    Args:
        server_name: 服务器名称
        text: 要发送的消息文本
    """
    binds = await MCQQBind.get_by_server_name(server_name)
    if not binds:
        logger.debug(
            f"[MCQueQiao] 服务器 '{server_name}' 未绑定任何 QQ 群，跳过推送"
        )
        return

    if not gss.active_bot:
        logger.warning("[MCQueQiao] 没有活跃的 Bot 连接，无法推送消息")
        return

    for bind in binds:
        await _send_to_bind(bind, text)


async def _send_to_bind(bind: MCQQBind, text: str) -> None:
    """按绑定行中的连接信息向指定群发送消息。

    逻辑参考 gs_subscribe / Subscribe.send：使用 WS_BOT_ID 定位活跃 Bot。
    """
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
    try:
        await bot.send(MessageSegment.text(text))
        logger.info(
            f"[MCQueQiao] [{bind.server_name}] 已推送消息到群 "
            f"{bind.group_id}: {text}"
        )
    except Exception as e:
        logger.error(
            f"[MCQueQiao] [{bind.server_name}] 推送消息到群 "
            f"{bind.group_id} 失败: {e}"
        )