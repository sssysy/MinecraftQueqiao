from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core import send_rcon_command
from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_rcon = SV("鹊桥 RCON 指令", pm=3)


async def _get_targets(
    group_id: str, servers: Optional[List[MCQQServer]]
) -> List[MCQQServer]:
    """按群绑定 + 选择器筛选目标服务器。servers 为 None 表示全部绑定。"""
    binds = await MCQQBind.get_by_group_id(group_id)
    if not binds:
        return []
    selected_ids = {s.id for s in servers} if servers is not None else None
    targets: List[MCQQServer] = []
    for bind in binds:
        server = await MCQQServer.get_by_name(bind.server_name)
        if server is None:
            continue
        if selected_ids is not None and server.id not in selected_ids:
            continue
        targets.append(server)
    return targets


@sv_mcqq_rcon.on_prefix("rcon")
async def rcon_command(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mcrcon <指令>")
        return

    text = ev.text.strip()
    if not text:
        await bot.send("用法：mcrcon <指令> 或 mcrcon [服务器] <指令>")
        return

    # 解析可选服务器选择器
    servers: Optional[List[MCQQServer]] = None
    command = text
    parts = text.split(maxsplit=1)
    if parts:
        resolved, _ = await resolve_servers(parts[0])
        if resolved is not None:
            servers = resolved
            command = parts[1].strip() if len(parts) > 1 else ""

    if not command:
        await bot.send("指令内容为空，请提供要执行的 Minecraft 指令")
        return

    targets = await _get_targets(ev.group_id, servers)
    if not targets:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    results = []
    for server in targets:
        server_display = server.display_name or server.server_name
        success, out = await send_rcon_command(server.server_name, command)
        if success:
            output_str = str(out).strip() if out else "(无输出)"
            results.append(f"[{server_display}] 执行成功:\n{output_str}")
        else:
            results.append(f"[{server_display}] {out}")

    await bot.send("\n\n".join(results))
