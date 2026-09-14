from typing import Any, Awaitable, Callable, List

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core.api import send_action_bar, send_broadcast, send_title
from ..utils.helpers.component import parse_text_or_json_component
from ._guards import resolve_targets_with_optional_selector, send_not_group

sv_mcqq_broadcast = SV("鹊桥广播与公告指令", pm=3)


async def _run_push(
    bot: Bot,
    ev: Event,
    *,
    usage: str,
    empty_tip: str,
    success_tip: str,
    build_payload: Callable[[str], Any],
    send: Callable[[str, Any], Awaitable[bool]],
) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await send_not_group(bot, f"mc{usage} <内容>")
        return

    text = ev.text.strip()
    if not text:
        await bot.send(f"用法：mc{usage} <内容>")
        return

    resolved = await resolve_targets_with_optional_selector(bot, ev, text)
    if resolved is None:
        return
    targets, content = resolved
    if not content:
        await bot.send(empty_tip)
        return

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
        empty_tip="广播内容为空，请提供要广播的文本",
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
        empty_tip="公告内容为空，请提供要发布的公告文本",
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
        empty_tip="动作栏内容为空，请提供要展示的文本",
        success_tip="消息发送成功",
        build_payload=lambda c: parse_text_or_json_component(
            c, default_color="aqua"
        ),
        send=lambda name, payload: send_action_bar(name, message=payload),
    )
