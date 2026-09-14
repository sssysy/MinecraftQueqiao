"""QQ 端传送 handler：前置检查 + 调 service。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from gsuid_core.ai_core.trigger_bridge import ai_return
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ...mcqq_config import mcqq_config
from ...mcqq_database import MCQQServer
from ..helpers.admin import is_admin
from . import service


@dataclass
class TpContext:
    bot: Bot
    ev: Event
    player_name: str
    server: MCQQServer
    pos: Optional[Tuple[float, float, float, str]]


async def resolve_tp_context(
    bot: Bot,
    ev: Event,
    *,
    need_online: bool = True,
) -> Optional[TpContext]:
    """失败时已发送错误文案并返回 None。"""
    if not service.tp_enabled():
        await bot.send("未启用传送功能")
        return None

    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用传送指令")
        return None

    player_name = await service.get_bound_player_by_user_id(ev.user_id)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return None

    server, pos, err = await service.resolve_active_server(
        ev.group_id, player_name, need_pos=need_online
    )
    if err:
        await bot.send(err)
        return None
    if server is None:
        await bot.send("无可用服务器")
        return None

    if need_online and pos is None:
        await bot.send("玩家离线，无法执行")
        return None

    return TpContext(bot=bot, ev=ev, player_name=player_name, server=server, pos=pos)


async def handle_list_waypoint(bot: Bot, ev: Event) -> None:
    ctx = await resolve_tp_context(bot, ev, need_online=False)
    if not ctx:
        return
    points = await service.list_points(ctx.server.server_name, ctx.player_name)
    await bot.send(service.format_point_list(points))


async def handle_teleport(bot: Bot, ev: Event) -> None:
    ctx = await resolve_tp_context(bot, ev, need_online=True)
    if not ctx:
        return

    point_name = ev.text.strip()
    if not point_name:
        await bot.send("用法：mctp <路径点名称>")
        return

    ok, msg = await service.teleport_to(
        ctx.server.server_name, ctx.player_name, point_name
    )
    if not ok:
        await bot.send(msg)
        return
    ai_return(
        f"传送成功：已将玩家 {ctx.player_name} 传送至路径点 {point_name}"
    )


async def handle_add_waypoint(bot: Bot, ev: Event, is_global: bool) -> None:
    if not service.tp_enabled():
        await bot.send("未启用传送功能")
        return
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用该指令")
        return

    player_name = await service.get_bound_player_by_user_id(ev.user_id)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    raw_args = ev.text.strip()
    if not raw_args:
        cmd_name = "增加全局tp" if is_global else "增加tp"
        await bot.send(f"用法：mc{cmd_name} <路径点名称> [x] [y] [z]")
        return

    server, pos, err = await service.resolve_active_server(
        ev.group_id, player_name, need_pos=True
    )
    if err:
        await bot.send(err)
        return
    assert server is not None

    if is_global:
        if not await is_admin(server.server_name, ev=ev, player_name=player_name):
            await bot.send("您没有添加全局路径点的权限")
            return

    if pos is None:
        await bot.send("玩家离线，无法获取玩家位置，执行失败")
        return

    ok, msg = await service.add_point(
        server.server_name,
        player_name,
        raw_args,
        is_global=is_global,
        curr_pos=pos,
    )
    await bot.send(msg if ok else f"参数错误！\n{msg}")


async def handle_delete_waypoint(bot: Bot, ev: Event, is_global: bool) -> None:
    if not service.tp_enabled():
        await bot.send("未启用传送功能")
        return
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在绑定的群聊中使用该指令")
        return

    player_name = await service.get_bound_player_by_user_id(ev.user_id)
    if not player_name:
        await bot.send("您尚未绑定 MC 游戏角色，请先发送 mc绑定 <游戏ID> 进行绑定")
        return

    point_name = ev.text.strip()
    if not point_name:
        cmd_name = "删除全局tp" if is_global else "删除tp"
        await bot.send(f"用法：mc{cmd_name} <路径点名称>")
        return

    server, _, err = await service.resolve_active_server(
        ev.group_id, player_name, need_pos=False
    )
    if err:
        await bot.send(err)
        return
    assert server is not None

    if is_global:
        if not await is_admin(server.server_name, ev=ev, player_name=player_name):
            await bot.send("您没有删除全局路径点的权限")
            return

    ok, msg = await service.delete_point(
        server.server_name, player_name, point_name, is_global=is_global
    )
    await bot.send(msg)
