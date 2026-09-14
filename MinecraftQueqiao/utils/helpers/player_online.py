"""基于 RCON data get entity 的语言无关在线判定。只认 NBT，不认本地化文案。"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from gsuid_core.logger import logger

from ...mcqq_core.api import send_rcon_command

# data get entity <name> Pos → [123.0d, 64.0d, 456.0d]
POS_PATTERN = re.compile(
    r"\[\s*(-?\d+(?:\.\d+)?)[df]?\s*,\s*(-?\d+(?:\.\d+)?)[df]?\s*,\s*(-?\d+(?:\.\d+)?)[df]?\s*\]"
)
# data get entity <name> UUID → [I; 1, 2, 3, 4]
UUID_PATTERN = re.compile(r"\[\s*I\s*;")
# data get entity <name> Dimension → "minecraft:overworld"
DIM_PATTERN = re.compile(r'"(minecraft:[^"]+)"|"([^"]+)"')


async def is_player_online(server_name: str, player_name: str) -> bool:
    """通过实体 NBT 是否可解析判断玩家是否在线，不依赖命令输出语言。"""
    ok, out = await send_rcon_command(
        server_name, f"data get entity {player_name} Pos"
    )
    if ok and out and POS_PATTERN.search(str(out)):
        return True

    ok_uuid, out_uuid = await send_rcon_command(
        server_name, f"data get entity {player_name} UUID"
    )
    if ok_uuid and out_uuid and UUID_PATTERN.search(str(out_uuid)):
        return True

    logger.debug(
        f"[MC·在线判定] [{server_name}] 玩家 {player_name} 离线或 NBT 不可解析: "
        f"pos={out!r}, uuid={out_uuid!r}"
    )
    return False


async def get_player_pos(
    server_name: str, player_name: str
) -> Optional[Tuple[float, float, float, str]]:
    """读取玩家坐标与维度；仅解析 NBT，不依赖本地化前缀句。"""
    ok, out = await send_rcon_command(
        server_name, f"data get entity {player_name} Pos"
    )
    if not ok or not out:
        logger.debug(
            f"[MC·实体坐标] [{server_name}] 获取 {player_name} Pos 失败: {out}"
        )
        return None

    out_str = str(out)
    match = POS_PATTERN.search(out_str)
    if not match:
        logger.debug(
            f"[MC·实体坐标] [{server_name}] {player_name} Pos 无 NBT: {out_str}"
        )
        return None

    try:
        x = round(float(match.group(1)), 1)
        y = round(float(match.group(2)), 1)
        z = round(float(match.group(3)), 1)
    except (ValueError, IndexError):
        return None

    ok_dim, out_dim = await send_rcon_command(
        server_name, f"data get entity {player_name} Dimension"
    )
    dim_match = DIM_PATTERN.search(str(out_dim)) if ok_dim and out_dim else None
    if not dim_match:
        return None

    return (x, y, z, dim_match.group(1) or dim_match.group(2))
