"""游戏内传送相关触发器。前缀来自配置 ingame_prefix。"""

from __future__ import annotations

from ..helpers.ingame_cmd import ingame
from ...mcqq_core.events import register_ingame_handler
from . import service


@ingame.on_command("tp列表", "传送点列表", "路径点列表")
async def _list(server_name: str, player_name: str, args: str) -> None:
    points = await service.list_points(server_name, player_name)
    if not points:
        await service.tellraw(
            server_name, player_name, "[MC 传送点列表] 暂无可用的传送点", "yellow"
        )
        return
    await service.tellraw(
        server_name, player_name, service.format_point_list(points), "gold"
    )


@ingame.on_command("增加全局tp", "添加全局tp", need_admin=True)
async def _add_global(server_name: str, player_name: str, args: str) -> None:
    if not args:
        await service.tellraw(
            server_name,
            player_name,
            "用法: 增加全局tp <路径点名称> [x] [y] [z]",
            "yellow",
        )
        return
    pos = await service.get_player_pos(server_name, player_name)
    if not pos:
        await service.tellraw(server_name, player_name, "[传送] 读取当前坐标失败", "red")
        return
    ok, msg = await service.add_point(
        server_name, player_name, args, is_global=True, curr_pos=pos
    )
    await service.tellraw(server_name, player_name, f"[传送] {msg}", "green" if ok else "red")


@ingame.on_command("增加tp", "添加tp")
async def _add_personal(server_name: str, player_name: str, args: str) -> None:
    if not args:
        await service.tellraw(
            server_name,
            player_name,
            "用法: 增加tp <路径点名称> [x] [y] [z]",
            "yellow",
        )
        return
    pos = await service.get_player_pos(server_name, player_name)
    if not pos:
        await service.tellraw(server_name, player_name, "[传送] 读取当前坐标失败", "red")
        return
    ok, msg = await service.add_point(
        server_name, player_name, args, is_global=False, curr_pos=pos
    )
    await service.tellraw(server_name, player_name, f"[传送] {msg}", "green" if ok else "red")


@ingame.on_command("删除全局tp", need_admin=True)
async def _del_global(server_name: str, player_name: str, args: str) -> None:
    if not args:
        await service.tellraw(
            server_name, player_name, "用法: 删除全局tp <路径点名称>", "yellow"
        )
        return
    ok, msg = await service.delete_point(
        server_name, player_name, args, is_global=True
    )
    await service.tellraw(server_name, player_name, msg, "green" if ok else "red")


@ingame.on_command("删除tp")
async def _del_personal(server_name: str, player_name: str, args: str) -> None:
    if not args:
        await service.tellraw(
            server_name, player_name, "用法: 删除tp <路径点名称>", "yellow"
        )
        return
    ok, msg = await service.delete_point(
        server_name, player_name, args, is_global=False
    )
    await service.tellraw(server_name, player_name, msg, "green" if ok else "red")


@ingame.on_command("传送", "tp")
async def _teleport(server_name: str, player_name: str, args: str) -> None:
    if not args:
        await service.tellraw(
            server_name, player_name, "用法: 传送 <路径点名称>", "yellow"
        )
        return
    ok, msg = await service.teleport_to(server_name, player_name, args)
    if not ok:
        await service.tellraw(server_name, player_name, f"[传送] {msg}", "red")


async def _dispatch(server_name: str, player_name: str, raw: str) -> bool:
    return await ingame.dispatch(server_name, player_name, raw)


register_ingame_handler(_dispatch)
