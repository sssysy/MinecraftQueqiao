from typing import List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_config import mcqq_config
from ..mcqq_core import send_rcon_command
from ..mcqq_database import MCQQBind, MCQQServer, MCQQRconWhitelist
from ..utils.helpers.prefix_match import is_command_blacklisted
from ..utils.helpers.server_select import get_group_target_servers, resolve_servers
from ..utils.helpers.user_select import extract_all_target_users

sv_mcqq_rcon = SV("鹊桥 RCON 指令", pm=6)
sv_mcqq_rcon_admin = SV("鹊桥 RCON 管理员管理", pm=3)


async def _parse_rcon_admin_args(
    ev: Event,
) -> Tuple[Optional[List[MCQQServer]], List[str], Optional[str]]:
    """解析 RCON 管理员命令参数。
    返回 (servers, user_ids, error_msg)。
    servers 为 None 时表示未在命令中显式指定服务器（可由群绑定推断）。
    """
    raw_tokens = ev.text.strip().split()
    servers: Optional[List[MCQQServer]] = None
    user_tokens: List[str] = []
    at_users = extract_all_target_users(ev)

    if at_users:
        # 已通过 @用户 指定目标用户，此时 raw_tokens[0] 若存在必为服务器参数
        if raw_tokens:
            first_token = raw_tokens[0]
            resolved, err = await resolve_servers(first_token)
            if err:
                return None, [], err
            servers = resolved
            user_tokens = raw_tokens[1:]
    else:
        # 未通过 @用户 指定目标用户，需从 raw_tokens 中解析服务器和/或 QQ 号
        if raw_tokens:
            first_token = raw_tokens[0]
            clean_first = first_token.strip().lstrip("@")
            if not clean_first.isdigit():
                # 非纯数字必为服务器名称/外显名
                resolved, err = await resolve_servers(first_token)
                if err:
                    return None, [], err
                servers = resolved
                user_tokens = raw_tokens[1:]
            else:
                # 纯数字：可能是服务器 ID 或用户 QQ 号
                # 若只有一个 token，必须作为目标用户 QQ 号（由群绑定推断服务器）
                if len(raw_tokens) == 1:
                    user_tokens = raw_tokens
                else:
                    # 多个 token：优先尝试按服务器 ID 匹配
                    server = await MCQQServer.get_by_id(int(clean_first))
                    if server is not None:
                        servers = [server]
                        user_tokens = raw_tokens[1:]
                    else:
                        # 无法匹配为服务器 ID，则作为纯数字 QQ 号列表兜底
                        user_tokens = raw_tokens

    unique_user_ids = extract_all_target_users(ev, extra_tokens=user_tokens)
    return servers, unique_user_ids, None


@sv_mcqq_rcon.on_command("rcon")
async def rcon_command(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mcrcon <指令>")
        return

    text = ev.text.strip()
    if not text:
        await bot.send("用法：mcrcon <指令> 或 mcrcon [服务器] <指令>")
        return

    # 解析可选服务器选择器
    servers: Optional[List[MCQQServer]] = None
    command = text
    parts = text.split(maxsplit=1)
    if parts:
        resolved, _ = await resolve_servers(parts[0])
        if resolved is not None:
            servers = resolved
            command = parts[1].strip() if len(parts) > 1 else ""

    if not command:
        await bot.send("指令内容为空，请提供要执行的 Minecraft 指令")
        return

    # 指令黑名单检查
    blacklist = mcqq_config.get_config("command_blacklist").data
    if is_command_blacklisted(command, blacklist):
        await bot.send("黑名单指令，跳过传递")
        return

    targets = await get_group_target_servers(ev.group_id, servers)
    if not targets:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    results = []
    for server in targets:
        server_display = server.display_name or server.server_name

        # 权限检查：Bot超级管理员(user_pm <= 2) 或在 RCON 白名单中的用户
        is_auth = (ev.user_pm <= 2) or await MCQQRconWhitelist.is_whitelisted(
            server.server_name, ev.user_id
        )
        if not is_auth:
            results.append(f"[{server_display}] 权限不足：您没有该服务器的 RCON 执行权限")
            continue

        success, out = await send_rcon_command(server.server_name, command)
        if success:
            output_str = str(out).strip() if out else "(无输出)"
            results.append(f"[{server_display}] 执行成功:\n{output_str}")
        else:
            results.append(f"[{server_display}] {out}")

    await bot.send("\n\n".join(results))


@sv_mcqq_rcon_admin.on_command(("增加rcon管理员", "添加rcon管理员"))
async def add_rcon_admin(bot: Bot, ev: Event) -> None:
    servers, user_ids, err = await _parse_rcon_admin_args(ev)
    if err:
        await bot.send(err)
        return

    if not user_ids:
        await bot.send("未检测到目标用户，请提供 QQ 号或 @用户。\n用法：mc增加rcon管理员 [服务器] <QQ号/@用户>")
        return

    if servers is not None:
        targets = servers
    elif ev.user_type == "group" and ev.group_id:
        targets = await get_group_target_servers(ev.group_id, None)
        if not targets:
            await bot.send("当前群未绑定任何服务器，请指定服务器（例如：mc增加rcon管理员 生存服 @用户）或先执行 mc群服绑定")
            return
    else:
        await bot.send("私聊中请指定服务器（例如：mc增加rcon管理员 生存服 12345678）")
        return

    results = []
    for server in targets:
        server_display = server.display_name or server.server_name
        for uid in user_ids:
            existing = await MCQQRconWhitelist.get_by_server_and_user(
                server.server_name, uid
            )
            if existing:
                results.append(f"• 用户 {uid} 已在服务器 [{server_display}] 的 RCON 白名单中")
            else:
                await MCQQRconWhitelist.full_insert_data(
                    server_name=server.server_name,
                    user_id=uid,
                )
                logger.info(f"[MCQueQiao] 已将用户 {uid} 添加至服务器 '{server.server_name}' 的 RCON 白名单")
                results.append(f"• 已将用户 {uid} 添加至服务器 [{server_display}] 的 RCON 白名单")

    await bot.send("\n".join(results))


@sv_mcqq_rcon_admin.on_command(("删除rcon管理员", "移除rcon管理员"))
async def delete_rcon_admin(bot: Bot, ev: Event) -> None:
    servers, user_ids, err = await _parse_rcon_admin_args(ev)
    if err:
        await bot.send(err)
        return

    if not user_ids:
        await bot.send("未检测到目标用户，请提供 QQ 号或 @用户。\n用法：mc删除rcon管理员 [服务器] <QQ号/@用户>")
        return

    if servers is not None:
        targets = servers
    elif ev.user_type == "group" and ev.group_id:
        targets = await get_group_target_servers(ev.group_id, None)
        if not targets:
            await bot.send("当前群未绑定任何服务器，请指定服务器（例如：mc删除rcon管理员 生存服 @用户）或先执行 mc群服绑定")
            return
    else:
        await bot.send("私聊中请指定服务器（例如：mc删除rcon管理员 生存服 12345678）")
        return

    results = []
    for server in targets:
        server_display = server.display_name or server.server_name
        for uid in user_ids:
            existing = await MCQQRconWhitelist.get_by_server_and_user(
                server.server_name, uid
            )
            if not existing:
                results.append(f"• 用户 {uid} 不在服务器 [{server_display}] 的 RCON 白名单中")
            else:
                await MCQQRconWhitelist.delete_row(
                    server_name=server.server_name,
                    user_id=uid,
                )
                logger.info(f"[MCQueQiao] 已将用户 {uid} 从服务器 '{server.server_name}' 的 RCON 白名单中移除")
                results.append(f"• 已将用户 {uid} 从服务器 [{server_display}] 的 RCON 白名单中移除")

    await bot.send("\n".join(results))


@sv_mcqq_rcon_admin.on_command(("查看rcon管理员", "查询rcon管理员", "rcon管理员列表", "rcon白名单列表", "rcon白名单"))
async def list_rcon_admin(bot: Bot, ev: Event) -> None:
    text = ev.text.strip()
    servers: Optional[List[MCQQServer]] = None
    if text:
        resolved, err = await resolve_servers(text)
        if err:
            await bot.send(err)
            return
        servers = resolved

    if servers is not None:
        targets = servers
    elif ev.user_type == "group" and ev.group_id:
        targets = await get_group_target_servers(ev.group_id, None)
        if not targets:
            await bot.send("当前群未绑定任何服务器，请指定服务器（例如：mc查看rcon管理员 生存服）或先执行 mc群服绑定")
            return
    else:
        targets = await MCQQServer.get_all_enabled()
        if not targets:
            await bot.send("当前未配置任何启用的 MC 服务器")
            return

    lines = ["【RCON 管理员白名单】"]
    for server in targets:
        server_display = server.display_name or server.server_name
        admins = await MCQQRconWhitelist.get_by_server_name(server.server_name)
        if admins:
            admin_list_str = "\n".join(f"  - {a.user_id}" for a in admins)
            lines.append(f"• {server_display} ({server.server_name}):\n{admin_list_str}")
        else:
            lines.append(f"• {server_display} ({server.server_name}):\n  (暂无白名单管理员)")

    await bot.send("\n".join(lines))

