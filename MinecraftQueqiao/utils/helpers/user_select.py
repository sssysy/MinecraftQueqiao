from typing import List

from gsuid_core.models import Event


def extract_at_user_ids(ev: Event) -> List[str]:
    """从 Event 中提取所有被 @ 的用户 ID（去重且保序）"""
    users: List[str] = []
    if ev.at_list:
        for item in ev.at_list:
            uid = str(item).strip() if item else ""
            if uid and uid not in users:
                users.append(uid)
    elif ev.at and ev.at.strip():
        uid = ev.at.strip()
        if uid not in users:
            users.append(uid)
    return users
