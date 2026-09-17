from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from gsuid_core.logger import logger

from .downloader import download_image

_TEXTURE2D_CAPES_DIR = (
    Path(__file__).parent.parent / "render" / "texture2d" / "capes"
)


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
    """统一获取披风原始贴图字节（内置 texture2d 优先；若未内置且有 url 则走 downloader）。"""
    # 1. 优先从内置 texture2d/capes 目录读取
    local_path = get_cape_texture_path(alias)
    if local_path is not None:
        try:
            return local_path.read_bytes()
        except Exception as e:
            logger.warning(
                f"[MCQueQiao] 读取内置披风贴图失败({local_path}): {e}"
            )

    # 2. 内置未收录且提供了网络 URL，走统一 downloader（image_tmp 缓存）
    if not texture_url:
        return None
    return await download_image(texture_url)
