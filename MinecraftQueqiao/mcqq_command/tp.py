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


@sv_mcqq_tp.on_command(
    "tp",
    block=True,
    to_ai="""将当前用户在 Minecraft 游戏内的角色传送到指定路径点/地标。
仅当用户明确要求传送自己时调用（如"把我传送到家"、"传送到主城"、"tp 刷铁机"）。
闲聊、询问传送机制或单纯讨论地名时切勿调用！需要用户已绑定游戏角色且正在服务器游戏中。

Args:
    text: 要传送的目标路径点名称。例如 "家"、"主城"、"刷铁机"。
""",
)
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
