from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQServer
from ..mcqq_ws import ws_manager

sv_mcqq_ws = SV("鹊桥ws连接状态指令", pm=3)


@sv_mcqq_ws.on_fullmatch(("连接状态", "ws状态", "WS状态", "刷新ws连接"))
async def check_ws_status(bot: Bot, ev: Event) -> None:
    servers = await MCQQServer.get_all_enabled()
    if not servers:
        await bot.send("当前未配置任何启用的 MC 服务器")
        return

    online_servers = []
    offline_servers = []
    for server in servers:
        name = server.display_name or server.server_name
        if ws_manager.is_connected(server.server_name):
            online_servers.append(name)
        else:
            offline_servers.append(name)

    lines = ["服务器连接状态"]
    if online_servers:
        lines.append("[在线]")
        for s in online_servers:
            lines.append(f" - {s}")
    if offline_servers:
        lines.append("[离线]")
        for s in offline_servers:
            lines.append(f" - {s}")

    await bot.send("\n".join(lines))