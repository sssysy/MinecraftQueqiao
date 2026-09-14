"""传送领域业务：两端共用，不感知 Bot/Event。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from gsuid_core.logger import logger

from ...mcqq_core.api import send_private_msg, send_rcon_command
from ...mcqq_config import mcqq_config
from ...mcqq_database import (
    MCQQBind,
    MCQQServer,
    MCQQUserBind,
    MCQQWaypoint,
)

POS_PATTERN = re.compile(
    r"\[\s*(-?\d+(?:\.\d+)?)[df]?\s*,\s*(-?\d+(?:\.\d+)?)[df]?\s*,\s*(-?\d+(?:\.\d+)?)[df]?\s*\]"
)
DIM_PATTERN = re.compile(r'"(minecraft:[^"]+)"|"([^"]+)"')


@dataclass
class ActiveServer:
    server: MCQQServer
    pos: Optional[Tuple[float, float, float, str]]


def tp_enabled() -> bool:
    return bool(mcqq_config.get_config("tp_enabled").data)


async def tellraw(
    server_name: str,
    player_name: str,
    message: str,
    color: str = "white",
) -> bool:
    """向玩家发送私聊（鹊桥 V2 send_private_msg）。"""
    payload = [{"text": message, "color": color}]
    ok, _ = await send_private_msg(server_name, player_name, payload)
    return ok


async def get_player_pos(
    server_name: str, player_name: str
) -> Optional[Tuple[float, float, float, str]]:
    ok, out = await send_rcon_command(
        server_name, f"data get entity {player_name} Pos"
    )
    if not ok or not out:
        logger.debug(
            f"[MC·地标传送] [{server_name}] 获取玩家 {player_name} Pos 失败: {out}"
        )
        return None

    out_str = str(out)
    if "No entity was found" in out_str or "未找到实体" in out_str:
        return None

    match = POS_PATTERN.search(out_str)
    if not match:
        logger.warning(
            f"[MC·地标传送] [{server_name}] 无法解析玩家 {player_name} 坐标: {out_str}"
        )
        return None

    try:
        x = round(float(match.group(1)), 1)
        y = round(float(match.group(2)), 1)
        z = round(float(match.group(3)), 1)
    except (ValueError, IndexError):
        return None

    dimension = "minecraft:overworld"
    ok_dim, out_dim = await send_rcon_command(
        server_name, f"data get entity {player_name} Dimension"
    )
    if ok_dim and out_dim:
        dim_match = DIM_PATTERN.search(str(out_dim))
        if dim_match:
            dimension = (
                dim_match.group(1) or dim_match.group(2) or "minecraft:overworld"
            )

    return (x, y, z, dimension)


async def execute_teleport(
    server_name: str,
    player_name: str,
    point_name: str,
    x: float,
    y: float,
    z: float,
    dimension: str = "minecraft:overworld",
) -> Tuple[bool, str]:
    if dimension:
        cmd = f"execute in {dimension} run tp {player_name} {x} {y} {z}"
    else:
        cmd = f"tp {player_name} {x} {y} {z}"

    ok, out = await send_rcon_command(server_name, cmd)
    if not ok:
        logger.warning(
            f"[MC·地标传送] [{server_name}] 传送玩家 {player_name} 失败: {out}"
        )
        return False, f"传送失败: {out}"

    notify_text = f"[传送] 已传送至 {point_name} ({x}, {y}, {z})"
    await tellraw(server_name, player_name, notify_text, "green")
    return True, notify_text


async def list_points(
    server_name: str, player_name: Optional[str] = None
) -> List[MCQQWaypoint]:
    return await MCQQWaypoint.get_list(server_name, player_name)


async def get_point(
    server_name: str, point_name: str, player_name: Optional[str] = None
) -> Optional[MCQQWaypoint]:
    return await MCQQWaypoint.get_point(server_name, point_name, player_name)


def build_point_from_tokens(
    tokens: list[str],
    current_pos: Tuple[float, float, float],
) -> Tuple[str, float, float, float]:
    """tokens[0]=名，[1..3]=x y z（可省）。tokens 已 decode。"""
    if not tokens:
        raise ValueError("路径点名称不能为空")
    if len(tokens) > 4:
        raise ValueError("参数传递错误，需要参数：路径点名称、x、y、z（坐标可省略）")

    point_name = tokens[0]
    curr_x, curr_y, curr_z = current_pos

    def _parse_coord(val: str, default: float, name: str) -> float:
        val_clean = val.strip()
        if not val_clean:
            return default
        try:
            return round(float(val_clean), 1)
        except ValueError:
            raise ValueError(f"坐标 {name} 必须为数字，输入为: '{val_clean}'")

    val_x = tokens[1] if len(tokens) > 1 else ""
    val_y = tokens[2] if len(tokens) > 2 else ""
    val_z = tokens[3] if len(tokens) > 3 else ""
    return (
        point_name,
        _parse_coord(val_x, curr_x, "X"),
        _parse_coord(val_y, curr_y, "Y"),
        _parse_coord(val_z, curr_z, "Z"),
    )


async def add_point(
    server_name: str,
    player_name: str,
    tokens: list[str],
    *,
    is_global: bool,
    curr_pos: Tuple[float, float, float, str],
) -> Tuple[bool, str]:
    curr_x, curr_y, curr_z, curr_dim = curr_pos
    try:
        point_name, x, y, z = build_point_from_tokens(
            tokens, (curr_x, curr_y, curr_z)
        )
    except ValueError as e:
        return False, str(e)

    await MCQQWaypoint.add_or_update(
        server_name=server_name,
        point_name=point_name,
        player_name=player_name,
        x=x,
        y=y,
        z=z,
        dimension=curr_dim,
        is_global=is_global,
    )
    scope = "全局" if is_global else "个人"
    return (
        True,
        f"添加{scope}路径点成功\n名称：{point_name}\n坐标：{x}, {y}, {z}",
    )


async def delete_point(
    server_name: str,
    player_name: str,
    point_name: str,
    *,
    is_global: bool,
) -> Tuple[bool, str]:
    ok = await MCQQWaypoint.delete_point(
        server_name=server_name,
        point_name=point_name,
        player_name=player_name,
        is_global=is_global,
    )
    if ok:
        return True, "删除成功"
    return False, f"删除失败：未找到路径点 {point_name}"


async def teleport_to(
    server_name: str, player_name: str, point_name: str
) -> Tuple[bool, str]:
    point = await get_point(server_name, point_name, player_name)
    if not point:
        return False, f"未找到路径点 [{point_name}]"
    return await execute_teleport(
        server_name,
        player_name,
        point.point_name,
        point.x,
        point.y,
        point.z,
        point.dimension,
    )


async def get_bound_player_by_user_id(user_id: str) -> Optional[str]:
    bind = await MCQQUserBind.get_by_user_id(user_id)
    if bind and bind.player_name:
        return bind.player_name.strip()
    return None


async def resolve_active_server(
    group_id: str,
    player_name: str,
    *,
    need_pos: bool = True,
) -> Tuple[Optional[MCQQServer], Optional[Tuple[float, float, float, str]], Optional[str]]:
    binds = await MCQQBind.get_by_group_id(group_id)
    if not binds:
        return None, None, "当前群未绑定任何 MC 服务器，请先执行 mc群服绑定"

    servers: List[MCQQServer] = []
    for b in binds:
        s = await MCQQServer.get_by_name(b.server_name)
        if s and s.enabled and s not in servers:
            servers.append(s)

    if not servers:
        return None, None, "无可用服务器"

    if not need_pos:
        return servers[0], None, None

    if len(servers) == 1:
        s = servers[0]
        pos_info = await get_player_pos(s.server_name, player_name)
        return s, pos_info, None

    for s in servers:
        pos_info = await get_player_pos(s.server_name, player_name)
        if pos_info is not None:
            return s, pos_info, None

    return servers[0], None, None


def format_point_list(points: List[MCQQWaypoint]) -> str:
    if not points:
        return "路径点列表\n - 无"

    global_pts = [p for p in points if p.is_global]
    personal_pts = [p for p in points if not p.is_global]
    lines = ["[MC 传送点列表]"]
    if global_pts:
        lines.append("[全局]")
        for p in global_pts:
            lines.append(f" - {p.point_name}")
    if personal_pts:
        lines.append("[个人]")
        for p in personal_pts:
            lines.append(f" - {p.point_name}")
    return "\n".join(lines)
