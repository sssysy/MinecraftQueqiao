from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from gsuid_core.data_store import get_res_path
from gsuid_core.logger import logger

IMAGE_TMP_DIR: Path = get_res_path() / "MinecraftQueqiao" / "image_tmp"

HTTP_HEADERS = {
    "User-Agent": "MCQueQiao/2.0 (downloader; +https://github.com)",
}
HTTP_TIMEOUT = 10.0


def _cache_path(url: str) -> Path:
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".png"
    return IMAGE_TMP_DIR / f"{digest}{suffix}"


def _ensure_dir() -> None:
    IMAGE_TMP_DIR.mkdir(parents=True, exist_ok=True)


async def download_image(url: str) -> Optional[bytes]:
    """检查 image_tmp 缓存；未命中则下载并落盘。成功返回 bytes，失败返回 None。"""
    if not url:
        return None

    cache_file = _cache_path(url)
    if cache_file.is_file() and cache_file.stat().st_size > 0:
        try:
            return cache_file.read_bytes()
        except Exception as e:
            logger.warning(f"[MCQueQiao] 读取图片缓存失败({cache_file}): {e}")

    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers=HTTP_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200 or not resp.content:
                logger.debug(
                    f"[MCQueQiao] 图片下载失败 {url}: HTTP {resp.status_code}"
                )
                return None
            content = resp.content
    except httpx.TimeoutException:
        logger.debug(f"[MCQueQiao] 图片下载超时 {url}")
        return None
    except Exception as e:
        logger.debug(
            f"[MCQueQiao] 图片下载异常 {url}: {type(e).__name__}: {e}"
        )
        return None

    try:
        _ensure_dir()
        cache_file.write_bytes(content)
    except Exception as e:
        logger.warning(f"[MCQueQiao] 写入图片缓存失败({cache_file}): {e}")

    return content
