from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer
from ..mcqq_ws import ws_manager
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_status = SV("鹊桥服务器状态指令")


@sv_mcqq_status.on_command("查看")
async def status_command(bot: Bot, ev: Event) -> None:
    # 仅在群聊中执行
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mc查看 [服务器] 指令")
        return

    text = ev.text.strip()

    # 解析可选的服务器选择
    servers, err = await resolve_servers(text)
    if err:
        await bot.send(err)
        return

    # 查询群绑定的服务器
    binds = await MCQQBind.get_by_group_id(ev.group_id)
    if not binds:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    targets: List[MCQQServer] = []
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

    results = []
    for server in targets:
        name = server.display_name or server.server_name
        is_conn = ws_manager.is_connected(server.server_name)
        status_text = "🟢 在线" if is_conn else "🔴 离线"
        ci_text = "已启用" if server.chatimage_enabled else "未启用"

        results.append(
            f"[{name}] 服务器状态：\n"
            f"• WS 名：{server.server_name}\n"
            f"• 反向连接：{status_text}\n"
            f"• CI MOD 支持：{ci_text}"
        )

    await bot.send("\n\n".join(results))
