from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.server_resolve import resolve_servers

sv_mcqq_bind = SV("鹊桥群服相关指令")


@sv_mcqq_bind.on_command("群服绑定", block=True)
async def bind_server(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中发送 mc群服绑定 <服务器> 指令")
        return

    tokens = split_cmd_args(ev.text)
    if len(tokens) != 1:
        await bot.send(
            "参数传递错误\n用法：mc群服绑定 <服务器>\n例如：mc群服绑定 香草纪元"
        )
        return

    servers, err = await resolve_servers(decode_arg(tokens[0]))
    if err:
        await bot.send(err)
        return
    if not servers or len(servers) != 1:
        await bot.send(
            "请指定一个服务器\n用法：mc群服绑定 <服务器>\n例如：mc群服绑定 香草纪元"
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

    await bot.send("绑定成功！")


@sv_mcqq_bind.on_command("群服解绑", block=True)
async def unbind_server(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中发送 mc群服解绑 <服务器> 指令")
        return

    tokens = split_cmd_args(ev.text)
    if len(tokens) != 1:
        await bot.send(
            "参数传递错误\n用法：mc群服解绑 <服务器>\n例如：mc群服解绑 香草纪元"
        )
        return

    servers, err = await resolve_servers(decode_arg(tokens[0]))
    if err:
        await bot.send(err)
        return
    if not servers or len(servers) != 1:
        await bot.send(
            "请指定一个服务器\n用法：mc群服解绑 <服务器>\n例如：mc群服解绑 香草纪元"
        )
        return
    server = servers[0]

    existing = await MCQQBind.get_by_server_group(
        server.server_name, ev.group_id
    )
    if not existing:
        await bot.send(
            f"未找到服务器 {server.server_name}"
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
        await bot.send("解绑成功！")
    else:
        await bot.send("解绑失败，请检查控制台")