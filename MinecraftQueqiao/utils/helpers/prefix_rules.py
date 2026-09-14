"""白/黑/假人/指令黑名单规则匹配（r: 前缀表示正则）。"""

from __future__ import annotations

import re
from typing import List

from gsuid_core.logger import logger


def iter_rules(rules: list[str] | str | None) -> List[str]:
    if rules is None:
        return []
    if isinstance(rules, str):
        rules = [rules] if rules else []
    return [p.strip() for p in rules if p and str(p).strip()]


def has_rules(rules: list[str] | str | None) -> bool:
    return bool(iter_rules(rules))


def _match_regex(pattern: str, text: str) -> bool:
    try:
        return re.search(pattern, text) is not None
    except re.error as e:
        logger.warning(f"[MCQueQiao] 正则表达式 '{pattern}' 语法错误: {e}")
        return False


def match_and_trim_prefix(
    text: str, prefixes: list[str] | str
) -> tuple[bool, str]:
    """白名单：空前缀列表直接放行；r: 正则命中保留原文；普通前缀命中则去掉前缀。"""
    patterns = iter_rules(prefixes)
    if not patterns:
        return True, text

    stripped = text.lstrip()
    for p in patterns:
        if p.startswith("r:"):
            if _match_regex(p[2:], text):
                return True, text
        else:
            if stripped.startswith(p):
                return True, stripped[len(p) :].lstrip()
            if text.startswith(p):
                return True, text[len(p) :].lstrip()
    return False, text


def is_blacklisted(text: str, blacklist: list[str] | str) -> bool:
    patterns = iter_rules(blacklist)
    if not patterns:
        return False
    stripped = text.lstrip()
    for p in patterns:
        if p.startswith("r:"):
            if _match_regex(p[2:], text):
                return True
        elif stripped.startswith(p) or text.startswith(p):
            return True
    return False


def is_fake_player(player_name: str, filter_list: list[str] | str) -> bool:
    if not player_name or player_name == "Unknown":
        return False
    patterns = iter_rules(filter_list)
    if not patterns:
        return False
    target = player_name.strip()
    for p in patterns:
        if p.startswith("r:"):
            if _match_regex(p[2:], target):
                return True
        elif target == p:
            return True
    return False


def is_command_blacklisted(command: str, blacklist: list[str] | str) -> bool:
    if not command:
        return False
    patterns = iter_rules(blacklist)
    if not patterns:
        return False

    cmd_raw = command.strip()
    cmd_no_slash = cmd_raw.lstrip("/")
    cmd_raw_lower = cmd_raw.lower()
    cmd_lower = cmd_no_slash.lower()

    for p in patterns:
        if p.startswith("r:"):
            pattern = p[2:]
            try:
                if re.search(pattern, cmd_raw, re.IGNORECASE) or re.search(
                    pattern, cmd_no_slash, re.IGNORECASE
                ):
                    return True
            except re.error as e:
                logger.warning(
                    f"[MCQueQiao] 指令黑名单正则 '{pattern}' 语法错误: {e}"
                )
        else:
            p_clean = p.lstrip("/").lower()
            p_raw = p.lower()
            if (
                cmd_lower.startswith(p_clean)
                or cmd_raw_lower.startswith(p_raw)
                or cmd_raw_lower.startswith("/" + p_clean)
            ):
                return True
    return False
