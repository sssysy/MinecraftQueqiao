"""统一指令参数解析：空格分参，参数内空格用 \\+ 表示。"""

from __future__ import annotations

from typing import List, Optional, Tuple

SPACE_ESCAPE = "\\+"


def decode_arg(token: str) -> str:
    """`a\\+b` → `a b`。"""
    return token.replace(SPACE_ESCAPE, " ")


def split_cmd_args(text: str) -> List[str]:
    """按空白切分；不折叠 \\+，只做切分。空文本返回 []。"""
    text = text.strip()
    if not text:
        return []
    return text.split()


def parse_positional(
    text: str,
    *,
    min_args: int = 0,
    max_args: Optional[int] = None,
    names: Optional[Tuple[str, ...]] = None,
) -> Tuple[Optional[List[str]], Optional[str]]:
    """按位置解析参数。

    Returns:
        (args, err)
        args 为 decode 后的参数列表；err 为「参数传递错误」文案。
    """
    tokens = split_cmd_args(text)
    n = len(tokens)
    if n < min_args:
        expect = _format_expect(min_args, max_args, names)
        return None, f"参数传递错误，{expect}"
    if max_args is not None and n > max_args:
        expect = _format_expect(min_args, max_args, names)
        return None, f"参数传递错误，{expect}"
    return [decode_arg(t) for t in tokens], None


def _format_expect(
    min_args: int, max_args: Optional[int], names: Optional[Tuple[str, ...]]
) -> str:
    if names:
        if max_args is None or max_args == min_args:
            return f"需要参数：{'、'.join(names)}"
        optional = names[min_args:max_args] if max_args else names[min_args:]
        return (
            f"需要参数：{'、'.join(names[:min_args])}"
            + (f"，可选：{'、'.join(optional)}" if optional else "")
        )
    if max_args is None:
        return f"至少 {min_args} 个参数"
    if min_args == max_args:
        return f"需要 {min_args} 个参数"
    return f"需要 {min_args}~{max_args} 个参数"


def split_user_ids(token: str) -> List[str]:
    """按中英文逗号拆用户 ID。"""
    parts: List[str] = []
    for raw in token.replace("，", ",").split(","):
        item = raw.strip().lstrip("@")
        if item:
            parts.append(item)
    return parts
