"""游戏内指令注册与匹配。前缀读配置 ingame_prefix，不写死 mc。"""

from __future__ import annotations

from typing import Awaitable, Callable, List, Tuple

from gsuid_core.logger import logger

from ..mcqq_config import mcqq_config

IngameHandler = Callable[[str, str, str], Awaitable[None]]


def read_ingame_prefix() -> str:
    raw = mcqq_config.get_config("ingame_prefix").data
    prefix = str(raw).strip() if raw is not None else ""
    return prefix or "mc"


class IngameCommands:
    def __init__(self) -> None:
        self._rules: List[Tuple[str, IngameHandler, bool]] = []

    def on_command(
        self, *names: str, need_admin: bool = False
    ) -> Callable[[IngameHandler], IngameHandler]:
        def deco(fn: IngameHandler) -> IngameHandler:
            for name in names:
                self._rules.append((name, fn, need_admin))
            return fn

        return deco

    async def dispatch(self, server_name: str, player_name: str, raw: str) -> bool:
        if not player_name or not raw:
            return False
        if not mcqq_config.get_config("tp_enabled").data:
            return False

        prefix = read_ingame_prefix()
        msg = raw.strip()
        if msg.startswith("/"):
            msg = msg[1:].strip()

        # 最长指令名优先，避免 tp 吃掉 tp列表
        for name, fn, need_admin in sorted(
            self._rules, key=lambda item: -len(item[0])
        ):
            tokens = (f"{prefix}{name}", f"{prefix} {name}")
            args: str | None = None
            for token in tokens:
                if msg == token:
                    args = ""
                    break
                if msg.startswith(token + " "):
                    args = msg[len(token) :].strip()
                    break
            if args is None:
                continue

            if need_admin:
                from .admin import is_admin

                if not await is_admin(server_name, player_name=player_name):
                    from ..waypoint.service import tellraw

                    await tellraw(
                        server_name,
                        player_name,
                        "您没有该指令的权限",
                        "red",
                    )
                    return True

            try:
                await fn(server_name, player_name, args)
            except Exception as e:
                logger.error(
                    f"[MC·游戏内指令] [{server_name}] '{name}' 执行异常: {e}"
                )
            return True

        return False


ingame = IngameCommands()
