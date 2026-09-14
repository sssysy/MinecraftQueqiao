"""服务器解析：ID / 内部名 / 外显名；群绑定目标服；可选选择器。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ...mcqq_database import MCQQBind, MCQQServer


async def resolve_servers(
    text: str,
) -> Tuple[Optional[List[MCQQServer]], Optional[str]]:
    """解析服务器选择文本。返回 (servers, err)。err 非空必须打断，不得静默回退。"""
    text = text.strip()
    if not text:
        return None, None

    if text.isdigit():
        server = await MCQQServer.get_by_id(int(text))
        if server is None:
            return None, f"未找到 ID 为 {text} 的服务器，请确认服务器ID"
        return [server], None

    server = await MCQQServer.get_by_name(text)
    if server is not None:
        return [server], None

    matches = await MCQQServer.get_by_display_name(text)
    if not matches:
        return None, f"未找到名称为 {text} 的服务器，请确认服务器名称后重试"
    if len(matches) > 1:
        ids = "/".join(str(s.id) for s in matches)
        return (
            None,
            f"有多个服务器的外显名均为 [{text}] （ID：{ids}），"
            f"请使用对应的服务器ID重新执行命令",
        )
    return [matches[0]], None


async def get_group_servers(
    group_id: str, *, only_enabled: bool = True
) -> List[MCQQServer]:
    binds = await MCQQBind.get_by_group_id(group_id)
    if not binds:
        return []
    servers: List[MCQQServer] = []
    seen: set[str] = set()
    for bind in binds:
        if bind.server_name in seen:
            continue
        server = await MCQQServer.get_by_name(bind.server_name)
        if server is None:
            continue
        if only_enabled and not server.enabled:
            continue
        seen.add(bind.server_name)
        servers.append(server)
    return servers


def filter_by_ids(
    servers: List[MCQQServer], selected: Optional[List[MCQQServer]]
) -> List[MCQQServer]:
    if selected is None:
        return list(servers)
    selected_ids = {s.id for s in selected}
    return [s for s in servers if s.id in selected_ids]


async def get_group_target_servers(
    group_id: str, servers: Optional[List[MCQQServer]] = None
) -> List[MCQQServer]:
    group_servers = await get_group_servers(group_id, only_enabled=True)
    return filter_by_ids(group_servers, servers)


async def parse_optional_servers(
    text: str,
) -> Tuple[Optional[List[MCQQServer]], str, Optional[str]]:
    """可选服务器选择器：首 token 可解析为服务器则吃掉。

    Returns:
        (servers|None, rest, err)
        servers 为 None 表示未指定服务器（走群绑定）。err 非空必须打断。
    """
    text = text.strip()
    if not text:
        return None, "", None

    parts = text.split(maxsplit=1)
    first, rest = parts[0], parts[1] if len(parts) > 1 else ""
    resolved, err = await resolve_servers(first)
    if err:
        return None, text, err
    if resolved:
        return resolved, rest.strip(), None
    return None, text, None
