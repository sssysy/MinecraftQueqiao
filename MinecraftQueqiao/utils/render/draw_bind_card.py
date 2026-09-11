import hashlib
import uuid as uuid_lib
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import httpx
from PIL import Image, ImageDraw, ImageFont
from gsuid_core.logger import logger

RENDER_DIR = Path(__file__).parent
FONT_PATH = RENDER_DIR.parent / "fonts" / "mc-unicode-font.otf"
BG_PATH = RENDER_DIR / "texture2d" / "Blank_Sign.jpg"
DEFAULT_AVATAR_PATH = RENDER_DIR / "texture2d" / "default_head.png"

SCALE = 2
BASE_W, BASE_H = 768, 384
CANVAS_W = BASE_W * SCALE
CANVAS_H = BASE_H * SCALE

AVATAR_SIZE = 340
AVATAR_X = 90
AVATAR_Y = (CANVAS_H - AVATAR_SIZE) // 2

TEXT_X = 480
TEXT_RIGHT_PAD = 50
TEXT_MAX_W = CANVAS_W - TEXT_X - TEXT_RIGHT_PAD
# 四行几乎占满高度：上下留少量边距
TEXT_TOP = 28
LINE_BLOCK_H = (CANVAS_H - TEXT_TOP * 2) / 4
FONT_SIZE_BASE = 96
FONT_SIZE_MIN = 36
LINE_TOP_PAD = 6

TEXT_COLOR = (0, 0, 0)
TITLE_COLOR = (0, 0, 0)
PLACEHOLDER_BG = (180, 160, 120)
PLACEHOLDER_BORDER = (100, 80, 50)

HTTP_HEADERS = {
    "User-Agent": "MCQueQiao/2.0 (bind-card; +https://github.com)",
}
HTTP_TIMEOUT = 8.0


def offline_uuid(player_name: str) -> str:
    """按 OfflinePlayer:<name> 的 MD5 生成 Java 离线 UUID。"""
    data = f"OfflinePlayer:{player_name}".encode("utf-8")
    md5 = bytearray(hashlib.md5(data).digest())
    md5[6] = (md5[6] & 0x0F) | 0x30
    md5[8] = (md5[8] & 0x3F) | 0x80
    return str(uuid_lib.UUID(bytes=bytes(md5)))


def format_uuid(raw: str) -> str:
    """将 32 位无横线 UUID 格式化为带横线形式。"""
    raw = raw.replace("-", "").strip()
    if len(raw) != 32:
        return raw
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def mask_uuid(uuid_str: str) -> str:
    """隐藏 UUID 中间部分，仅保留前两位与后两位。"""
    if len(uuid_str) <= 4:
        return uuid_str
    return uuid_str[:2] + "*" * (len(uuid_str) - 4) + uuid_str[-2:]


async def get_player_uuid(player_name: str) -> str:
    """优先 Mojang API，失败时回退离线 UUID。"""
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(
                f"https://api.mojang.com/users/profiles/minecraft/{player_name}"
            )
            if resp.status_code == 200:
                data = resp.json()
                uid = str(data.get("id", "")).strip()
                if uid:
                    return format_uuid(uid)
    except Exception as e:
        logger.debug(f"[MCQueQiao] Mojang UUID 查询失败({player_name}): {e}")
    return offline_uuid(player_name)


def get_default_avatar() -> Optional[Image.Image]:
    """获取本地默认头像。"""
    if not DEFAULT_AVATAR_PATH.exists():
        return None
    try:
        img = Image.open(DEFAULT_AVATAR_PATH).convert("RGBA")
        return img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.NEAREST)
    except Exception as e:
        logger.debug(f"[MCQueQiao] 默认头像加载失败: {e}")
        return None


async def get_player_avatar(player_name: str) -> Optional[Image.Image]:
    """从 mc-heads.net 获取玩家头像，失败时使用本地默认头像。"""
    try:
        url = f"https://mc-heads.net/avatar/{player_name}/{AVATAR_SIZE}"
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content:
                img = Image.open(BytesIO(resp.content)).convert("RGBA")
                return img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.NEAREST)
    except Exception as e:
        logger.debug(f"[MCQueQiao] 玩家头像获取失败({player_name}): {e}")
    return get_default_avatar()


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size=max(1, int(size)))


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    size: int,
    max_w: int,
) -> ImageFont.ImageFont:
    """按最大宽度收缩字号，保证整行可见。"""
    size = int(size)
    while size > FONT_SIZE_MIN:
        font = _load_font(size)
        if _text_width(draw, text, font) <= max_w:
            return font
        size -= 2
    return _load_font(FONT_SIZE_MIN)


def _fit_font_pair(
    draw: ImageDraw.ImageDraw,
    texts: list[str],
    size: int,
    max_w: int,
) -> ImageFont.ImageFont:
    """按最大宽度收缩字号，确保所有正文文本使用相同字号并保持对齐。"""
    size = int(size)
    while size > FONT_SIZE_MIN:
        font = _load_font(size)
        if all(_text_width(draw, t, font) <= max_w for t in texts if t):
            return font
        size -= 2
    return _load_font(FONT_SIZE_MIN)


def _draw_placeholder(draw: ImageDraw.ImageDraw) -> None:
    x0, y0 = AVATAR_X, AVATAR_Y
    x1, y1 = x0 + AVATAR_SIZE, y0 + AVATAR_SIZE
    border = max(4, AVATAR_SIZE // 50)
    draw.rectangle(
        [x0, y0, x1, y1],
        fill=PLACEHOLDER_BG,
        outline=PLACEHOLDER_BORDER,
        width=border,
    )
    font = _load_font(max(28, AVATAR_SIZE // 8))
    text = "游戏头像"
    tw = _text_width(draw, text, font)
    th = _text_height(draw, text, font)
    tx = x0 + (AVATAR_SIZE - tw) // 2
    ty = y0 + (AVATAR_SIZE - th) // 2
    draw.text((tx, ty), text, font=font, fill=TEXT_COLOR)


async def draw_bind_card(
    player_name: str,
    user_name: str,
    hide_uuid: bool = False,
) -> Tuple[bytes, str]:
    """绘制绑定信息告示牌卡片。

    Returns:
        (jpg_bytes, display_uuid) — jpg 图片字节与展示用的 UUID 字符串
    """
    player_uuid = offline_uuid(player_name)
    display_uuid = mask_uuid(player_uuid) if hide_uuid else player_uuid

    bg = Image.open(BG_PATH).convert("RGB")
    canvas = bg.resize((CANVAS_W, CANVAS_H), Image.NEAREST)

    avatar = await get_player_avatar(player_name)
    if avatar is not None:
        mask = avatar.split()[3] if avatar.mode == "RGBA" else None
        canvas.paste(avatar, (AVATAR_X, AVATAR_Y), mask)
    else:
        draw_ph = ImageDraw.Draw(canvas)
        _draw_placeholder(draw_ph)

    draw = ImageDraw.Draw(canvas)
    try:
        _load_font(FONT_SIZE_BASE)
    except OSError as e:
        logger.warning(f"[MCQueQiao] 加载 MC 字体失败: {e}")
        raise

    title_text = "=== 绑定信息 ==="
    body_texts = [
        f"游戏名：{player_name}",
        f"用户名：{user_name}",
    ]

    title_font = _fit_font(draw, title_text, FONT_SIZE_BASE, TEXT_MAX_W)
    body_font = _fit_font_pair(draw, body_texts, FONT_SIZE_BASE, TEXT_MAX_W)

    render_items = [
        (title_text, title_font, TITLE_COLOR, True),
        (body_texts[0], body_font, TEXT_COLOR, False),
        (body_texts[1], body_font, TEXT_COLOR, False),
    ]

    for i, (text, font, color, is_title) in enumerate(render_items):
        th = _text_height(draw, text, font)
        block_h = LINE_BLOCK_H
        y = int(TEXT_TOP + i * block_h + (block_h - th) / 2) - LINE_TOP_PAD
        if is_title:
            tw = _text_width(draw, text, font)
            x = TEXT_X + max(0, (TEXT_MAX_W - tw) // 2)
        else:
            x = TEXT_X
        draw.text((x, y), text, font=font, fill=color)

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=95, subsampling=0)
    return buf.getvalue(), display_uuid
