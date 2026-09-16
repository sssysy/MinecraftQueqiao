from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQUserBind
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.ms_auth import get_user_mc_token
from .service import (
    fetch_owned_capes,
    format_cape_list,
    is_none_cape_name,
    match_cape,
    set_active_cape,
)

sv_mc_capes = SV("披风管理", priority=4)

LIST_USAGE = "用法：mc我的披风 / mc披风列表"
SWITCH_USAGE = "用法：mc切换披风 <披风名|无>\n可用 mc披风列表 查看可选名称"


@sv_mc_capes.on_command(("我的披风", "披风列表"), block=True)
async def my_capes_command(bot: Bot, ev: Event) -> None:
    if split_cmd_args(ev.text):
        await bot.send(f"参数传递错误\n{LIST_USAGE}")
        return

    bind = await MCQQUserBind.get_by_user_id(ev.user_id)
    player_name = bind.player_name if bind and bind.player_name else ""

    mc_token, err = await get_user_mc_token(ev.user_id)
    if err or not mc_token:
        await bot.send(err or "获取披风失败")
        return

    capes, err = await fetch_owned_capes(mc_token, with_images=True)
    if err or capes is None:
        await bot.send(err or "获取披风失败")
        return

    if not player_name:
        player_name = ev.user_id

    await bot.send(format_cape_list(player_name, capes))


@sv_mc_capes.on_command("切换披风", block=True)
async def switch_cape_command(bot: Bot, ev: Event) -> None:
    tokens = split_cmd_args(ev.text)
    if not tokens:
        await bot.send(f"参数传递错误\n{SWITCH_USAGE}")
        return

    cape_name = " ".join(decode_arg(t) for t in tokens).strip()
    if not cape_name:
        await bot.send(f"参数传递错误\n{SWITCH_USAGE}")
        return

    mc_token, err = await get_user_mc_token(ev.user_id)
    if err or not mc_token:
        await bot.send(err or "切换披风失败")
        return

    unequip = is_none_cape_name(cape_name)
    cape_id: str | None = None

    if not unequip:
        capes, err = await fetch_owned_capes(mc_token, with_images=False)
        if err or capes is None:
            await bot.send(err or "切换披风失败")
            return
        matched = match_cape(capes, cape_name)
        if matched is None:
            options = [" - 无", *(f" - {c.display_name}" for c in capes)]
            await bot.send(
                f"未找到披风：{cape_name}\n当前可选：\n" + "\n".join(options)
            )
            return
        cape_id = matched.cape_id
        display = matched.display_name
    else:
        display = "无"

    err = await set_active_cape(mc_token, cape_id)
    if err:
        await bot.send(err)
        return

    logger.info(f"[MCQueQiao] 切换披风：{ev.user_id} -> {display}")
    await bot.send(f"已切换披风：{display}")
