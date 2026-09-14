"""玩家相关：目标解析与正版头像/皮肤拉取。"""

from __future__ import annotations

import random
from io import BytesIO
from typing import List, Optional, Tuple

import httpx
from PIL import Image
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQUserBind
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.user_select import extract_at_user_ids

AVATAR_SIZE = 256
HTTP_HEADERS = {
    "User-Agent": "MCQueQiao/2.0 (player-info; +https://github.com)",
}
HTTP_TIMEOUT = 8.0

# 正面大脸：mc-heads avatar（仅头部正面）
STYLE_FACE = "正面大脸"


async def resolve_target_player_name(
    ev: Event,
    *,
    cmd_usage: str,
) -> Tuple[Optional[str], Optional[str]]:
    """解析查询目标。

    - 空参：自己已绑定的游戏名
    - @用户：该用户已绑定的游戏名
    - 1 参：正版玩家名
    - 不支持 QQ 号

    Returns:
        (player_name, err)
    """
    at_users = extract_at_user_ids(ev)
    tokens = split_cmd_args(ev.text)

    if at_users:
        if tokens:
            return None, f"参数传递错误\n{cmd_usage}"
        target_uid = at_users[0]
        bind = await MCQQUserBind.get_by_user_id(target_uid)
        if not bind or not bind.player_name:
            return None, "未找到绑定，请先 mc绑定 <游戏名>"
        return bind.player_name, None

    if len(tokens) == 0:
        bind = await MCQQUserBind.get_by_user_id(ev.user_id)
        if not bind or not bind.player_name:
            return None, "你尚未绑定游戏名，请先 mc绑定 <游戏名>"
        return bind.player_name, None

    if len(tokens) == 1:
        return decode_arg(tokens[0]), None

    return None, f"参数传递错误\n{cmd_usage}"


def _pick_avatar_style() -> str:
    options: List[str] = list(mcqq_config.get_config("avatar_style").data or [])
    if not options:
        return STYLE_FACE
    return random.choice(options)


async def _download(url: str) -> Optional[bytes]:
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers=HTTP_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content:
                return resp.content
            logger.debug(
                f"[MCQueQiao] 下载失败 {url}: HTTP {resp.status_code}"
            )
    except httpx.TimeoutException:
        logger.debug(f"[MCQueQiao] 下载超时 {url}")
    except Exception as e:
        logger.debug(f"[MCQueQiao] 下载异常 {url}: {type(e).__name__}: {e}")
    return None


async def fetch_avatar_png(player_name: str) -> Tuple[Optional[bytes], Optional[str]]:
    """按配置风格拉取头像，固定输出 256x256 PNG。"""
    style = _pick_avatar_style()
    # 当前仅「正面大脸」；预留多风格扩展
    url = f"https://mc-heads.net/avatar/{player_name}/{AVATAR_SIZE}"
    if style != STYLE_FACE:
        logger.warning(f"[MCQueQiao] 未知头像风格 {style}，回退为 {STYLE_FACE}")

    content = await _download(url)
    if content is None:
        return None, f"获取头像失败：{player_name}\n请确认玩家名是否为正版名，或稍后重试"

    try:
        img = Image.open(BytesIO(content)).convert("RGBA")
        if img.size != (AVATAR_SIZE, AVATAR_SIZE):
            img = img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.NEAREST)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), None
    except Exception as e:
        logger.warning(f"[MCQueQiao] 头像处理失败({player_name}): {e}")
        return None, f"头像图片处理失败：{player_name}"


async def fetch_skin_png(player_name: str) -> Tuple[Optional[bytes], Optional[str]]:
    """拉取原始皮肤贴图 PNG（不重编码，可直接导入游戏）。"""
    url = f"https://mc-heads.net/skin/{player_name}"
    content = await _download(url)
    if content is None:
        return None, f"获取皮肤失败：{player_name}\n请确认玩家名是否为正版名，或稍后重试"

    # 仅校验是合法 PNG，字节保持原样
    try:
        Image.open(BytesIO(content)).verify()
    except Exception as e:
        logger.warning(f"[MCQueQiao] 皮肤不是合法图片({player_name}): {e}")
        return None, f"皮肤图片无效：{player_name}"
    return content, None
