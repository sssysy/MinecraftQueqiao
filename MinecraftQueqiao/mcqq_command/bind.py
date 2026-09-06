from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_bind = SV("鹊桥群服相关指令")


@sv_mcqq_bind.on_command("群服绑定")
async def bind_server(bot: Bot, ev: Event) -> None:
    # 仅在群聊中执行绑定
    if ev.user_type != "group" or not ev.group_id:
        await bot.send(
            "请在群聊中发送 mc群服绑定<服务器> 指令"
        )
        return

    servers, err = await resolve_servers(ev.text)
    if err:
        await bot.send(err)
        return
    if servers is None or len(servers) != 1:
        await bot.send(
            "请指定一个服务器："
            "mc群服绑定<服务器>，例如 mc群服绑定香草纪元"
        )
        return
    server = servers[0]

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


@sv_mcqq_bind.on_command("群服解绑")
async def unbind_server(bot: Bot, ev: Event) -> None:
    # 仅在群聊中执行解绑
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中发送 mc群服解绑 指令")
        return

    server_id_text = ev.text.strip()
    if not server_id_text:
        await bot.send("格式错误，请使用 mc群服解绑<服务器>，例如 mc群服解绑香草纪元")
        return

    servers, err = await resolve_servers(server_id_text)
    if err:
        await bot.send(err)
        return
    if servers is None or len(servers) != 1:
        await bot.send(
            "请指定一个服务器："
            "mc群服解绑<服务器>，例如 mc群服解绑香草纪元"
        )
        return
    server = servers[0]

    existing = await MCQQBind.get_by_server_group(
        server.server_name, ev.group_id
    )
    if not existing:
        await bot.send(
            f"当前群未绑定服务器 {server.server_name}，无需解绑"
        )
        return

    res = await MCQQBind.delete_row(
        server_name=server.server_name, group_id=ev.group_id
    )
    if res:
        logger.info(
            f"[MCQueQiao] 群 {ev.group_id} 已解绑服务器 "
            f"'{server.server_name}' (ID={server.id})"
        )
        await bot.send(
            f"解绑成功：已将当前群与服务器 {server.server_name} 解除绑定"
        )
    else:
        await bot.send("解绑失败，请稍后重试")