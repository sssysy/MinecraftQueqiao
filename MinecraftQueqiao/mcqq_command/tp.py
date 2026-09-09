from typing import List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQBind, MCQQServer, MCQQUserBind, MCQQWaypoint
from ..utils.helpers.admin import is_admin
from ..utils.helpers.waypoint_helper import (
    execute_teleport,
    get_player_pos_and_dimension,
    parse_waypoint_args,
)

sv_mcqq_tp = SV("鹊桥传送指令")


async def _get_bound_player(ev: Event) -> Optional[str]:
    """获取触发者绑定的 MC 角色名"""
    bind = await MCQQUserBind.get_by_user_id(ev.user_id)
    if bind and bind.player_name:
        return bind.player_name.strip()
    return None


async def _resolve_active_server(
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


@sv_mcqq_tp.on_command("tp")
async def teleport_command(bot: Bot, ev: Event) -> None:
    """传送指令: mctp <路径点名称>"""
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用 mctp <路径点名称>")
        return

    player_name = await _get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    point_name = ev.text.strip()
    if not point_name:
        await bot.send("用法：mctp <路径点名称>")
        return

    server, pos_info, err = await _resolve_active_server(ev.group_id, player_name)
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


@sv_mcqq_tp.on_command(("增加全局tp", "添加全局tp"))
async def add_global_waypoint_command(bot: Bot, ev: Event) -> None:
    """增加全局路径点: mc增加全局tp <路径点名称> [x] [y] [z]"""
    await _handle_add_waypoint(bot, ev, is_global=True)


@sv_mcqq_tp.on_command(("增加tp", "添加tp"))
async def add_personal_waypoint_command(bot: Bot, ev: Event) -> None:
    """增加个人路径点: mc增加tp <路径点名称> [x] [y] [z]"""
    await _handle_add_waypoint(bot, ev, is_global=False)


async def _handle_add_waypoint(bot: Bot, ev: Event, is_global: bool) -> None:
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用该指令")
        return

    player_name = await _get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    raw_args = ev.text.strip()
    if not raw_args:
        cmd_name = "增加全局tp" if is_global else "增加tp"
        await bot.send(f"用法：mc{cmd_name} <路径点名称> [x] [y] [z]")
        return

    server, pos_info, err = await _resolve_active_server(ev.group_id, player_name)
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


@sv_mcqq_tp.on_command("删除全局tp")
async def delete_global_waypoint_command(bot: Bot, ev: Event) -> None:
    """删除全局路径点: mc删除全局tp <路径点名称>"""
    await _handle_delete_waypoint(bot, ev, is_global=True)


@sv_mcqq_tp.on_command("删除tp")
async def delete_personal_waypoint_command(bot: Bot, ev: Event) -> None:
    """删除个人路径点: mc删除tp <路径点名称>"""
    await _handle_delete_waypoint(bot, ev, is_global=False)


async def _handle_delete_waypoint(bot: Bot, ev: Event, is_global: bool) -> None:
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用该指令")
        return

    player_name = await _get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    point_name = ev.text.strip()
    if not point_name:
        cmd_name = "删除全局tp" if is_global else "删除tp"
        await bot.send(f"用法：mc{cmd_name} <路径点名称>")
        return

    server, pos_info, err = await _resolve_active_server(ev.group_id, player_name)
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


@sv_mcqq_tp.on_command(("tp列表", "传送列表", "路径点列表"))
async def list_waypoint_command(bot: Bot, ev: Event) -> None:
    """查看路径点列表: mctp列表"""
    if not mcqq_config.get_config("tp_enabled").data:
        await bot.send("未启用传送功能")
        return

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用 mctp列表")
        return

    player_name = await _get_bound_player(ev)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    server, pos_info, err = await _resolve_active_server(ev.group_id, player_name)
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
