from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.helpers.arg_parse import parse_positional
from ..utils.waypoint import qq as waypoint_qq

sv_mcqq_tp = SV("鹊桥传送指令")


@sv_mcqq_tp.on_command(("tp列表", "传送点列表", "路径点列表"), block=True)
async def list_waypoint_command(bot: Bot, ev: Event) -> None:
    await waypoint_qq.handle_list_waypoint(bot, ev)


@sv_mcqq_tp.on_command(
    "tp",
    block=True,
    to_ai="""将当前用户在 Minecraft 游戏内的角色传送到指定路径点/地标。
仅当用户明确要求传送自己时调用。需要用户已绑定游戏角色且正在服务器游戏中。

Args:
    text: 要传送的目标路径点名称（单个参数，空格请用 \\+）。
""",
)
async def teleport_command(bot: Bot, ev: Event) -> None:
    args, err = parse_positional(ev.text, min_args=1, max_args=1, names=("路径点名称",))
    if err:
        await bot.send(err + "\n用法：mctp <路径点名称>")
        return
    await waypoint_qq.handle_teleport(bot, ev, point_name=args[0])


@sv_mcqq_tp.on_command(("增加全局tp", "添加全局tp"), block=True)
async def add_global_waypoint_command(bot: Bot, ev: Event) -> None:
    await waypoint_qq.handle_add_waypoint(bot, ev, is_global=True)


@sv_mcqq_tp.on_command(("增加tp", "添加tp"), block=True)
async def add_personal_waypoint_command(bot: Bot, ev: Event) -> None:
    await waypoint_qq.handle_add_waypoint(bot, ev, is_global=False)


@sv_mcqq_tp.on_command("删除全局tp", block=True)
async def delete_global_waypoint_command(bot: Bot, ev: Event) -> None:
    args, err = parse_positional(ev.text, min_args=1, max_args=1, names=("路径点名称",))
    if err:
        await bot.send(err + "\n用法：mc删除全局tp <路径点名称>")
        return
    await waypoint_qq.handle_delete_waypoint(bot, ev, is_global=True, point_name=args[0])


@sv_mcqq_tp.on_command("删除tp", block=True)
async def delete_personal_waypoint_command(bot: Bot, ev: Event) -> None:
    args, err = parse_positional(ev.text, min_args=1, max_args=1, names=("路径点名称",))
    if err:
        await bot.send(err + "\n用法：mc删除tp <路径点名称>")
        return
    await waypoint_qq.handle_delete_waypoint(bot, ev, is_global=False, point_name=args[0])
