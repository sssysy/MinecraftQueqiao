from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

import httpx
from gsuid_core.logger import logger

_TEXTURE2D_CAPES_DIR = (
    Path(__file__).parent.parent / "render" / "texture2d" / "capes"
)

HTTP_HEADERS = {
    "User-Agent": "MCQueQiao/2.0 (cape-cache; +https://github.com)",
}
HTTP_TIMEOUT = 10.0


def safe_cape_filename(alias: str) -> str:
    """过滤文件名非法字符并生成标准的披风文件名。"""
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", alias.strip())
    if not safe_name:
        safe_name = "unknown_cape"
    return f"{safe_name}.png"


def get_cape_texture_path(alias: str) -> Optional[Path]:
    """检查插件内置 texture2d/capes 目录下是否存在原始披风贴图。"""
    if not alias:
        return None
    fname = safe_cape_filename(alias)
    t2d_file = _TEXTURE2D_CAPES_DIR / fname
    if t2d_file.is_file() and t2d_file.stat().st_size > 0:
        return t2d_file
    return None


async def get_cape_texture_bytes(
    alias: str, texture_url: str = ""
) -> Optional[bytes]:
    """统一获取披风原始贴图字节（内置 texture2d 优先；若未内置且有 url 则在线获取）。"""
    # 1. 优先从内置 texture2d/capes 目录读取
    local_path = get_cape_texture_path(alias)
    if local_path is not None:
        try:
            return local_path.read_bytes()
        except Exception as e:
            logger.warning(
                f"[MCQueQiao] 读取内置披风贴图失败({local_path}): {e}"
            )

    # 2. 内置未收录且提供了网络 URL，发起下载返回 bytes
    if not texture_url:
        return None

    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers=HTTP_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(texture_url)
            if resp.status_code == 200 and resp.content:
                return resp.content
            logger.debug(
                f"[MCQueQiao] 披风贴图下载失败 {texture_url}: HTTP {resp.status_code}"
            )
    except Exception as e:
        logger.debug(f"[MCQueQiao] 披风贴图下载异常 {texture_url}: {e}")

    return None
