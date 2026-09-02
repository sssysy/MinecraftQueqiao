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

    connected_count = 0
    lines = ["【Minecraft 鹊桥连接状态】"]
    for server in servers:
        name = server.display_name or server.server_name
        is_conn = ws_manager.is_connected(server.server_name)
        if is_conn:
            connected_count += 1
            status_tag = "🟢 在线"
        else:
            status_tag = "🔴 离线"

        lines.append(f"• {name} ({server.server_name}): {status_tag}")

    lines.append(
        f"\n共 {len(servers)} 个配置服务器，已连接: {connected_count} 个"
    )
    await bot.send("\n".join(lines))