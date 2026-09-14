"""服务器解析：ID / 内部名 / 外显名；群绑定目标服；主服务器默认。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ...mcqq_database import MCQQBind, MCQQServer

ERR_NO_BIND = "当前群未绑定任何服务器，请先使用 mc群服绑定 <服务器>"
ERR_NO_MAIN = (
    "当前群绑定异常，无法找到主服务器，"
    "请使用 mc切换主服务器 <服务器> 进行设置"
)
ERR_MULTI_MAIN = (
    "当前群绑定异常，检测到多个主服务器，"
    "请使用 mc切换主服务器 <服务器> 修正"
)
ERR_NOT_BOUND = "当前群未绑定该服务器"


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


async def _load_bind_server(bind: MCQQBind) -> Optional[MCQQServer]:
    server = None
    if bind.server_id:
        server = await MCQQServer.get_by_id(bind.server_id)
    if server is None and bind.server_name:
        server = await MCQQServer.get_by_name(bind.server_name)
    return server


async def get_group_main_server(
    group_id: str,
) -> Tuple[Optional[MCQQServer], Optional[str]]:
    """取该群唯一主服务器。返回 (server, err)。"""
    binds = await MCQQBind.get_by_group_id(group_id)
    if not binds:
        return None, ERR_NO_BIND

    mains = [b for b in binds if b.is_main]
    if len(mains) == 0:
        return None, ERR_NO_MAIN
    if len(mains) > 1:
        return None, ERR_MULTI_MAIN

    server = await _load_bind_server(mains[0])
    if server is None or not server.enabled:
        return None, ERR_NO_MAIN
    return server, None


async def resolve_group_targets(
    group_id: str,
    selected: Optional[List[MCQQServer]] = None,
) -> Tuple[Optional[List[MCQQServer]], Optional[str]]:
    """命令层统一入口。返回 (servers, err)。

    - selected 非空：与群绑定求交集后返回
    - selected 为空：取该群主服务器（绝不取全部绑定或随便一台）
    """
    if selected:
        group_servers = await get_group_servers(group_id, only_enabled=True)
        selected_ids = {s.id for s in selected}
        targets = [s for s in group_servers if s.id in selected_ids]
        if not targets:
            return None, ERR_NOT_BOUND
        return targets, None

    server, err = await get_group_main_server(group_id)
    if err or server is None:
        return None, err or ERR_NO_MAIN
    return [server], None
