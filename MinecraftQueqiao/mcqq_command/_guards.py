"""命令层共享前置检查。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..mcqq_database import MCQQServer
from ..utils.helpers.server_resolve import (
    get_group_target_servers,
    parse_optional_servers,
)


async def send_not_group(bot: Bot, usage_hint: str) -> None:
    await bot.send(f"请在群聊中使用 {usage_hint}")


async def resolve_targets_with_optional_selector(
    bot: Bot,
    ev: Event,
    text: str,
) -> Optional[Tuple[List[MCQQServer], str]]:
    """解析可选服务器选择器 + 群绑定目标服。

    Returns:
        (targets, content) 或 None（错误已发送）
    """
    servers, rest, err = await parse_optional_servers(text)
    if err:
        await bot.send(err)
        return None

    content = rest if servers is not None else text
    targets = await get_group_target_servers(ev.group_id or "", servers)
    if not targets:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return None
    return targets, content.strip()
