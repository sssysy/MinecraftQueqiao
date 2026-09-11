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

SCALE = 2
BASE_W, BASE_H = 768, 384
CANVAS_W = BASE_W * SCALE
CANVAS_H = BASE_H * SCALE

AVATAR_SIZE = 220
AVATAR_X = 160
AVATAR_Y = (CANVAS_H - AVATAR_SIZE) // 2

TEXT_X = 500
TEXT_START_Y = 150
LINE_GAP = 115
FONT_SIZE_TITLE = 48
FONT_SIZE_BODY = 36

TEXT_COLOR = (55, 45, 35)
TITLE_COLOR = (40, 32, 24)
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


async def get_player_avatar(player_name: str) -> Optional[Image.Image]:
    """从 mc-heads.net 获取玩家头像，失败返回 None。"""
    try:
        url = f"https://mc-heads.net/avatar/{player_name}/{AVATAR_SIZE}"
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content:
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                return img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.NEAREST)
    except Exception as e:
        logger.debug(f"[MCQueQiao] 玩家头像获取失败({player_name}): {e}")
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size=size)


def _draw_placeholder(draw: ImageDraw.ImageDraw) -> None:
    x0, y0 = AVATAR_X, AVATAR_Y
    x1, y1 = x0 + AVATAR_SIZE, y0 + AVATAR_SIZE
    draw.rectangle([x0, y0, x1, y1], fill=PLACEHOLDER_BG, outline=PLACEHOLDER_BORDER, width=4)
    try:
        font = _load_font(28)
    except OSError:
        font = ImageFont.load_default()
    text = "游戏头像"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
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
    player_uuid = await get_player_uuid(player_name)
    display_uuid = mask_uuid(player_uuid) if hide_uuid else player_uuid

    bg = Image.open(BG_PATH).convert("RGB")
    canvas = bg.resize((CANVAS_W, CANVAS_H), Image.NEAREST)

    avatar = await get_player_avatar(player_name)
    if avatar is not None:
        canvas.paste(avatar, (AVATAR_X, AVATAR_Y))
    else:
        draw_ph = ImageDraw.Draw(canvas)
        _draw_placeholder(draw_ph)

    draw = ImageDraw.Draw(canvas)
    try:
        title_font = _load_font(FONT_SIZE_TITLE)
        body_font = _load_font(FONT_SIZE_BODY)
    except OSError as e:
        logger.warning(f"[MCQueQiao] 加载 MC 字体失败，使用默认字体: {e}")
        title_font = ImageFont.load_default()
        body_font = title_font

    lines = [
        ("绑定信息", title_font, TITLE_COLOR),
        (f"游戏名：{player_name}", body_font, TEXT_COLOR),
        (f"用户名：{user_name}", body_font, TEXT_COLOR),
        (f"UUID：{display_uuid}", body_font, TEXT_COLOR),
    ]

    for i, (text, font, color) in enumerate(lines):
        y = TEXT_START_Y + i * LINE_GAP
        x = TEXT_X
        if i == 0:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            x = TEXT_X + max(0, (CANVAS_W - TEXT_X - 80 - tw) // 2)
        draw.text((x, y), text, font=font, fill=color)

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=95, subsampling=0)
    return buf.getvalue(), display_uuid
