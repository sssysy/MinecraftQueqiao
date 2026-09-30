"""「我的披风」卡片 PIL 渲染。"""

from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

_RENDER_DIR = Path(__file__).parent
_FONT_PATH = _RENDER_DIR.parent / "fonts" / "mc-unicode-font.otf"
_TEXTURE2D_DIR = _RENDER_DIR / "texture2d"
_NO_CAPES_PNG = _TEXTURE2D_DIR / "no_capes.png"
_DEFAULT_AVATAR_PNG = _TEXTURE2D_DIR / "default_head.png"
_MCLOGO_PNG = _TEXTURE2D_DIR / "mclogo.png"

SCALE = 2
CARD_W = 560 * SCALE
BORDER = 2 * SCALE

BG_CARD = (20, 20, 20)
BG_BAR = (13, 13, 13)
BG_FOOTER = (16, 16, 16)
BORDER_CARD = (44, 44, 44)
GREEN_LINE = (60, 133, 39)
BORDER_FOOTER = (42, 42, 42)
C_WHITE = (255, 255, 255)
C_GRAY = (176, 176, 176)
C_EN = (136, 136, 136)
C_FOOTER = (119, 119, 119)
C_ACTIVE_CN = (143, 212, 122)
C_ACTIVE_EN = (106, 170, 92)
C_NONE_TEXT = (176, 176, 176)

FS_NAME = 22 * SCALE
FS_SUB = 12 * SCALE
FS_NONE = 18 * SCALE
FS_CN = 13 * SCALE
FS_EN = 10 * SCALE
FS_FOOTER = 10 * SCALE

NAME_LS = 1 * SCALE
NAME_MAX_W = 160 * SCALE
BOLD_STROKE = 1.5

PROF_PAD_X = 18 * SCALE
PROF_PAD_Y = 16 * SCALE
AVATAR = 64 * SCALE
GAP_PROFILE = 12 * SCALE
LOGO_H = 28 * SCALE
GREEN_H = 3 * SCALE
WRAP_PAD_T = 18 * SCALE
WRAP_PAD_X = 14 * SCALE
WRAP_PAD_B = 8 * SCALE
GRID_GAP_R = 18 * SCALE
GRID_GAP_C = 10 * SCALE
CAPE_W, CAPE_H = 80 * SCALE, 128 * SCALE
CN_MT = 8 * SCALE
EN_MT = 3 * SCALE
FOOTER_MT = 10 * SCALE
FOOTER_BORDER = 2 * SCALE
FOOTER_PAD_Y = 10 * SCALE
FOOTER_PAD_X = 12 * SCALE

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(str(_FONT_PATH), size=size)
    return _font_cache[size]


def _tw(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    if not text:
        return 0
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def _th(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    if not text:
        return 0
    b = draw.textbbox((0, 0), text, font=font)
    return b[3] - b[1]


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, ...],
    *,
    ls: int = 0,
    bold: bool = False,
) -> int:
    x, y = xy
    stroke = BOLD_STROKE if bold else 0
    stroke_fill = fill if bold else None
    if ls == 0:
        draw.text(
            (x, y),
            text,
            font=font,
            fill=fill,
            stroke_width=stroke,
            stroke_fill=stroke_fill,
        )
        return _tw(draw, text, font)
    cx = x
    for ch in text:
        draw.text(
            (cx, y),
            ch,
            font=font,
            fill=fill,
            stroke_width=stroke,
            stroke_fill=stroke_fill,
        )
        cx += _tw(draw, ch, font) + ls
    return cx - x - (ls if text else 0)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_w: int,
) -> List[str]:
    if not text:
        return []
    lines: List[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if _tw(draw, trial, font) <= max_w:
            current = trial
            continue
        if not current:
            lines.append(ch)
            continue
        if " " in current:
            idx = current.rfind(" ")
            lines.append(current[:idx])
            current = current[idx + 1 :] + ch
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def _process_cape_image(img_bytes: bytes) -> Image.Image:
    """提取披风背面图案并标准化为 80x128 像素风。"""
    im = Image.open(BytesIO(img_bytes)).convert("RGBA")
    w, h = im.size
    if w > h:
        scale = w / 64.0
        cropped = im.crop(
            (
                int(round(1 * scale)),
                int(round(1 * scale)),
                int(round(11 * scale)),
                int(round(17 * scale)),
            )
        )
        return cropped.resize((CAPE_W, CAPE_H), Image.NEAREST)
    return im.resize((CAPE_W, CAPE_H), Image.NEAREST)


def _load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def draw_my_capes_pil(
    player_name: str,
    capes: Sequence[object],
    avatar_bytes: Optional[bytes] = None,
) -> bytes:
    """绘制「我的披风」卡片，返回 PNG 字节。

    对齐规则：披风数 < 3 时整行居中；否则 3 列网格左对齐（末行不满也左对齐）。
    """
    measure = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    f_name = _font(FS_NAME)
    f_sub = _font(FS_SUB)
    f_none = _font(FS_NONE)
    f_cn = _font(FS_CN)
    f_en = _font(FS_EN)
    f_footer = _font(FS_FOOTER)

    display_name = (player_name or "Steve").strip() or "Steve"
    name_lines = _wrap_text(measure, display_name, f_name, 300 * SCALE)
    name_line_h = int(FS_NAME * 1.2)
    profile_h = PROF_PAD_Y * 2 + max(
        AVATAR, name_line_h * len(name_lines) + int(FS_SUB * 1.2) + 4 * SCALE
    )

    has_active = any(bool(getattr(c, "is_active", False)) for c in capes)
    items: List[Tuple[str, str, str, bool, Optional[Image.Image]]] = []
    items.append(("none", "无", "None", not has_active, None))
    for c in capes:
        raw_display = str(getattr(c, "display_name", "") or "").strip()
        raw_alias = str(getattr(c, "alias", "") or "").strip()
        if raw_display and raw_display != raw_alias:
            cn, en = raw_display, raw_alias
        else:
            cn, en = (raw_alias or raw_display or "披风"), ""
        img: Optional[Image.Image] = None
        raw = getattr(c, "image", None)
        if raw and isinstance(raw, bytes):
            try:
                img = _process_cape_image(raw)
            except Exception:
                img = None
        items.append(("cape", cn, en, bool(getattr(c, "is_active", False)), img))

    center_row = len(capes) < 3

    content_w = CARD_W - BORDER * 2
    grid_w = content_w - WRAP_PAD_X * 2
    col_w = (grid_w - GRID_GAP_C * 2) // 3

    item_heights: List[int] = []
    name_layouts: List[Tuple[List[str], List[str]]] = []
    for _kind, cn, en, _active, _img in items:
        cn_lines = _wrap_text(measure, cn, f_cn, NAME_MAX_W)
        en_lines = _wrap_text(measure, en, f_en, NAME_MAX_W) if en else []
        name_layouts.append((cn_lines, en_lines))
        h = CAPE_H
        if cn_lines:
            h += CN_MT + int(FS_CN * 1.25) * len(cn_lines)
        if en_lines:
            h += EN_MT + int(FS_EN * 1.2) * len(en_lines)
        item_heights.append(h)

    rows = max(1, math.ceil(len(items) / 3))
    row_heights = [
        max(item_heights[r * 3 : r * 3 + 3]) for r in range(rows)
    ]
    grid_h = sum(row_heights) + GRID_GAP_R * (rows - 1)
    wrap_h = WRAP_PAD_T + grid_h + WRAP_PAD_B

    footer_text = "Create by GsCore & Power by MinecraftQueqiao & Auther by sssysy"
    footer_lines = _wrap_text(
        measure, footer_text, f_footer, content_w - FOOTER_PAD_X * 2
    )
    footer_h = (
        FOOTER_BORDER
        + FOOTER_PAD_Y * 2
        + int(FS_FOOTER * 1.2) * max(1, len(footer_lines))
    )

    card_h = BORDER * 2 + profile_h + GREEN_H + wrap_h + FOOTER_MT + footer_h

    canvas = Image.new("RGBA", (CARD_W, int(card_h)), BG_CARD + (255,))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(
        [0, 0, CARD_W - 1, card_h - 1], outline=BORDER_CARD + (255,), width=BORDER
    )

    # 顶栏
    bar_y = BORDER
    draw.rectangle(
        [BORDER, bar_y, CARD_W - BORDER - 1, bar_y + profile_h - 1],
        fill=BG_BAR + (255,),
    )
    draw.rectangle(
        [BORDER, bar_y + profile_h, CARD_W - BORDER - 1, bar_y + profile_h + GREEN_H - 1],
        fill=GREEN_LINE + (255,),
    )

    ax = BORDER + PROF_PAD_X
    ay = bar_y + (profile_h - AVATAR) // 2
    if avatar_bytes:
        try:
            av = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
        except Exception:
            av = _load_rgba(_DEFAULT_AVATAR_PNG)
    else:
        av = _load_rgba(_DEFAULT_AVATAR_PNG)
    av = av.resize((AVATAR, AVATAR), Image.NEAREST)
    canvas.paste(av, (ax, ay), av.split()[3])

    tx = ax + AVATAR + GAP_PROFILE
    total_name_h = name_line_h * len(name_lines) + int(FS_SUB * 1.2) + 4 * SCALE
    ty = bar_y + (profile_h - total_name_h) // 2
    for i, line in enumerate(name_lines):
        _draw_text(
            draw,
            (tx, ty + i * name_line_h),
            line,
            f_name,
            C_WHITE,
            ls=NAME_LS,
            bold=True,
        )
    draw.text(
        (tx, ty + name_line_h * len(name_lines) + 4 * SCALE),
        "已拥有披风",
        font=f_sub,
        fill=C_GRAY,
    )

    logo = _load_rgba(_MCLOGO_PNG)
    logo_w = int(LOGO_H * logo.width / logo.height)
    logo = logo.resize((logo_w, LOGO_H), Image.LANCZOS)
    canvas.paste(
        logo,
        (CARD_W - BORDER - PROF_PAD_X - logo_w, bar_y + (profile_h - LOGO_H) // 2),
        logo.split()[3],
    )

    # 网格
    grid_top = BORDER + profile_h + GREEN_H + WRAP_PAD_T
    for idx, (kind, cn, en, active, img) in enumerate(items):
        r, c = divmod(idx, 3)
        row_top = grid_top + sum(row_heights[:r]) + GRID_GAP_R * r
        if center_row:
            n = min(3, len(items))
            block_w = n * col_w + (n - 1) * GRID_GAP_C
            origin_x = BORDER + WRAP_PAD_X + (grid_w - block_w) // 2
        else:
            origin_x = BORDER + WRAP_PAD_X
        col_left = origin_x + c * (col_w + GRID_GAP_C)
        x0 = col_left + (col_w - CAPE_W) // 2
        y0 = row_top

        if kind == "none":
            no_img = _load_rgba(_NO_CAPES_PNG).resize((CAPE_W, CAPE_H), Image.NEAREST)
            canvas.paste(no_img, (x0, y0), no_img.split()[3])
            ftxt = "无"
            ls = 4 * SCALE
            tws = _tw(draw, ftxt, f_none) + (len(ftxt) - 1) * ls
            ths = _th(draw, ftxt, f_none)
            _draw_text(
                draw,
                (x0 + (CAPE_W - tws) // 2 + 2 * SCALE, y0 + (CAPE_H - ths) // 2),
                ftxt,
                f_none,
                C_NONE_TEXT,
                ls=ls,
            )
        elif img is not None:
            canvas.paste(img, (x0, y0), img.split()[3])

        cn_lines, en_lines = name_layouts[idx]
        cn_color = C_ACTIVE_CN if active else C_WHITE
        en_color = C_ACTIVE_EN if active else C_EN
        name_y = y0 + CAPE_H
        if cn_lines:
            name_y += CN_MT
            lh = int(FS_CN * 1.25)
            for i, line in enumerate(cn_lines):
                lw = _tw(draw, line, f_cn)
                draw.text(
                    (col_left + (col_w - lw) // 2, name_y + i * lh),
                    line,
                    font=f_cn,
                    fill=cn_color,
                )
            name_y += lh * len(cn_lines)
        if en_lines:
            name_y += EN_MT
            lh = int(FS_EN * 1.2)
            for i, line in enumerate(en_lines):
                lw = _tw(draw, line, f_en)
                draw.text(
                    (col_left + (col_w - lw) // 2, name_y + i * lh),
                    line,
                    font=f_en,
                    fill=en_color,
                )

    # 页脚
    fy = BORDER + profile_h + GREEN_H + wrap_h + FOOTER_MT
    draw.rectangle(
        [BORDER, fy, CARD_W - BORDER - 1, fy + FOOTER_BORDER - 1],
        fill=BORDER_FOOTER + (255,),
    )
    draw.rectangle(
        [BORDER, fy + FOOTER_BORDER, CARD_W - BORDER - 1, card_h - BORDER - 1],
        fill=BG_FOOTER + (255,),
    )
    text_y = fy + FOOTER_BORDER + FOOTER_PAD_Y
    parts = [
        ("Create by ", C_FOOTER),
        ("GsCore", C_WHITE),
        (" & Power by ", C_FOOTER),
        ("MinecraftQueqiao", C_WHITE),
        (" & Auther by ", C_FOOTER),
        ("sssysy", C_WHITE),
    ]
    line_w = sum(_tw(draw, t, f_footer) for t, _ in parts)
    cx = (CARD_W - line_w) // 2
    for t, col in parts:
        draw.text((cx, text_y), t, font=f_footer, fill=col)
        cx += _tw(draw, t, f_footer)

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()
