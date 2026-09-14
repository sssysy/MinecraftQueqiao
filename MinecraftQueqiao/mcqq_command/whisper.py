from typing import List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core.api import send_private_msg
from ..mcqq_database import MCQQServer, MCQQUserBind
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.component import parse_text_or_json_component
from ..utils.helpers.server_resolve import get_group_main_server
from ..utils.helpers.user_select import extract_at_user_ids

sv_mcqq_whisper = SV("鹊桥私聊指令")


async def _parse_whisper_args(
    ev: Event,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """@目标 | 游戏名|QQ号  +  内容（各为一个 token，空格用 \\+）。"""
    tokens = split_cmd_args(ev.text)
    at_users = extract_at_user_ids(ev)

    if at_users:
        if len(tokens) != 1:
            return (
                None,
                None,
                "参数传递错误\n用法：mc私聊 @用户 <内容>（内容空格请用 \\+）",
            )
        content = decode_arg(tokens[0])
        user_bind = await MCQQUserBind.get_by_user_id(at_users[0])
        if not user_bind:
            return (
                None,
                None,
                f"目标用户 {at_users[0]} 尚未绑定 MC 游戏角色，无法发送私聊。请直接使用游戏内名称",
            )
        return user_bind.player_name, content, None

    if len(tokens) != 2:
        return (
            None,
            None,
            "参数传递错误\n用法：mc私聊 <游戏名|QQ号> <内容>（内容空格请用 \\+）\n"
            "例如：mc私聊 Notch 来\\+我家",
        )

    target_raw = decode_arg(tokens[0]).lstrip("@")
    content = decode_arg(tokens[1])

    if target_raw.isdigit():
        user_bind = await MCQQUserBind.get_by_user_id(target_raw)
        if not user_bind:
            return (
                None,
                None,
                f"目标用户 {target_raw} 尚未绑定 MC 游戏角色，无法发送私聊。请直接使用游戏内名称",
            )
        return user_bind.player_name, content, None

    user_bind = await MCQQUserBind.get_by_player_name(target_raw)
    if user_bind and user_bind.player_name:
        return user_bind.player_name, content, None
    return target_raw, content, None


async def _get_target_servers(ev: Event) -> Tuple[List[MCQQServer], Optional[str]]:
    if ev.user_type == "group" and ev.group_id:
        server, err = await get_group_main_server(ev.group_id)
        if err or server is None:
            return [], err or "当前群未绑定任何可用的 MC 服务器，请先使用 mc群服绑定 指令"
        return [server], None
    servers = await MCQQServer.get_all_enabled()
    if not servers:
        return [], "当前未配置任何启用的 MC 服务器"
    return servers, None


@sv_mcqq_whisper.on_command(
    ("私聊", "私信"),
    block=True,
    to_ai="""向 Minecraft 服务器内正在游玩的指定玩家发送游戏内私信。
仅当用户明确表示要向服务器内的某位玩家发消息时调用。

Args:
    text: 格式 "<目标玩家名或QQ号> <私聊内容>"，空格用 \\+。
""",
)
async def whisper_command(bot: Bot, ev: Event) -> None:
    player_name, content, err = await _parse_whisper_args(ev)
    if err:
        await bot.send(err)
        return
    if not player_name or not content:
        return

    servers, srv_err = await _get_target_servers(ev)
    if srv_err:
        await bot.send(srv_err)
        return

    sender_name = (
        ev.sender.get("nickname") or ev.sender.get("card") or ev.user_id
    )

    components = [
        {"text": f"<{sender_name}(", "color": "white"},
        {"text": "私聊", "color": "yellow"},
        {"text": ")> ", "color": "white"},
    ]
    parsed_content = parse_text_or_json_component(content, default_color="white")
    if isinstance(parsed_content, list):
        components.extend(parsed_content)
    else:
        components.append(parsed_content)

    results = []
    for server in servers:
        server_display = server.display_name or server.server_name
        ok, out = await send_private_msg(
            server.server_name, player_name, components
        )
        if not ok:
            results.append(f"[{server_display}] 发送失败: {out}")
            continue

        out_str = str(out) if out else ""
        if any(
            kw in out_str
            for kw in (
                "No player was found",
                "未找到玩家",
                "找不到玩家",
                "Player not found",
            )
        ):
            results.append(f"未找到玩家 {player_name}")
        else:
            results.append("私聊发送成功")
            logger.info(
                f"[MC·私聊] [{server.server_name}] 已向 {player_name} 发送: {content}"
            )

    await bot.send("\n".join(results))
