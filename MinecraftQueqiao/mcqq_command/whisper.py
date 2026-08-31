import json
from typing import List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core import send_rcon_command
from ..mcqq_database import MCQQBind, MCQQServer, MCQQUserBind
from ..mcqq_ws import ws_manager
from ..utils.helpers.component import parse_text_or_json_component

sv_mcqq_whisper = SV("鹊桥私聊指令")


async def _parse_whisper_args(
    ev: Event,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """解析私聊参数。
    
    Returns:
        (player_name, content, error_msg)
    """
    raw_text = ev.text.strip()
    target_uid: Optional[str] = None
    content: str = ""

    # 1. 优先提取 @用户
    if ev.at_list:
        for at_item in ev.at_list:
            if at_item and str(at_item).strip():
                target_uid = str(at_item).strip()
                break
    elif ev.at and ev.at.strip():
        target_uid = ev.at.strip()

    if target_uid:
        content = raw_text
    else:
        parts = raw_text.split(maxsplit=1)
        if len(parts) < 2:
            return (
                None,
                None,
                "用法：mc私聊 <@用户 / QQ号 / 游戏ID> <私聊内容>\n"
                "例如：mc私聊 @张三 你好呀 / mc私聊 12345678 快上线 / mc私聊 Steve 收到请回复",
            )
        first_token = parts[0].strip().lstrip("@")
        content = parts[1].strip()
        if first_token.isdigit():
            target_uid = first_token
        else:
            # 可能是 MC 游戏名，也可能是绑定的用户名
            user_bind = await MCQQUserBind.get_by_user_id(first_token)
            if user_bind:
                return user_bind.player_name, content, None
            # 直接作为 MC 游戏名
            return first_token, content, None

    if not content:
        return None, None, "私聊内容不能为空，请提供要发送的文本"

    # 如果指定了 target_uid，查询绑定表
    user_bind = await MCQQUserBind.get_by_user_id(target_uid)
    if not user_bind:
        return (
            None,
            None,
            f"目标用户 {target_uid} 尚未绑定 MC 游戏角色，无法发送私聊。\n"
            f"可使用 mc绑定 <游戏ID> 进行绑定，或直接输入对方游戏名（如 mc私聊 Steve 内容）。",
        )

    return user_bind.player_name, content, None


async def _get_target_servers(ev: Event) -> Tuple[List[MCQQServer], Optional[str]]:
    """获取要发送私聊的目标服务器列表。"""
    if ev.user_type == "group" and ev.group_id:
        binds = await MCQQBind.get_by_group_id(ev.group_id)
        if not binds:
            return [], "当前群未绑定任何 MC 服务器，请先使用 mc群服绑定 指令"
        servers: List[MCQQServer] = []
        for bind in binds:
            server = await MCQQServer.get_by_name(bind.server_name)
            if server and server.enabled:
                servers.append(server)
        if not servers:
            return [], "当前群绑定的服务器均未启用或配置异常"
        return servers, None
    else:
        # 私聊环境：发送至所有已启用的服务器
        servers = await MCQQServer.get_all_enabled()
        if not servers:
            return [], "当前未配置任何启用的 MC 服务器"
        return servers, None


@sv_mcqq_whisper.on_command(("私聊", "私信"))
async def whisper_command(bot: Bot, ev: Event) -> None:
    """向 Minecraft 玩家发送私聊消息（通过 tellraw）。
    用法：
      mc私聊 <@用户 / QQ号 / 游戏ID> <私聊内容>
    """
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
    if not servers:
        await bot.send("未找到可用的目标服务器")
        return

    # 发送者名称
    sender_name = (
        ev.sender.get("nickname")
        or ev.sender.get("card")
        or ev.user_id
    )

    # 构造 tellraw JSON
    components = [
        {"text": f"<{sender_name}(", "color": "white"},
        {"text": "私聊", "color": "yellow"},
        {"text": ")> ", "color": "white"},
    ]
    parsed_content = parse_text_or_json_component(content, default_color="white")
    if isinstance(parsed_content, list):
        components.extend(parsed_content)
    elif isinstance(parsed_content, dict):
        components.append(parsed_content)
    else:
        components.append({"text": str(content), "color": "white"})

    tellraw_json_str = json.dumps(components, ensure_ascii=False)

    target_selector = f'"{player_name}"' if " " in player_name else player_name
    rcon_cmd = f"tellraw {target_selector} {tellraw_json_str}"

    results = []
    for server in servers:
        server_display = server.display_name or server.server_name

        if not ws_manager.is_connected(server.server_name):
            results.append(f"[{server_display}] 服务器当前离线（WS未连接）")
            continue

        success, out = await send_rcon_command(server.server_name, rcon_cmd)
        if success:
            out_str = str(out).strip() if out else ""
            # 判断 Minecraft 提示是否未找到玩家
            if any(
                kw in out_str
                for kw in ("No player was found", "未找到玩家", "找不到玩家", "Player not found")
            ):
                results.append(f"[{server_display}] 未找到玩家 {player_name}（玩家可能不在线）")
            else:
                results.append(f"[{server_display}] 私聊已发送给玩家 {player_name}")
                logger.info(
                    f"[MCQueQiao] [{server.server_name}] 已向玩家 {player_name} 发送私聊: "
                    f"<{sender_name}(私聊)> {content}"
                )
        else:
            results.append(f"[{server_display}] 发送失败: {out}")

    await bot.send("\n".join(results))
