"""文本 / JSON → Minecraft 文本组件；可点击组件工厂。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union


def parse_text_or_json_component(
    content: str,
    default_color: str = "white",
    default_prefix: Optional[str] = None,
    bold: bool = False,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    stripped = str(content).strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass

    components: List[Dict[str, Any]] = []
    if default_prefix:
        components.append({"text": default_prefix, "color": "gold", "bold": True})

    text_comp: Dict[str, Any] = {"text": str(content), "color": default_color}
    if bold:
        text_comp["bold"] = True
    components.append(text_comp)
    return components


def clickable_text(
    text: str,
    url: str,
    hover: str,
    *,
    color: str = "white",
) -> Dict[str, Any]:
    """可点击文本组件。同时写 camelCase 与 snake_case，兼容 MC 1.20.4 与 1.20.5+。"""
    return {
        "text": text,
        "color": color,
        "underlined": True,
        "clickEvent": {
            "action": "open_url",
            "value": url,
        },
        "click_event": {
            "action": "open_url",
            "url": url,
            "value": url,
        },
        "hoverEvent": {
            "action": "show_text",
            "value": hover,
            "contents": hover,
        },
        "hover_event": {
            "action": "show_text",
            "value": hover,
            "contents": hover,
        },
    }


def chat_image_code(url: str) -> Dict[str, Any]:
    return {"text": f"[[CICode,url={url},name=图片]]", "color": "white"}
