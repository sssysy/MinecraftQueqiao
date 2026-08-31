import re

# Minecraft 格式码: § 或 \u00a7 后跟 0-9/a-f(颜色)或 k-o(样式)/r(重置)
_FORMAT_CODE_RE = re.compile(r"[§\u00a7][0-9a-fk-or]", re.IGNORECASE)


def strip_minecraft_formatting_codes(text: str) -> str:
    """移除 Minecraft 格式码(§ 或 \\u00a7 加单字符)，返回纯文本。"""
    if not text:
        return ""
    return _FORMAT_CODE_RE.sub("", str(text))

