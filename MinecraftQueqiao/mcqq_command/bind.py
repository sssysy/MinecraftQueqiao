from typing import Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.server_resolve import resolve_servers

sv_mcqq_bind = SV("鹊桥群服相关指令")


async def _resolve_one_server(
    bot: Bot, text: str, usage: str
) -> Optional[MCQQServer]:
    tokens = split_cmd_args(text)
    if len(tokens) != 1:
        await bot.send(f"参数传递错误\n{usage}")
        return None
    servers, err = await resolve_servers(decode_arg(tokens[0]))
    if err:
        await bot.send(err)
        return None
    if not servers or len(servers) != 1:
        await bot.send(usage)
        return None
    return servers[0]


@sv_mcqq_bind.on_command("群服绑定", block=True)
async def bind_server(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中发送 mc群服绑定 <服务器> 指令")
        return

    usage = "用法：mc群服绑定 <服务器>\n例如：mc群服绑定 香草纪元"
    server = await _resolve_one_server(bot, ev.text, usage)
    if server is None:
        return

    mains = await MCQQBind.get_mains_by_group(ev.group_id)
    has_main = bool(mains)

    existing = await MCQQBind.get_by_server_group(
        server.server_name, ev.group_id
    )
    if existing:
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
        # 无主服时把本次更新的服务器提升为主服；有主服则保留其原 is_main
        if not has_main:
            bind_data["is_main"] = True
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
        await MCQQBind.full_insert_data(
            server_id=server.id,
            server_name=server.server_name,
            group_id=ev.group_id,
            ws_bot_id=ev.WS_BOT_ID or "",
            bot_id=ev.bot_id,
            bot_self_id=ev.bot_self_id,
            user_type=ev.user_type,
            msg_id=ev.msg_id,
            user_id=ev.user_id,
            is_main=not has_main,
        )
        logger.info(
            f"[MCQueQiao] 群 {ev.group_id} 已绑定服务器 "
            f"'{server.server_name}' (ID={server.id}, main={not has_main})"
        )

    display = server.display_name or server.server_name
    if not has_main:
        await bot.send(f"绑定成功！\n已将 [{display}] 设为本群主服务器")
    else:
        await bot.send("绑定成功！")


@sv_mcqq_bind.on_command("群服解绑", block=True)
async def unbind_server(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中发送 mc群服解绑 <服务器> 指令")
        return

    usage = "用法：mc群服解绑 <服务器>\n例如：mc群服解绑 香草纪元"
    server = await _resolve_one_server(bot, ev.text, usage)
    if server is None:
        return

    existing = await MCQQBind.get_by_server_group(
        server.server_name, ev.group_id
    )
    if not existing:
        await bot.send(
            f"未找到服务器 {server.server_name}"
        )
        return

    was_main = existing.is_main
    res = await MCQQBind.delete_row(
        server_name=server.server_name, group_id=ev.group_id
    )
    if res:
        logger.info(
            f"[MCQueQiao] 群 {ev.group_id} 已解绑服务器 "
            f"'{server.server_name}' (ID={server.id})"
        )
        if was_main:
            await bot.send(
                "解绑成功！\n注意：已解绑主服务器，"
                "请使用 mc切换主服务器 <服务器> 设置新的主服务器"
            )
        else:
            await bot.send("解绑成功！")
    else:
        await bot.send("解绑失败，请检查控制台")


@sv_mcqq_bind.on_command("切换主服务器", block=True)
async def switch_main_server(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中发送 mc切换主服务器 <服务器> 指令")
        return

    usage = "用法：mc切换主服务器 <服务器>\n例如：mc切换主服务器 香草纪元"
    server = await _resolve_one_server(bot, ev.text, usage)
    if server is None:
        return

    existing = await MCQQBind.get_by_server_group(
        server.server_name, ev.group_id
    )
    if not existing:
        await bot.send("当前群未绑定该服务器，请先使用 mc群服绑定 指令")
        return

    ok = await MCQQBind.set_main_for_group(ev.group_id, server.server_name)
    if not ok:
        await bot.send("切换失败，请检查控制台")
        return

    display = server.display_name or server.server_name
    logger.info(
        f"[MCQueQiao] 群 {ev.group_id} 主服务器已切换为 "
        f"'{server.server_name}' (ID={server.id})"
    )
    await bot.send(f"已将 [{display}] 设为本群主服务器")
