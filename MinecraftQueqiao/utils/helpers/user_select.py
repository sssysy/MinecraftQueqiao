from typing import List, Optional, Tuple

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


def extract_single_target_user(
    ev: Event,
    default_to_sender: bool = True,
) -> Tuple[Optional[str], str, bool]:
    """提取单个目标用户 ID 与剩余文本。

    优先提取 @用户；若无 @，则检查文本首个 token 是否为纯数字 QQ 号（支持前导 @）。

    Returns:
        (target_user_id, remaining_text, is_for_other)
        - target_user_id: 目标用户 ID（可能为被 @ 成员、指定 QQ 号或发送者自身）
        - remaining_text: 除去目标标识后的剩余文本
        - is_for_other: 是否为针对他人的操作
    """
    raw_text = ev.text.strip()
    at_users = extract_at_user_ids(ev)
    if at_users:
        return at_users[0], raw_text, True

    tokens = raw_text.split(maxsplit=1)
    if tokens:
        first = tokens[0].strip().lstrip("@")
        if first.isdigit():
            remaining = tokens[1].strip() if len(tokens) > 1 else ""
            return first, remaining, True

    if default_to_sender:
        return ev.user_id, raw_text, False
    return None, raw_text, False


def extract_all_target_users(
    ev: Event,
    extra_tokens: Optional[List[str]] = None,
) -> List[str]:
    """提取命令中包含的所有目标用户 ID（@用户 + 纯数字 QQ 号参数，去重且保序）"""
    user_ids = extract_at_user_ids(ev)
    if extra_tokens:
        for tok in extra_tokens:
            tok_clean = tok.strip().lstrip("@")
            if tok_clean.isdigit() and tok_clean not in user_ids:
                user_ids.append(tok_clean)
    return user_ids
