from typing import List, Optional, Tuple

from ...mcqq_database import MCQQBind, MCQQServer



async def get_group_target_servers(
    group_id: str, servers: Optional[List[MCQQServer]] = None
) -> List[MCQQServer]:
    """按群绑定 + 可选选择器筛选目标服务器。servers 为 None 表示当前群绑定的全部服务器。"""
    binds = await MCQQBind.get_by_group_id(group_id)
    if not binds:
        return []
    selected_ids = {s.id for s in servers} if servers is not None else None
    targets: List[MCQQServer] = []
    for bind in binds:
        server = await MCQQServer.get_by_name(bind.server_name)
        if server is None:
            continue
        if selected_ids is not None and server.id not in selected_ids:
            continue
        targets.append(server)
    return targets



async def resolve_servers(
    text: str,
) -> Tuple[Optional[List[MCQQServer]], Optional[str]]:
    """解析用户输入的服务器选择文本。
    服务器ID -> 内部名 -> 外显名
    """
    text = text.strip()
    if not text:
        return None, None

    # 1. 数字：按 ID 精确匹配
    if text.isdigit():
        server = await MCQQServer.get_by_id(int(text))
        if server is None:
            return None, (
                f"未找到 ID 为 {text} 的服务器，"
                f"请先在网页控制台确认服务器ID"
            )
        return [server], None

    # 2. 内部名优先：命中即返回
    server = await MCQQServer.get_by_name(text)
    if server is not None:
        return [server], None

    # 3. 外显名：可能重复，需检查歧义
    matches = await MCQQServer.get_by_display_name(text)
    if not matches:
        return None, f"未找到名称为 [{text}] 的服务器，请使用服务器ID重试"
    if len(matches) > 1:
        ids = "/".join(str(s.id) for s in matches)
        return (
            None,
            f"有多个服务器的外显名均为 [{text}] （ID：{ids}），"
            f"请使用对应的服务器ID重新执行命令",
        )
    return [matches[0]], None