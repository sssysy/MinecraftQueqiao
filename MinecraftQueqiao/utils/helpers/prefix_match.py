import re
from gsuid_core.logger import logger


def match_and_trim_prefix(text: str, prefixes: list[str] | str) -> tuple[bool, str]:
    """检查文本是否匹配白名单前缀或正则规则，并按规则决定是否去除前缀。

    规则：
    - 若 prefixes 为空列表或未配置任何非空规则，直接放行 (True, text)。
    - 若规则以 'r:' 开头，视作正则表达式匹配（re.search）。匹配成功时不去除前缀，保留原文本 (True, text)。
    - 若规则为普通字符串，视作前缀匹配。匹配成功后去除该前缀 (True, trimmed_text)。
    - 若列表中多条规则均未匹配，返回 (False, text)。
    """
    if isinstance(prefixes, str):
        prefixes = [prefixes] if prefixes else []

    patterns = [p for p in prefixes if p]
    if not patterns:
        return True, text

    for p in patterns:
        if p.startswith("r:"):
            pattern = p[2:]
            try:
                if re.search(pattern, text):
                    return True, text
            except re.error as e:
                logger.warning(f"[MCQueQiao] 正则表达式 '{pattern}' 语法错误: {e}")
        else:
            stripped = text.lstrip()
            if stripped.startswith(p):
                return True, stripped[len(p) :].lstrip()
            elif text.startswith(p):
                return True, text[len(p) :].lstrip()

    return False, text


def is_blacklisted(text: str, blacklist: list[str] | str) -> bool:
    """检查文本是否命中黑名单规则（普通前缀或以 'r:' 开头的正则表达式）。

    规则：
    - 若 blacklist 为空列表或无有效规则，返回 False。
    - 若规则以 'r:' 开头，视作正则表达式匹配（re.search），命中返回 True。
    - 若规则为普通字符串，视作前缀匹配（.startswith），命中返回 True。
    - 均未命中返回 False。
    """
    if isinstance(blacklist, str):
        blacklist = [blacklist] if blacklist else []

    patterns = [p for p in blacklist if p]
    if not patterns:
        return False

    for p in patterns:
        if p.startswith("r:"):
            pattern = p[2:]
            try:
                if re.search(pattern, text):
                    return True
            except re.error as e:
                logger.warning(f"[MCQueQiao] 黑名单正则表达式 '{pattern}' 语法错误: {e}")
        else:
            stripped = text.lstrip()
            if stripped.startswith(p) or text.startswith(p):
                return True

    return False
