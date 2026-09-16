from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx
from gsuid_core.logger import logger

from .map import get_display_name

HTTP_HEADERS = {
    "User-Agent": "MCQueQiao/2.0 (capes; +https://github.com)",
    "Accept": "application/json",
}
HTTP_TIMEOUT = 12.0

PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"
ACTIVE_CAPE_URL = "https://api.minecraftservices.com/minecraft/profile/capes/active"

NONE_ALIASES = frozenset({"无", "无披风", "none", "no", "null", "nonecape"})


@dataclass
class CapeItem:
    cape_id: str
    alias: str
    display_name: str
    is_active: bool
    texture_url: str
    image: Optional[bytes] = None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        headers=HTTP_HEADERS,
        follow_redirects=True,
    )


async def _download_image(url: str) -> Optional[bytes]:
    if not url:
        return None
    try:
        async with _client() as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content:
                return resp.content
            logger.debug(
                f"[MCQueQiao] 披风贴图下载失败 {url}: HTTP {resp.status_code}"
            )
    except Exception as e:
        logger.debug(f"[MCQueQiao] 披风贴图下载异常 {url}: {type(e).__name__}: {e}")
    return None


async def fetch_owned_capes(
    mc_token: str,
    *,
    with_images: bool = True,
) -> Tuple[Optional[List[CapeItem]], Optional[str]]:
    """拉取账户披风列表；with_images 时下载贴图 bytes。"""
    try:
        async with _client() as client:
            resp = await client.get(
                PROFILE_URL,
                headers={"Authorization": f"Bearer {mc_token}"},
            )
            data = resp.json()
    except Exception as e:
        logger.warning(f"[MCQueQiao] 拉取披风列表异常: {type(e).__name__}: {e}")
        return None, "获取披风列表失败，请稍后重试"

    if resp.status_code == 401:
        return None, "登录已失效，请重新发送 mc登录"
    if resp.status_code != 200:
        err_msg = data.get("errorMessage") or f"HTTP {resp.status_code}"
        logger.warning(f"[MCQueQiao] 拉取披风列表拒绝: {err_msg}")
        return None, f"获取披风列表失败：{err_msg}"

    raw_capes = data.get("capes") or []
    items: List[CapeItem] = []
    for cape in raw_capes:
        if not isinstance(cape, dict):
            continue
        alias = str(cape.get("alias") or "")
        items.append(
            CapeItem(
                cape_id=str(cape.get("id") or ""),
                alias=alias,
                display_name=get_display_name(alias),
                is_active=str(cape.get("state") or "").upper() == "ACTIVE",
                texture_url=str(cape.get("url") or ""),
            )
        )

    if with_images:
        for item in items:
            item.image = await _download_image(item.texture_url)

    return items, None


def is_none_cape_name(name: str) -> bool:
    return name.strip().lower() in NONE_ALIASES


def match_cape(
    capes: List[CapeItem], query: str
) -> Optional[CapeItem]:
    """按中文译名或英文 alias 匹配；不匹配「无」。"""
    q = query.strip()
    if not q or is_none_cape_name(q):
        return None
    ql = q.lower()
    ql_ns = ql.replace(" ", "")

    for c in capes:
        if c.display_name == q or c.display_name.lower() == ql:
            return c
    for c in capes:
        if c.alias.lower() == ql:
            return c
    for c in capes:
        if (
            c.alias.lower().replace(" ", "") == ql_ns
            or c.display_name.lower().replace(" ", "") == ql_ns
        ):
            return c
    return None


async def set_active_cape(
    mc_token: str,
    cape_id: Optional[str],
) -> Optional[str]:
    """切换披风；cape_id 为 None 时卸下。失败返回错误文案。"""
    try:
        async with _client() as client:
            if cape_id is None:
                resp = await client.delete(
                    ACTIVE_CAPE_URL,
                    headers={"Authorization": f"Bearer {mc_token}"},
                )
            else:
                resp = await client.put(
                    ACTIVE_CAPE_URL,
                    headers={
                        "Authorization": f"Bearer {mc_token}",
                        "Content-Type": "application/json",
                    },
                    json={"capeId": cape_id},
                )
            data = resp.json() if resp.content else {}
    except Exception as e:
        logger.warning(f"[MCQueQiao] 切换披风异常: {type(e).__name__}: {e}")
        return "切换披风失败，请稍后重试"

    if resp.status_code == 401:
        return "登录已失效，请重新发送 mc登录"
    if resp.status_code >= 400:
        err_msg = (
            data.get("errorMessage")
            or data.get("error")
            or f"HTTP {resp.status_code}"
        )
        logger.warning(f"[MCQueQiao] 切换披风拒绝: {err_msg}")
        return f"切换披风失败：{err_msg}"
    return None


def format_cape_list(player_name: str, capes: List[CapeItem]) -> str:
    lines = [f"{player_name} 的可选披风列表：", " - 无"]
    for c in capes:
        suffix = " (应用中)" if c.is_active else ""
        lines.append(f" - {c.display_name}{suffix}")
    return "\n".join(lines)
