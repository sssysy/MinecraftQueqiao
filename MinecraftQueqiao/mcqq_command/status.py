import asyncio
from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQServer
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.server_resolve import resolve_group_targets, resolve_servers
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

Args:
    text: 可选。服务器名称或 IP（单个参数，IP 可含端口）。留空查当前群绑定服务器。
""",
)
async def status_command(bot: Bot, ev: Event) -> None:
    tokens = split_cmd_args(ev.text)
    if len(tokens) > 1:
        await bot.send(
            "参数传递错误\n用法：mc服务器 [服务器名|IP:端口]"
        )
        return

    servers: Optional[List[MCQQServer]] = None
    if tokens:
        text = decode_arg(tokens[0])
        resolved, err = await resolve_servers(text)
        if resolved:
            servers = resolved
        elif is_server_address(text):
            res = await get_address_status_text(text)
            await bot.send(res)
            return
        elif err:
            await bot.send(err)
            return

    if servers is not None:
        targets = servers
    elif ev.user_type == "group" and ev.group_id:
        resolved, err = await resolve_group_targets(ev.group_id, None)
        if err or not resolved:
            await bot.send(err or "当前群未绑定任何服务器，请手动输入服务器 IP 查询")
            return
        targets = resolved
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
            logger.error(
                f"[MCQueQiao] 查询服务器 '{server.server_name}' 状态失败: {result}",
                exc_info=result,
            )
            lines.append(f"{name}\n状态：查询失败")
        else:
            lines.append(result)

    await bot.send("\n\n".join(lines))