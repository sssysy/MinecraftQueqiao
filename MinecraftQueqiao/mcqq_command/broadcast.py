from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core import send_action_bar, send_broadcast, send_title
from ..mcqq_database import MCQQServer
from ..utils.helpers.component import parse_text_or_json_component
from ..utils.helpers.server_select import get_group_target_servers, resolve_servers

sv_mcqq_broadcast = SV("鹊桥广播与公告指令", pm=3)



@sv_mcqq_broadcast.on_command("广播")
async def title_broadcast_command(bot: Bot, ev: Event) -> None:
    """mc广播: 走鹊桥 send_title (屏幕大标题)"""
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mc广播 <内容> 指令")
        return

    text = ev.text.strip()
    if not text:
        await bot.send("用法：mc广播 <广播内容> 或 mc广播 [服务器] <广播内容>")
        return

    servers: Optional[List[MCQQServer]] = None
    parts = text.split(maxsplit=1)
    if parts:
        resolved, _ = await resolve_servers(parts[0])
        if resolved is not None:
            servers = resolved
            content = parts[1].strip() if len(parts) > 1 else ""
        else:
            content = text
    else:
        content = text

    if not content:
        await bot.send("广播内容为空，请提供要广播的文本")
        return

    targets = await get_group_target_servers(ev.group_id, servers)
    if not targets:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    title_payload = parse_text_or_json_component(
        content, default_color="yellow", bold=True
    )

    success_servers = []
    fail_servers = []

    for server in targets:
        server_display = server.display_name or server.server_name
        ok = await send_title(server.server_name, title=title_payload)
        if ok:
            success_servers.append(server_display)
        else:
            fail_servers.append(f"[{server_display}] 未连接或发送失败")

    results = []
    if success_servers:
        results.append(f"屏幕大标题广播成功！涉及的服务器：\n" + ", ".join(success_servers))
    if fail_servers:
        results.extend(fail_servers)

    await bot.send("\n\n".join(results))


@sv_mcqq_broadcast.on_command("公告")
async def chat_broadcast_command(bot: Bot, ev: Event) -> None:
    """mc公告: 走鹊桥 broadcast (聊天栏广播)"""
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mc公告 <内容> 指令")
        return

    text = ev.text.strip()
    if not text:
        await bot.send("用法：mc公告 <公告内容> 或 mc公告 [服务器] <公告内容>")
        return

    servers: Optional[List[MCQQServer]] = None
    parts = text.split(maxsplit=1)
    if parts:
        resolved, _ = await resolve_servers(parts[0])
        if resolved is not None:
            servers = resolved
            content = parts[1].strip() if len(parts) > 1 else ""
        else:
            content = text
    else:
        content = text

    if not content:
        await bot.send("公告内容为空，请提供要发布的公告文本")
        return

    targets = await get_group_target_servers(ev.group_id, servers)
    if not targets:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    formatted_msg = parse_text_or_json_component(
        content, default_color="white", default_prefix="[公告] "
    )

    success_servers = []
    fail_servers = []

    for server in targets:
        server_display = server.display_name or server.server_name
        ok = await send_broadcast(server.server_name, formatted_msg)
        if ok:
            success_servers.append(server_display)
        else:
            fail_servers.append(f"[{server_display}] 未连接或发送失败")

    results = []
    if success_servers:
        results.append(f"聊天栏公告发布成功！涉及的服务器：\n" + ", ".join(success_servers))
    if fail_servers:
        results.extend(fail_servers)

    await bot.send("\n\n".join(results))


@sv_mcqq_broadcast.on_command(("动作栏", "actionbar", "状态栏"))
async def actionbar_broadcast_command(bot: Bot, ev: Event) -> None:
    """mc动作栏: 走鹊桥 send_actionbar (动作栏消息)"""
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mc动作栏 <内容> 指令")
        return

    text = ev.text.strip()
    if not text:
        await bot.send("用法：mc动作栏 <内容> 或 mc动作栏 [服务器] <内容>")
        return

    servers: Optional[List[MCQQServer]] = None
    parts = text.split(maxsplit=1)
    if parts:
        resolved, _ = await resolve_servers(parts[0])
        if resolved is not None:
            servers = resolved
            content = parts[1].strip() if len(parts) > 1 else ""
        else:
            content = text
    else:
        content = text

    if not content:
        await bot.send("动作栏内容为空，请提供要展示的文本")
        return

    targets = await get_group_target_servers(ev.group_id, servers)
    if not targets:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    actionbar_payload = parse_text_or_json_component(
        content, default_color="aqua"
    )

    success_servers = []
    fail_servers = []

    for server in targets:
        server_display = server.display_name or server.server_name
        ok = await send_action_bar(server.server_name, message=actionbar_payload)
        if ok:
            success_servers.append(server_display)
        else:
            fail_servers.append(f"[{server_display}] 未连接或发送失败")

    results = []
    if success_servers:
        results.append(f"动作栏消息发送成功！涉及的服务器：\n" + ", ".join(success_servers))
    if fail_servers:
        results.extend(fail_servers)

    await bot.send("\n\n".join(results))
