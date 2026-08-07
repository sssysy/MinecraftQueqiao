from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer
from ..mcqq_rcon import rcon_run
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_rcon = SV("鹊桥 RCON 指令", pm=3)


@sv_mcqq_rcon.on_prefix("rcon")
async def rcon_command(bot: Bot, ev: Event) -> None:
    # 仅在群聊中执行
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mcrcon <指令>")
        return

    text = ev.text.strip()
    if not text:
        await bot.send(
            "用法：mcrcon <指令> 或 mcrcon [服务器] <指令>"
        )
        return

    # 解析可选的服务器选择：首词为数字或能解析为服务器时当作选择器，其余为指令
    servers = None  # None 表示不筛选（作用于全部绑定服务器）
    command = text
    parts = text.split(maxsplit=1)
    if parts:
        first = parts[0]
        resolved, _ = await resolve_servers(first)
        if resolved is not None:
            servers = resolved
            command = parts[1].strip() if len(parts) > 1 else ""

    if not command:
        await bot.send("指令内容为空，请提供要执行的Minecraft指令")
        return

    # 查询群绑定的服务器
    binds = await MCQQBind.get_by_group_id(ev.group_id)
    if not binds:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    targets = []
    for bind in binds:
        server = await MCQQServer.get_by_name(bind.server_name)
        if server is None:
            continue
        if servers is not None and server.id not in {s.id for s in servers}:
            continue
        targets.append(server)

    if not targets:
        await bot.send("未找到匹配的服务器")
        return

    # 逐个执行并汇总结果
    results = []
    for server in targets:
        if not server.rcon_enabled:
            results.append(f"「{server.server_name}」未开启 RCON")
            continue
        if not server.rcon_host or not server.rcon_password:
            results.append(f"「{server.server_name}」RCON 配置不完整")
            continue
        try:
            output = await rcon_run(
                server.rcon_host,
                server.rcon_port,
                server.rcon_password,
                command,
            )
            out = output.strip()
            results.append(
                f"「{server.server_name}」: {out if out else '(无输出)'}"
            )
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{server.server_name}] RCON 执行指令失败: {e}"
            )
            results.append(f"「{server.server_name}」执行指令失败，详见控制台")

    await bot.send("\n".join(results))