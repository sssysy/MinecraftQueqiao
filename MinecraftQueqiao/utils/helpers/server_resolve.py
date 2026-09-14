"""服务器解析：ID / 内部名 / 外显名；群绑定目标服；可选选择器。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ...mcqq_database import MCQQBind, MCQQServer


async def resolve_servers(
    text: str,
) -> Tuple[Optional[List[MCQQServer]], Optional[str]]:
    """解析服务器选择文本。返回 (servers, err)。

    - 命中唯一服务器 → ([server], None)
    - 外显名歧义 → (None, err) 必须打断
    - 未找到 / 非法 ID → (None, err)，由调用方决定是否当错误
    """
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
    seen: set[int] = set()
    for bind in binds:
        server = None
        if bind.server_id:
            server = await MCQQServer.get_by_id(bind.server_id)
        if server is None and bind.server_name:
            server = await MCQQServer.get_by_name(bind.server_name)
        if server is None:
            continue
        if server.id in seen:
            continue
        if only_enabled and not server.enabled:
            continue
        seen.add(server.id)
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
