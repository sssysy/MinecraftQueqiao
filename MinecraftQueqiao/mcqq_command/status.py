import asyncio
from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQServer
from ..utils.helpers.server_resolve import get_group_target_servers, resolve_servers
from ..utils.helpers.server_status import (
    get_address_status_text,
    get_server_status_text,
    is_server_address,
)

sv_mcqq_status = SV("鹊桥服务器状态指令")


@sv_mcqq_status.on_command(
    ("服务器", "服务器状态"),
    block=True,
    to_ai="""查询当前 Minecraft 服务器的运行状态。
当用户询问服务器是否在线、服务器挂了吗、当前在线人数、在线玩家列表、服务器地址或延迟时调用。

Args:
    text: 可选。指定服务器名称或 IP；留空则查询当前群绑定的所有服务器。
""",
)
async def status_command(bot: Bot, ev: Event) -> None:
    text = ev.text.strip()
    servers: Optional[List[MCQQServer]] = None

    if text:
        resolved, err = await resolve_servers(text)
        if resolved:
            servers = resolved
        else:
            if is_server_address(text):
                res = await get_address_status_text(text)
                await bot.send(res)
                return
            if err:
                await bot.send(err)
                return

    if servers is not None:
        targets = servers
    elif ev.user_type == "group" and ev.group_id:
        targets = await get_group_target_servers(ev.group_id, None)
        if not targets:
            await bot.send("当前群未绑定任何服务器，请手动输入服务器 IP 查询")
            return
    else:
        targets = await MCQQServer.get_all_enabled()
        if not targets:
            await bot.send("当前未配置任何启用的 MC 服务器")
            return

    tasks = [get_server_status_text(server) for server in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    lines: List[str] = []
    for server, result in zip(targets, results):
        if isinstance(result, Exception):
            name = server.display_name or server.server_name
            lines.append(f"{name}\n状态：查询失败 ({result})")
        else:
            lines.append(result)

    await bot.send("\n\n".join(lines))
