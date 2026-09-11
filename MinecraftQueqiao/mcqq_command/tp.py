from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.helpers.waypoint_helper import (
    handle_add_waypoint,
    handle_delete_waypoint,
    handle_list_waypoint,
    handle_teleport,
)

sv_mcqq_tp = SV("鹊桥传送指令")


@sv_mcqq_tp.on_command(("tp列表", "传送点列表", "路径点列表"), block=True)
async def list_waypoint_command(bot: Bot, ev: Event) -> None:
    """查看路径点列表: mctp列表"""
    await handle_list_waypoint(bot, ev)


@sv_mcqq_tp.on_command("tp", block=True)
async def teleport_command(bot: Bot, ev: Event) -> None:
    """传送指令: mctp <路径点名称>"""
    await handle_teleport(bot, ev)


@sv_mcqq_tp.on_command(("增加全局tp", "添加全局tp"), block=True)
async def add_global_waypoint_command(bot: Bot, ev: Event) -> None:
    """增加全局路径点: mc增加全局tp <路径点名称> [x] [y] [z]"""
    await handle_add_waypoint(bot, ev, is_global=True)


@sv_mcqq_tp.on_command(("增加tp", "添加tp"), block=True)
async def add_personal_waypoint_command(bot: Bot, ev: Event) -> None:
    """增加个人路径点: mc增加tp <路径点名称> [x] [y] [z]"""
    await handle_add_waypoint(bot, ev, is_global=False)


@sv_mcqq_tp.on_command("删除全局tp", block=True)
async def delete_global_waypoint_command(bot: Bot, ev: Event) -> None:
    """删除全局路径点: mc删除全局tp <路径点名称>"""
    await handle_delete_waypoint(bot, ev, is_global=True)


@sv_mcqq_tp.on_command("删除tp", block=True)
async def delete_personal_waypoint_command(bot: Bot, ev: Event) -> None:
    """删除个人路径点: mc删除tp <路径点名称>"""
    await handle_delete_waypoint(bot, ev, is_global=False)
