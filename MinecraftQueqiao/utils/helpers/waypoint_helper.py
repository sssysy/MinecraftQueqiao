import json
import re
from typing import List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ...mcqq_config import mcqq_config
from ...mcqq_core import send_rcon_command
from ...mcqq_database import (
    MCQQBind,
    MCQQRconWhitelist,
    MCQQServer,
    MCQQUserBind,
    MCQQWaypoint,
)
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


async def get_bound_player(ev: Event) -> Optional[str]:
    """获取触发者绑定的 MC 角色名"""
    bind = await MCQQUserBind.get_by_user_id(ev.user_id)
    if bind and bind.player_name:
        return bind.player_name.strip()
    return None


async def resolve_active_server(
    group_id: str, player_name: str
) -> Tuple[Optional[MCQQServer], Optional[Tuple[float, float, float, str]], Optional[str]]:
    """解析当前群绑定的服务器，并检测玩家在哪台服务器在线。

    返回: (server, pos_info, error_message)
    """
    binds = await MCQQBind.get_by_group_id(group_id)
    if not binds:
        return None, None, "当前群未绑定任何 MC 服务器，请先执行 mc群服绑定"

    # 获取所有启用的服务器
    servers: List[MCQQServer] = []
    for b in binds:
        s = await MCQQServer.get_by_name(b.server_name)
        if s and s.enabled and s not in servers:
            servers.append(s)

    if not servers:
        return None, None, "无可用服务器"

    # 如果仅绑定了一台服务器
    if len(servers) == 1:
        s = servers[0]
        pos_info = await get_player_pos_and_dimension(s.server_name, player_name)
        return s, pos_info, None

    # 多服务器：寻找玩家当前在线的那台
    for s in servers:
        pos_info = await get_player_pos_and_dimension(s.server_name, player_name)
        if pos_info is not None:
            return s, pos_info, None

    # 若玩家都不在线，返回首个服务器但 pos_info 为 None
    return servers[0], None, None


async def handle_list_waypoint(bot: Bot, ev: Event) -> None:
    """查看路径点列表处理逻辑: mctp列表"""
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用 mctp列表")
        return

    player_name = await get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    server, pos_info, err = await resolve_active_server(ev.group_id, player_name)
    if err:
        await bot.send(err)
        return

    if not pos_info:
        await bot.send("玩家离线，无法获取路径点列表")
        return

    points = await MCQQWaypoint.get_list(
        server_name=server.server_name,
        player_name=player_name,
    )

    if not points:
        await bot.send("路径点列表\n - 无")
        return

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

    await bot.send("\n".join(lines))


async def handle_teleport(bot: Bot, ev: Event) -> None:
    """传送指令处理逻辑: mctp <路径点名称>"""
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用 mctp <路径点名称>")
        return

    player_name = await get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    point_name = ev.text.strip()
    if not point_name:
        await bot.send("用法：mctp <路径点名称>")
        return

    server, pos_info, err = await resolve_active_server(ev.group_id, player_name)
    if err:
        await bot.send(err)
        return

    if not pos_info:
        await bot.send("玩家离线，无法执行")
        return

    point = await MCQQWaypoint.get_point(server.server_name, point_name, player_name)
    if not point:
        await bot.send("未找到路径点，请在路径点列表中确认路径点名称")
        return

    ok, msg = await execute_teleport(
        server.server_name,
        player_name,
        point.point_name,
        point.x,
        point.y,
        point.z,
        point.dimension,
    )
    if not ok:
        await bot.send(f"传送失败: {msg}")
    # 传送成功后游戏内已发送 tellraw，群聊按要求不发送任何提示


async def handle_add_waypoint(bot: Bot, ev: Event, is_global: bool) -> None:
    """添加路径点处理逻辑"""
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用该指令")
        return

    player_name = await get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    raw_args = ev.text.strip()
    if not raw_args:
        cmd_name = "增加全局tp" if is_global else "增加tp"
        await bot.send(f"用法：mc{cmd_name} <路径点名称> [x] [y] [z]")
        return

    server, pos_info, err = await resolve_active_server(ev.group_id, player_name)
    if err:
        await bot.send(err)
        return

    # 全局路径点权限校验
    if is_global:
        is_admin_user = await is_admin(
            server.server_name,
            ev=ev,
            player_name=player_name,
        )
        if not is_admin_user:
            await bot.send("您没有添加全局路径点的权限")
            return

    if not pos_info:
        await bot.send("玩家离线，无法获取玩家位置，执行失败")
        return

    curr_x, curr_y, curr_z, curr_dim = pos_info

    try:
        point_name, x, y, z = parse_waypoint_args(
            raw_args, (curr_x, curr_y, curr_z)
        )
    except ValueError:
        cmd_name = "增加全局tp" if is_global else "增加tp"
        await bot.send(f"参数错误！\n用法：mc{cmd_name} <路径点名称> [x] [y] [z]")
        return

    await MCQQWaypoint.add_or_update(
        server_name=server.server_name,
        point_name=point_name,
        player_name=player_name,
        x=x,
        y=y,
        z=z,
        dimension=curr_dim,
        is_global=is_global,
    )

    if is_global:
        await bot.send(
            f"添加以下全局路径点成功\n"
            f"名称：{point_name}\n"
            f"坐标：{x}, {y}, {z}"
        )
    else:
        await bot.send(
            f"添加以下路径点成功\n"
            f"名称：{point_name}\n"
            f"坐标：{x}, {y}, {z}"
        )


async def handle_delete_waypoint(bot: Bot, ev: Event, is_global: bool) -> None:
    """删除路径点处理逻辑"""
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用该指令")
        return

    player_name = await get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    point_name = ev.text.strip()
    if not point_name:
        cmd_name = "删除全局tp" if is_global else "删除tp"
        await bot.send(f"用法：mc{cmd_name} <路径点名称>")
        return

    server, pos_info, err = await resolve_active_server(ev.group_id, player_name)
    if err:
        await bot.send(err)
        return

    if is_global:
        is_admin_user = await is_admin(
            server.server_name,
            ev=ev,
            player_name=player_name,
        )
        if not is_admin_user:
            await bot.send("您没有删除全局路径点的权限")
            return

    if not pos_info:
        await bot.send("玩家离线，无法删除玩家路径点")
        return

    ok = await MCQQWaypoint.delete_point(
        server_name=server.server_name,
        point_name=point_name,
        player_name=player_name,
        is_global=is_global,
    )

    if ok:
        await bot.send("删除成功")
    else:
        await bot.send(f"删除失败：未找到路径点 {point_name}")


