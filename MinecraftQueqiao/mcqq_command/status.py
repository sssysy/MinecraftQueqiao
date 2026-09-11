import asyncio
from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.server_select import resolve_servers
from ..utils.helpers.server_status import (
    get_address_status_text,
    get_server_status_text,
    is_server_address,
)

sv_mcqq_status = SV("鹊桥服务器状态指令")


@sv_mcqq_status.on_command(
    ("服务器", "服务器状态"), block=True
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
        binds = await MCQQBind.get_by_group_id(ev.group_id)
        if not binds:
            await bot.send(
                "当前群未绑定任何服务器，请手动输入服务器 IP 查询"
            )
            return
        targets = []
        for bind in binds:
            server = await MCQQServer.get_by_name(bind.server_name)
            if server:
                targets.append(server)
        if not targets:
            await bot.send("未找到当前群绑定的有效服务器")
            return
    else:
        targets = await MCQQServer.get_all_enabled()
        if not targets:
            await bot.send("当前未配置任何启用的 MC 服务器")
            return

    # 并发查询所有目标服务器状态
    tasks = [get_server_status_text(server) for server in targets]
    results = await asyncio.gather(*tasks)

    await bot.send("\n\n".join(results))




