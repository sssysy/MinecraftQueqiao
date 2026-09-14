from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_config import mcqq_config
from ..mcqq_core.api import send_rcon_command
from ..mcqq_database import MCQQServer, MCQQRconWhitelist
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args, split_user_ids
from ..utils.helpers.admin import is_admin
from ..utils.helpers.prefix_rules import is_command_blacklisted
from ..utils.helpers.server_resolve import (
    resolve_group_targets,
    resolve_servers,
)
from ..utils.helpers.user_name import resolve_user_name

sv_mcqq_rcon_admin = SV("鹊桥 RCON 管理员管理", pm=3, priority=4)
sv_mcqq_rcon = SV("鹊桥 RCON 指令", pm=6, priority=5)


@sv_mcqq_rcon.on_command("rcon", block=True)
async def rcon_command(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mcrcon <指令>")
        return

    tokens = split_cmd_args(ev.text)
    if not tokens:
        await bot.send("用法：mcrcon [服务器] <指令>")
        return

    servers: Optional[List[MCQQServer]] = None
    # 首 token 是服务器则吃掉，其余全部是指令（允许空格）
    if len(tokens) >= 2:
        resolved, err = await resolve_servers(tokens[0])
        if resolved:
            servers = resolved
            command = " ".join(decode_arg(t) for t in tokens[1:])
        elif err and err.startswith("有多个"):
            await bot.send(err)
            return
        else:
            command = " ".join(decode_arg(t) for t in tokens)
    else:
        command = decode_arg(tokens[0])

    if not command:
        await bot.send("未提供指令\n用法：mcrcon [服务器] <指令>")
        return

    blacklist = mcqq_config.get_config("command_blacklist").data
    if is_command_blacklisted(command, blacklist):
        await bot.send("黑名单指令！")
        return

    targets, err = await resolve_group_targets(ev.group_id, servers)
    if err or not targets:
        await bot.send(err or "当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    results = []
    for server in targets:
        server_display = server.display_name or server.server_name
        if not await is_admin(server.server_name, ev=ev):
            results.append(f"您没有在 {server_display} 执行指令的权限")
            continue

        success, out = await send_rcon_command(server.server_name, command)
        if success:
            output_str = str(out).strip() if out else ""
            if output_str:
                results.append(f"执行命令成功\n> {output_str}")
            else:
                results.append("命令执行完毕")
        else:
            results.append(f"[{server_display}] {out}")

    await bot.send("\n\n".join(results))


async def _resolve_admin_targets(
    bot: Bot, ev: Event, servers: Optional[List[MCQQServer]]
) -> Optional[List[MCQQServer]]:
    if servers is not None:
        return servers
    if ev.user_type == "group" and ev.group_id:
        targets, err = await resolve_group_targets(ev.group_id, None)
        if err or not targets:
            await bot.send(err or "当前群未绑定任何服务器")
            return None
        return targets
    return None


async def _parse_admin_args(
    bot: Bot, ev: Event, usage: str
) -> Optional[tuple[Optional[List[MCQQServer]], List[str]]]:
    """[服务器] <用户QQ[,用户QQ]|@用户>。多用户用逗号；@ 可多个。"""
    from ..utils.helpers.user_select import extract_at_user_ids

    at_users = extract_at_user_ids(ev)
    tokens = split_cmd_args(ev.text)
    servers: Optional[List[MCQQServer]] = None
    user_ids: List[str] = list(at_users)

    if at_users:
        # 有 @ 时：可选服务器为唯一 token
        if len(tokens) > 1:
            await bot.send(f"参数传递错误\n用法：{usage}")
            return None
        if tokens:
            resolved, err = await resolve_servers(tokens[0])
            if err or not resolved:
                await bot.send(err or f"未找到服务器 {tokens[0]}")
                return None
            servers = resolved
    else:
        if not tokens:
            await bot.send(f"未检测到目标用户\n用法：{usage}")
            return None
        if len(tokens) == 1:
            user_ids.extend(split_user_ids(tokens[0]))
        elif len(tokens) == 2:
            resolved, err = await resolve_servers(tokens[0])
            if err or not resolved:
                await bot.send(err or f"未找到服务器 {tokens[0]}")
                return None
            servers = resolved
            user_ids.extend(split_user_ids(tokens[1]))
        else:
            await bot.send(
                f"参数传递错误，多用户请用逗号分隔\n用法：{usage}"
            )
            return None

    # 去重保序
    seen: set[str] = set()
    unique: List[str] = []
    for uid in user_ids:
        if uid not in seen:
            seen.add(uid)
            unique.append(uid)
    return servers, unique


@sv_mcqq_rcon_admin.on_command(("增加rcon管理员", "添加rcon管理员"), block=True)
async def add_rcon_admin(bot: Bot, ev: Event) -> None:
    usage = "mc增加rcon管理员 [服务器] <@用户|QQ号[,QQ号]>"
    parsed = await _parse_admin_args(bot, ev, usage)
    if parsed is None:
        return
    servers, user_ids = parsed

    targets = await _resolve_admin_targets(bot, ev, servers)
    if targets is None:
        if ev.user_type != "group" and servers is None:
            await bot.send(f"请指定服务器\n例如：{usage}")
        return

    results = []
    for server in targets:
        for uid in user_ids:
            existing = await MCQQRconWhitelist.get_by_server_and_user(
                server.server_name, uid
            )
            if existing:
                results.append("用户已存在")
            else:
                await MCQQRconWhitelist.full_insert_data(
                    server_name=server.server_name,
                    user_id=uid,
                )
                logger.info(
                    f"[MC·RCON] 已将用户 {uid} 添加至 '{server.server_name}' 白名单"
                )
                results.append("用户增加成功")

    await bot.send("\n".join(results))


@sv_mcqq_rcon_admin.on_command(("删除rcon管理员", "移除rcon管理员"), block=True)
async def delete_rcon_admin(bot: Bot, ev: Event) -> None:
    usage = "mc删除rcon管理员 [服务器] <@用户|QQ号[,QQ号]>"
    parsed = await _parse_admin_args(bot, ev, usage)
    if parsed is None:
        return
    servers, user_ids = parsed

    targets = await _resolve_admin_targets(bot, ev, servers)
    if targets is None:
        if ev.user_type != "group" and servers is None:
            await bot.send(f"请指定服务器\n例如：{usage}")
        return

    results = []
    for server in targets:
        for uid in user_ids:
            existing = await MCQQRconWhitelist.get_by_server_and_user(
                server.server_name, uid
            )
            if not existing:
                results.append("用户不存在")
            else:
                await MCQQRconWhitelist.delete_row(
                    server_name=server.server_name,
                    user_id=uid,
                )
                logger.info(
                    f"[MC·RCON] 已将用户 {uid} 从 '{server.server_name}' 白名单移除"
                )
                results.append("用户删除成功")

    await bot.send("\n".join(results))


@sv_mcqq_rcon_admin.on_command(
    ("查看rcon管理员", "查询rcon管理员", "rcon管理员列表"),
    block=True,
)
async def list_rcon_admin(bot: Bot, ev: Event) -> None:
    tokens = split_cmd_args(ev.text)
    servers: Optional[List[MCQQServer]] = None
    if len(tokens) > 1:
        await bot.send("参数传递错误\n用法：mc查看rcon管理员 [服务器]")
        return
    if tokens:
        resolved, err = await resolve_servers(tokens[0])
        if err or not resolved:
            await bot.send(err or f"未找到服务器 {tokens[0]}")
            return
        servers = resolved

    if servers is not None:
        targets = servers
    elif ev.user_type == "group" and ev.group_id:
        resolved, err = await resolve_group_targets(ev.group_id, None)
        if err or not resolved:
            await bot.send(err or "当前群未绑定任何服务器")
            return
        targets = resolved
    else:
        targets = await MCQQServer.get_all_enabled()
        if not targets:
            await bot.send("当前未配置任何启用的 MC 服务器")
            return

    server_blocks = []
    for server in targets:
        server_display = server.display_name or server.server_name
        block_lines = [f"{server_display} 管理员名单："]
        admins = await MCQQRconWhitelist.get_by_server_name(server.server_name)
        if admins:
            for a in admins:
                user_name = await resolve_user_name(
                    bot.bot_id, a.user_id, ev.group_id or ""
                )
                if user_name:
                    block_lines.append(f" - {user_name} ({a.user_id})")
                else:
                    block_lines.append(f" - ({a.user_id})")
        else:
            block_lines.append(" - 无")
        server_blocks.append("\n".join(block_lines))

    await bot.send("\n\n".join(server_blocks))
