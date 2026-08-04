from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer

sv_mcqq_bind = SV("MC鹊桥绑定")


@sv_mcqq_bind.on_prefix("绑定")
async def bind_server(bot: Bot, ev: Event) -> None:
    # 仅在群聊中执行绑定
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中发送 mc绑定<服务器ID> 指令")
        return

    server_id_text = ev.text.strip()
    if not server_id_text.isdigit():
        await bot.send("格式错误，请使用 mc绑定<服务器ID>，例如 mc绑定1")
        return

    server_id = int(server_id_text)
    server = await MCQQServer.get_by_id(server_id)
    if not server:
        await bot.send(f"未找到 ID 为 {server_id} 的服务器，请先在网页控制台确认服务器ID")
        return

    # 写绑定数据库
    bind_data = {
        "server_id": server.id,
        "server_name": server.server_name,
        "group_id": ev.group_id,
        "ws_bot_id": ev.WS_BOT_ID or "",
        "bot_id": ev.bot_id,
        "bot_self_id": ev.bot_self_id,
        "user_type": ev.user_type,
        "msg_id": ev.msg_id,
        "user_id": ev.user_id,
    }

    existing = await MCQQBind.get_by_server_group(
        server.server_name, ev.group_id
    )
    if existing:
        await MCQQBind.update_data_by_data(
            {
                "server_name": server.server_name,
                "group_id": ev.group_id,
            },
            bind_data,
        )
        logger.info(
            f"[MCQueQiao] 群 {ev.group_id} 与服务器 "
            f"'{server.server_name}' 绑定已更新"
        )
    else:
        await MCQQBind.full_insert_data(**bind_data)
        logger.info(
            f"[MCQueQiao] 群 {ev.group_id} 已绑定服务器 "
            f"'{server.server_name}' (ID={server.id})"
        )

    await bot.send(
        f"绑定成功：已将当前群绑定至服务器 {server.server_name}"
    )