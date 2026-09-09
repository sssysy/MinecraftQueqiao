import json
import re
from typing import Optional, Tuple

from gsuid_core.logger import logger

from ...mcqq_config import mcqq_config
from ...mcqq_core import send_rcon_command
from ...mcqq_database import MCQQRconWhitelist, MCQQUserBind, MCQQWaypoint
from .admin import is_admin


POS_PATTERN = re.compile(
    r"\[\s*(-?\d+(?:\.\d+)?)[df]?\s*,\s*(-?\d+(?:\.\d+)?)[df]?\s*,\s*(-?\d+(?:\.\d+)?)[df]?\s*\]"
)
DIM_PATTERN = re.compile(r'"(minecraft:[^"]+)"|"([^"]+)"')


async def get_player_pos_and_dimension(
    server_name: str, player_name: str
) -> Optional[Tuple[float, float, float, str]]:
    """通过 RCON 查询玩家当前位置坐标 (x, y, z) 及维度 (dimension)。
    如果玩家不在线或查询失败，返回 None。
    """
    # 1. 查询坐标 Pos
    ok, out = await send_rcon_command(
        server_name, f"data get entity {player_name} Pos"
    )
    if not ok or not out:
        logger.debug(f"[MC·地标传送] [{server_name}] 获取玩家 {player_name} Pos 失败: {out}")
        return None

    out_str = str(out)
    if "No entity was found" in out_str or "未找到实体" in out_str:
        return None

    match = POS_PATTERN.search(out_str)
    if not match:
        logger.warning(
            f"[MC·地标传送] [{server_name}] 无法解析玩家 {player_name} 坐标输出: {out_str}"
        )
        return None

    try:
        x = round(float(match.group(1)), 1)
        y = round(float(match.group(2)), 1)
        z = round(float(match.group(3)), 1)
    except (ValueError, IndexError):
        return None

    # 2. 查询维度 Dimension
    dimension = "minecraft:overworld"
    ok_dim, out_dim = await send_rcon_command(
        server_name, f"data get entity {player_name} Dimension"
    )
    if ok_dim and out_dim:
        dim_match = DIM_PATTERN.search(str(out_dim))
        if dim_match:
            dimension = dim_match.group(1) or dim_match.group(2) or "minecraft:overworld"

    return (x, y, z, dimension)


def parse_waypoint_args(
    raw_text: str, current_pos: Tuple[float, float, float]
) -> Tuple[str, float, float, float]:
    """按空格拆分参数：路径点名称、x、y、z。
    例如：
      '家 123 45 67' -> ('家', 123.0, 45.0, 67.0)
      '家 123  67' (中间两空格，y为空) -> ('家', 123.0, current_y, 67.0)
      '家 123' (少于4参数) -> ('家', 123.0, current_y, current_z)
      '家' -> ('家', current_x, current_y, current_z)

    Raises:
      ValueError: 路径点名称为空或坐标非数字
    """
    tokens = raw_text.strip().split(" ")
    if not tokens or not tokens[0].strip():
        raise ValueError("路径点名称不能为空")

    point_name = tokens[0].strip()
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

    x = _parse_coord(val_x, curr_x, "X")
    y = _parse_coord(val_y, curr_y, "Y")
    z = _parse_coord(val_z, curr_z, "Z")

    return point_name, x, y, z


async def send_player_tellraw(
    server_name: str,
    player_name: str,
    message: str,
    color: str = "green",
) -> bool:
    """向指定玩家发送游戏内 tellraw 消息（仅该玩家可见）"""
    payload = json.dumps({"text": message, "color": color}, ensure_ascii=False)
    cmd = f"tellraw {player_name} {payload}"
    ok, _ = await send_rcon_command(server_name, cmd)
    return ok


async def execute_teleport(
    server_name: str,
    player_name: str,
    point_name: str,
    x: float,
    y: float,
    z: float,
    dimension: str = "minecraft:overworld",
) -> Tuple[bool, str]:
    """执行传送并在游戏内向玩家发送 tellraw 提示。

    游戏内提示格式: [传送] 已传送至 <路径点名称> (<x>, <y>, <z>)
    """
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

    # 传送成功，发送游戏内私聊通知
    notify_text = f"[传送] 已传送至 {point_name} ({x}, {y}, {z})"
    await send_player_tellraw(server_name, player_name, notify_text, color="green")
    return True, notify_text


async def check_admin_permission(
    server_name: str,
    user_id: Optional[str] = None,
    user_pm: int = 6,
    player_name: Optional[str] = None,
) -> bool:
    """检查是否具有服务器管理员权限（兼容向后调用，代理至 is_admin）。"""
    return await is_admin(
        server_name=server_name,
        user_id=user_id,
        user_pm=user_pm,
        player_name=player_name,
    )


async def handle_ingame_tp_command(
    server_name: str, player_name: str, raw_message: str
) -> bool:
    """检查并处理游戏内发送的传送相关指令。
    若匹配到传送指令，执行对应逻辑并返回 True（拦截消息，阻止转发到 QQ 群）；
    否则返回 False（继续普通消息分发）。
    """
    if not player_name or not raw_message:
        return False

    if not mcqq_config.get_config("tp_enabled").data:
        return False

    msg = raw_message.strip()
    if msg.startswith("/"):
        msg = msg[1:].strip()

    # 1. 查看传送列表
    list_commands = (
        "mctp列表",
        "mc tp列表",
        "mctp 列表",
        "mc tp 列表",
        "mc传送列表",
        "mc 传送列表",
        "mc路径点列表",
        "mc 路径点列表",
    )
    if msg in list_commands:
        points = await MCQQWaypoint.get_list(server_name, player_name)
        if not points:
            await send_player_tellraw(
                server_name, player_name, "[MC 传送点列表] 暂无可用的传送点", "yellow"
            )
            return True

        global_pts = [p for p in points if p.is_global]
        personal_pts = [p for p in points if not p.is_global]

        await send_player_tellraw(
            server_name, player_name, "[MC 传送点列表]", "gold"
        )
        if global_pts:
            await send_player_tellraw(server_name, player_name, "[全局]", "yellow")
            for p in global_pts:
                await send_player_tellraw(
                    server_name, player_name, f" - {p.point_name}", "white"
                )
        if personal_pts:
            await send_player_tellraw(server_name, player_name, "[个人]", "aqua")
            for p in personal_pts:
                await send_player_tellraw(
                    server_name, player_name, f" - {p.point_name}", "white"
                )
        return True

    # 2. 增加全局路径点
    add_global_prefixes = ("mc增加全局tp", "mc添加全局tp", "mc 增加全局tp", "mc 添加全局tp")
    for pfx in add_global_prefixes:
        if msg.startswith(pfx):
            args = msg[len(pfx):].strip()
            if not args:
                await send_player_tellraw(
                    server_name, player_name, "用法: mc增加全局tp <路径点名称> [x] [y] [z]", "yellow"
                )
                return True

            is_admin_user = await is_admin(server_name, player_name=player_name)
            if not is_admin_user:
                await send_player_tellraw(
                    server_name, player_name, "您没有添加全局路径点的权限", "red"
                )
                return True

            pos_info = await get_player_pos_and_dimension(server_name, player_name)
            if not pos_info:
                await send_player_tellraw(
                    server_name, player_name, "[传送] 读取当前坐标失败", "red"
                )
                return True

            curr_x, curr_y, curr_z, curr_dim = pos_info
            try:
                pt_name, x, y, z = parse_waypoint_args(args, (curr_x, curr_y, curr_z))
            except ValueError as e:
                await send_player_tellraw(server_name, player_name, f"[传送] 参数错误: {e}", "red")
                return True

            await MCQQWaypoint.add_or_update(
                server_name, pt_name, player_name, x, y, z, curr_dim, is_global=True
            )
            await send_player_tellraw(
                server_name,
                player_name,
                f"[传送] 成功添加全局路径点 [{pt_name}] ({x}, {y}, {z})",
                "green",
            )
            return True

    # 3. 增加个人路径点
    add_prefixes = ("mc增加tp", "mc添加tp", "mc 增加tp", "mc 添加tp")
    for pfx in add_prefixes:
        if msg.startswith(pfx):
            args = msg[len(pfx):].strip()
            if not args:
                await send_player_tellraw(
                    server_name, player_name, "用法: mc增加tp <路径点名称> [x] [y] [z]", "yellow"
                )
                return True

            pos_info = await get_player_pos_and_dimension(server_name, player_name)
            if not pos_info:
                await send_player_tellraw(
                    server_name, player_name, "[传送] 读取当前坐标失败", "red"
                )
                return True

            curr_x, curr_y, curr_z, curr_dim = pos_info
            try:
                pt_name, x, y, z = parse_waypoint_args(args, (curr_x, curr_y, curr_z))
            except ValueError as e:
                await send_player_tellraw(server_name, player_name, f"[传送] 参数错误: {e}", "red")
                return True

            await MCQQWaypoint.add_or_update(
                server_name, pt_name, player_name, x, y, z, curr_dim, is_global=False
            )
            await send_player_tellraw(
                server_name,
                player_name,
                f"添加以下路径点成功\n名称：{pt_name}\n坐标：{x}, {y}, {z}",
                "green",
            )
            return True

    # 4. 删除全局路径点
    del_global_prefixes = ("mc删除全局tp", "mc 删除全局tp")
    for pfx in del_global_prefixes:
        if msg.startswith(pfx):
            pt_name = msg[len(pfx):].strip()
            if not pt_name:
                await send_player_tellraw(
                    server_name, player_name, "用法: mc删除全局tp <路径点名称>", "yellow"
                )
                return True

            is_admin_user = await is_admin(server_name, player_name=player_name)
            if not is_admin_user:
                await send_player_tellraw(
                    server_name, player_name, "您没有删除全局路径点的权限", "red"
                )
                return True

            ok = await MCQQWaypoint.delete_point(server_name, pt_name, player_name, is_global=True)
            if ok:
                await send_player_tellraw(
                    server_name, player_name, "删除成功", "green"
                )
            else:
                await send_player_tellraw(
                    server_name, player_name, f"删除失败：未找到路径点 {pt_name}", "red"
                )
            return True

    # 5. 删除个人路径点
    del_prefixes = ("mc删除tp", "mc 删除tp")
    for pfx in del_prefixes:
        if msg.startswith(pfx):
            pt_name = msg[len(pfx):].strip()
            if not pt_name:
                await send_player_tellraw(
                    server_name, player_name, "用法: mc删除tp <路径点名称>", "yellow"
                )
                return True

            ok = await MCQQWaypoint.delete_point(server_name, pt_name, player_name, is_global=False)
            if ok:
                await send_player_tellraw(
                    server_name, player_name, "删除成功", "green"
                )
            else:
                await send_player_tellraw(
                    server_name, player_name, f"删除失败：未找到路径点 {pt_name}", "red"
                )
            return True

    # 6. 传送指令 (mctp <地标> / mc tp <地标> / mc传送 <地标>)
    tp_prefixes = ("mctp ", "mctp", "mc tp ", "mc tp", "mc传送 ", "mc传送")
    for pfx in tp_prefixes:
        if msg.startswith(pfx):
            pt_name = msg[len(pfx):].strip()
            if not pt_name:
                await send_player_tellraw(
                    server_name, player_name, "用法: mctp <路径点名称>", "yellow"
                )
                return True

            point = await MCQQWaypoint.get_point(server_name, pt_name, player_name)
            if not point:
                await send_player_tellraw(
                    server_name,
                    player_name,
                    f"[传送] 未找到路径点 [{pt_name}]，输入 mctp列表 查看可用地标",
                    "red",
                )
                return True

            ok, msg_tp = await execute_teleport(
                server_name,
                player_name,
                point.point_name,
                point.x,
                point.y,
                point.z,
                point.dimension,
            )
            if not ok:
                await send_player_tellraw(server_name, player_name, f"[传送] {msg_tp}", "red")
            return True

    return False

