import json
from typing import Any, Dict, List, Optional, Union


def parse_text_or_json_component(
    content: str,
    default_color: str = "white",
    default_prefix: Optional[str] = None,
    bold: bool = False,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """智能解析普通文本或 Minecraft Raw JSON 文本组件。

    如果 content 是合法的 Minecraft JSON 组件结构（以 { 或 [ 开头的 dict 或 list），
    则反序列化直接返回；否则包装为标准 Minecraft 文本组件结构。

    Args:
        content: 用户输入的文本或 JSON 字符串
        default_color: 普通纯文本时的默认颜色（如 'white', 'aqua', 'yellow', 'gold' 等）
        default_prefix: 可选的前缀标签（如 '[公告] ', '[定时公告] ' 等）
        bold: 是否默认加粗

    Returns:
        dict 或 list[dict]
    """
    stripped = str(content).strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass

    # 普通纯文本处理
    components: List[Dict[str, Any]] = []
    if default_prefix:
        components.append({"text": default_prefix, "color": "gold", "bold": True})

    text_comp: Dict[str, Any] = {"text": str(content), "color": default_color}
    if bold:
        text_comp["bold"] = True
    components.append(text_comp)

    return components
