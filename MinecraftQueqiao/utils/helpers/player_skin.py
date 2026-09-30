"""正版皮肤纹理拉取与大头裁切。"""

from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import Any, Optional
from urllib.parse import quote

import httpx
from PIL import Image
from gsuid_core.logger import logger

from ...mcqq_config import mcqq_config
from .downloader import HTTP_HEADERS, HTTP_TIMEOUT, download_image

# 标准皮肤 UV：脸部 + 外层帽（仅 64x64 新版皮肤有帽层）
_FACE_BOX = (8, 8, 16, 16)
_HAT_BOX = (40, 8, 48, 16)

DEFAULT_MOJANG_API_BASE = "https://api.mojang.com"
DEFAULT_MOJANG_SESSION_BASE = "https://sessionserver.mojang.com"
DEFAULT_MOJANG_TEXTURE_BASE = "https://textures.minecraft.net"

PLAYER_AVATAR_SIZE = 256


def _base_url(key: str, default: str) -> str:
    raw = mcqq_config.get_config(key).data
    text = str(raw).strip() if raw else ""
    return text.rstrip("/") if text else default


def _rewrite_texture_url(raw_url: str) -> str:
    """将档案里的纹理 URL 换成配置的 CDN base。"""
    base = _base_url("mojang_texture_base", DEFAULT_MOJANG_TEXTURE_BASE)
    marker = "/texture/"
    idx = raw_url.find(marker)
    if idx >= 0:
        return f"{base}{raw_url[idx:]}"
    return raw_url


async def _get_json(client: httpx.AsyncClient, url: str) -> Optional[Any]:
    try:
        resp = await client.get(url)
    except Exception as e:
        logger.debug(f"[MCQueQiao] 请求失败 {url}: {type(e).__name__}: {e}")
        return None
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        logger.debug(f"[MCQueQiao] 请求被拒绝 {url}: HTTP {resp.status_code}")
        return None
    try:
        return resp.json()
    except Exception as e:
        logger.debug(f"[MCQueQiao] 响应不是 JSON {url}: {e}")
        return None


async def _name_to_uuid(client: httpx.AsyncClient, player_name: str) -> Optional[str]:
    api = _base_url("mojang_api_base", DEFAULT_MOJANG_API_BASE)
    url = f"{api}/users/profiles/minecraft/{quote(player_name)}"
    data = await _get_json(client, url)
    if not isinstance(data, dict):
        return None
    uuid = data.get("id")
    return str(uuid) if uuid else None


async def _uuid_to_skin_url(client: httpx.AsyncClient, uuid: str) -> Optional[str]:
    session = _base_url("mojang_session_base", DEFAULT_MOJANG_SESSION_BASE)
    url = f"{session}/session/minecraft/profile/{uuid}"
    data = await _get_json(client, url)
    if not isinstance(data, dict):
        return None
    for prop in data.get("properties") or []:
        if not isinstance(prop, dict) or prop.get("name") != "textures":
            continue
        raw = prop.get("value")
        if not raw:
            continue
        try:
            payload = json.loads(base64.b64decode(raw))
        except Exception as e:
            logger.debug(f"[MCQueQiao] 解析皮肤档案失败({uuid}): {e}")
            return None
        skin = (payload.get("textures") or {}).get("SKIN") or {}
        raw_url = skin.get("url")
        if raw_url:
            return _rewrite_texture_url(str(raw_url))
    return None


async def fetch_skin_texture(player_name: str) -> Optional[bytes]:
    """拉取原始皮肤贴图 PNG（64x64 / 64x32），失败返回 None。"""
    if not player_name:
        return None
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers=HTTP_HEADERS,
            follow_redirects=True,
        ) as client:
            uuid = await _name_to_uuid(client, player_name)
            if not uuid:
                return None
            skin_url = await _uuid_to_skin_url(client, uuid)
            if not skin_url:
                return None
    except Exception as e:
        logger.debug(
            f"[MCQueQiao] 获取皮肤地址失败({player_name}): {type(e).__name__}: {e}"
        )
        return None
    return await download_image(skin_url)


def render_front_face(skin_bytes: bytes, size: int = PLAYER_AVATAR_SIZE) -> Optional[bytes]:
    """从皮肤贴图裁出正面大脸（脸 + 帽层），NEAREST 放大后返回 PNG。"""
    try:
        skin = Image.open(BytesIO(skin_bytes))
        face = skin.crop(_FACE_BOX).convert("RGBA")
        # 64x32 旧版皮肤没有外层帽
        if skin.height >= 64 and skin.width >= 48:
            hat = skin.crop(_HAT_BOX).convert("RGBA")
            face = Image.alpha_composite(face, hat)
        if size != face.width:
            face = face.resize((size, size), Image.NEAREST)
        buf = BytesIO()
        face.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"[MCQueQiao] 大头裁切失败: {type(e).__name__}: {e}")
        return None


async def fetch_player_avatar(player_name: str) -> Optional[bytes]:
    """统一玩家头像入口：官方皮肤裁切正面大脸，失败返回 None。"""
    if not player_name:
        return None
    skin = await fetch_skin_texture(player_name)
    if skin is None:
        return None
    return render_front_face(skin)
