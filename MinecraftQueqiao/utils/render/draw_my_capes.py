from __future__ import annotations

import base64
import html as html_lib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import httpx
from gsuid_core.logger import logger

from .render import fill_template, render_html

if TYPE_CHECKING:
    from ...mc_capes.service import CapeItem

_RENDER_DIR = Path(__file__).parent
_HTML_TEMPLATE_PATH = _RENDER_DIR / "template" / "html" / "my_capes.html"
_TEXTURE2D_DIR = _RENDER_DIR / "texture2d"
_NO_CAPES_PNG = _TEXTURE2D_DIR / "no_capes.png"
_DEFAULT_AVATAR_PNG = _TEXTURE2D_DIR / "default_head.png"

_NO_CAPES_B64: str | None = None
_DEFAULT_AVATAR_B64: str | None = None

HTTP_HEADERS = {
    "User-Agent": "MCQueQiao/2.0 (draw-my-capes; +https://github.com)",
}
HTTP_TIMEOUT = 8.0


def _get_no_capes_data_uri() -> str:
    global _NO_CAPES_B64
    if _NO_CAPES_B64 is None:
        if _NO_CAPES_PNG.exists():
            data = _NO_CAPES_PNG.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            _NO_CAPES_B64 = f"data:image/png;base64,{b64}"
        else:
            _NO_CAPES_B64 = ""
    return _NO_CAPES_B64


def _get_default_avatar_data_uri() -> str:
    global _DEFAULT_AVATAR_B64
    if _DEFAULT_AVATAR_B64 is None:
        if _DEFAULT_AVATAR_PNG.exists():
            data = _DEFAULT_AVATAR_PNG.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            _DEFAULT_AVATAR_B64 = f"data:image/png;base64,{b64}"
        else:
            _DEFAULT_AVATAR_B64 = ""
    return _DEFAULT_AVATAR_B64


async def _fetch_avatar_bytes(player_name: str) -> bytes | None:
    if not player_name:
        return None
    url = f"https://mc-heads.net/avatar/{player_name}/256"
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content:
                return resp.content
    except Exception as e:
        logger.debug(f"[MCQueQiao] 拉取头像异常 {player_name}: {e}")
    return None


def _bytes_to_data_uri(data: bytes, mime_type: str = "image/png") -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def render_my_capes_html(
    player_name: str,
    capes: Sequence[Any],
    avatar_data_uri: str,
) -> str:
    """构建披风展示卡片的完整 HTML。"""
    template = _HTML_TEMPLATE_PATH.read_text(encoding="utf-8")
    display_player_name = html_lib.escape(player_name or "Steve")

    no_capes_uri = _get_no_capes_data_uri()
    has_active = any(bool(getattr(c, "is_active", False)) for c in capes)

    # 第一项固定为「无」
    items_html_parts: list[str] = []

    none_active_cls = " is-active" if not has_active else ""
    items_html_parts.append(
        f'<div class="cape-item{none_active_cls}">'
        f'  <div class="cape-img-box">'
        f'    <img class="cape-img" src="{no_capes_uri}" alt="无">'
        f"  </div>"
        f'  <div class="cape-name-cn">无</div>'
        f'  <div class="cape-name-en">None</div>'
        f"</div>"
    )

    for item in capes:
        raw_display = str(getattr(item, "display_name", "") or "").strip()
        raw_alias = str(getattr(item, "alias", "") or "").strip()
        is_active = bool(getattr(item, "is_active", False))
        active_cls = " is-active" if is_active else ""

        if raw_display and raw_display != raw_alias:
            # 拥有中文名：上方中文名，下方英文名
            cn_text = html_lib.escape(raw_display)
            en_text = html_lib.escape(raw_alias)
            name_blocks = f'<div class="cape-name-cn">{cn_text}</div>'
            if en_text:
                name_blocks += f'\n  <div class="cape-name-en">{en_text}</div>'
            alt_text = cn_text
        else:
            # 无中文名：在原中文名位置显示英文名，原英文名位置留空不显示
            primary_text = html_lib.escape(raw_alias or raw_display or "披风")
            name_blocks = f'<div class="cape-name-cn">{primary_text}</div>'
            alt_text = primary_text

        img_bytes = getattr(item, "image", None)
        if img_bytes and isinstance(img_bytes, bytes):
            img_uri = _bytes_to_data_uri(img_bytes)
        else:
            img_uri = no_capes_uri

        items_html_parts.append(
            f'<div class="cape-item{active_cls}">'
            f'  <div class="cape-img-box">'
            f'    <img class="cape-img" src="{img_uri}" alt="{alt_text}">'
            f"  </div>"
            f"  {name_blocks}"
            f"</div>"
        )

    total_items = len(items_html_parts)
    cols_count = min(max(total_items, 1), 5)

    replacements = {
        "player_name": display_player_name,
        "avatar_url": avatar_data_uri,
        "capes_grid_html": "\n".join(items_html_parts),
        "cols_count": str(cols_count),
    }

    return fill_template(template, replacements)


async def draw_my_capes(
    player_name: str,
    capes: Sequence[Any],
    avatar_bytes: bytes | None = None,
) -> bytes:
    """渲染「我的披风」图片，返回 PNG 图像字节。"""
    if avatar_bytes is None:
        avatar_bytes = await _fetch_avatar_bytes(player_name)

    if avatar_bytes:
        avatar_uri = _bytes_to_data_uri(avatar_bytes)
    else:
        avatar_uri = _get_default_avatar_data_uri()

    html_content = render_my_capes_html(
        player_name=player_name,
        capes=capes,
        avatar_data_uri=avatar_uri,
    )

    return await render_html(
        html_content,
        ".my-capes-card",
        viewport_width=1200,
        viewport_height=900,
        device_scale_factor=2.0,
    )
