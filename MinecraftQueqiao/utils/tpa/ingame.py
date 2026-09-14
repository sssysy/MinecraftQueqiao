"""游戏内 TPA 触发器。前缀来自配置 ingame_prefix。"""

from __future__ import annotations

from ..helpers.arg_parse import parse_positional
from ..helpers.ingame_cmd import ingame
from ...mcqq_core.events import register_ingame_handler
from . import service

_ACCEPT_WORDS = frozenset({"accept", "同意", "yes", "y"})
_DENY_WORDS = frozenset({"deny", "拒绝", "no", "n"})


@ingame.on_command("tpa")
async def _tpa(server_name: str, player_name: str, args: str) -> None:
    raw = (args or "").strip()
    if not raw:
        await service.tellraw(
            server_name,
            player_name,
            f"参数传递错误\n{service.tpa_usage()}",
            "yellow",
        )
        return

    tokens, err = parse_positional(raw, min_args=1, max_args=1, names=("目标/同意/拒绝",))
    if err:
        await service.tellraw(
            server_name,
            player_name,
            f"{err}\n{service.tpa_usage()}",
            "yellow",
        )
        return

    action = tokens[0]
    action_key = action.lower()

    if action_key in _ACCEPT_WORDS:
        ok, msg = await service.accept_tp(server_name, player_name)
        await service.tellraw(
            server_name, player_name, msg, "green" if ok else "yellow"
        )
        return

    if action_key in _DENY_WORDS:
        result = await service.deny_tp(server_name, player_name)
        await service.tellraw(
            server_name,
            player_name,
            result.to_target,
            "green" if result.ok else "yellow",
        )
        if result.ok and result.requester and result.to_requester:
            await service.tellraw(
                server_name,
                result.requester,
                result.to_requester,
                "red",
            )
        return

    ok, msg = await service.request_tp(server_name, player_name, action)
    await service.tellraw(
        server_name, player_name, msg, "green" if ok else "yellow"
    )


async def _dispatch(server_name: str, player_name: str, raw: str) -> bool:
    return await ingame.dispatch(server_name, player_name, raw)


register_ingame_handler(_dispatch)
