from typing import Any, Awaitable, Callable, List, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core.api import send_action_bar, send_broadcast, send_title
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.component import parse_text_or_json_component
from ..utils.helpers.server_resolve import resolve_group_targets, resolve_servers

sv_mcqq_broadcast = SV("鹊桥广播与公告指令", pm=3)


async def _resolve_push_args(
    bot: Bot, ev: Event, text: str, usage: str
) -> Optional[tuple[list, str]]:
    """[服务器] 正文。1 参=正文（主服务器）；2 参=服务器+正文；更多=参数错误。"""
    tokens = split_cmd_args(text)
    if not tokens:
        await bot.send(f"用法：mc{usage} [服务器] <内容>")
        return None

    if len(tokens) == 1:
        targets, err = await resolve_group_targets(ev.group_id or "", None)
        if err or not targets:
            await bot.send(err or "当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
            return None
        return targets, decode_arg(tokens[0])

    if len(tokens) == 2:
        servers, err = await resolve_servers(decode_arg(tokens[0]))
        if err or not servers:
            await bot.send(err or f"未找到服务器 {tokens[0]}")
            return None
        targets, err = await resolve_group_targets(ev.group_id or "", servers)
        if err or not targets:
            await bot.send(err or "当前群未绑定该服务器")
            return None
        return targets, decode_arg(tokens[1])

    await bot.send(
        f"参数传递错误，需要参数：可选服务器、内容（内容空格请用 \\+）\n"
        f"用法：mc{usage} [服务器] <内容>"
    )
    return None


async def _run_push(
    bot: Bot,
    ev: Event,
    *,
    usage: str,
    success_tip: str,
    build_payload: Callable[[str], Any],
    send: Callable[[str, Any], Awaitable[bool]],
) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send(f"请在群聊中使用 mc{usage} <内容>")
        return

    resolved = await _resolve_push_args(bot, ev, ev.text.strip(), usage)
    if resolved is None:
        return
    targets, content = resolved

    payload = build_payload(content)
    success_servers: List[str] = []
    fail_servers: List[str] = []
    for server in targets:
        server_display = server.display_name or server.server_name
        ok = await send(server.server_name, payload)
        if ok:
            success_servers.append(server_display)
        else:
            fail_servers.append(f"[{server_display}] 未连接或发送失败")

    results: List[str] = []
    if success_servers:
        formatted = "\n".join(f" - {s}" for s in success_servers)
        results.append(f"{success_tip}，涉及的服务器：\n{formatted}")
    results.extend(fail_servers)
    await bot.send("\n\n".join(results))


@sv_mcqq_broadcast.on_command("广播", block=True)
async def title_broadcast_command(bot: Bot, ev: Event) -> None:
    await _run_push(
        bot,
        ev,
        usage="广播",
        success_tip="广播完毕",
        build_payload=lambda c: parse_text_or_json_component(
            c, default_color="yellow", bold=True
        ),
        send=lambda name, payload: send_title(name, title=payload),
    )


@sv_mcqq_broadcast.on_command("公告", block=True)
async def chat_broadcast_command(bot: Bot, ev: Event) -> None:
    await _run_push(
        bot,
        ev,
        usage="公告",
        success_tip="公告完毕",
        build_payload=lambda c: parse_text_or_json_component(
            c, default_color="white", default_prefix="[公告] "
        ),
        send=lambda name, payload: send_broadcast(name, payload),
    )


@sv_mcqq_broadcast.on_command(("动作栏", "状态栏"), block=True)
async def actionbar_broadcast_command(bot: Bot, ev: Event) -> None:
    await _run_push(
        bot,
        ev,
        usage="动作栏",
        success_tip="消息发送成功",
        build_payload=lambda c: parse_text_or_json_component(
            c, default_color="aqua"
        ),
        send=lambda name, payload: send_action_bar(name, message=payload),
    )
