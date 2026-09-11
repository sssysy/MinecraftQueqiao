from typing import Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQUserBind
from ..utils.helpers.user_select import extract_single_target_user

sv_mcqq_player_bind = SV("鹊桥玩家绑定", priority=4)


@sv_mcqq_player_bind.on_command("绑定", block=True)
async def bind_player_command(bot: Bot, ev: Event) -> None:
    """绑定 Minecraft 游戏角色名。
    用法：
      mc绑定 <游戏ID>
      mc绑定 <@用户/QQ号> <游戏ID> (代绑)
    """
    target_uid, player_name, is_for_other = extract_single_target_user(
        ev, default_to_sender=True, allow_bare_target=False
    )
    if not target_uid:
        target_uid = ev.user_id

    if is_for_other and ev.user_pm > 3:
        await bot.send("无操作权限！", at=True)
        return

    player_name = player_name.strip()
    if not player_name:
        await bot.send("用法：mc绑定 <游戏名>\n如：mc绑定 Notch")
        return

    # 查重：阻止同一 MC 角色名绑定到多个用户
    bound_user = await MCQQUserBind.get_by_player_name(player_name)
    if bound_user and bound_user.user_id != target_uid:
        await bot.send("该玩家已被绑定！")
        return

    # 查询现有绑定
    existing = await MCQQUserBind.get_by_user_id(target_uid)
    if existing:
        await MCQQUserBind.update_data_by_data(
            {"user_id": target_uid},
            {
                "player_name": player_name,
                "bot_id": ev.bot_id,
            },
        )
        logger.info(
            f"[MC·游戏绑定] 绑定更新：{target_uid} <-> {player_name}"
        )
        if is_for_other:
            await bot.send(f"更新绑定成功：{target_uid} <-> {player_name}")
        else:
            await bot.send("更新绑定成功！")
    else:
        await MCQQUserBind.full_insert_data(
            user_id=target_uid,
            player_name=player_name,
            bot_id=ev.bot_id,
        )
        logger.info(
            f"[MC·游戏绑定] 角色绑定：{target_uid} <-> {player_name}"
        )
        if is_for_other:
            await bot.send(f"绑定成功：{target_uid} <-> {player_name}")
        else:
            await bot.send("绑定成功！")


@sv_mcqq_player_bind.on_command(("解绑", "解除绑定"), block=True)
async def unbind_player_command(bot: Bot, ev: Event) -> None:
    """解除 Minecraft 游戏角色名绑定。
    用法：
      mc解绑
      mc解绑 <@用户/QQ号> (管理员代解绑)
    """
    target_uid, _, is_for_other = extract_single_target_user(
        ev, default_to_sender=True, allow_bare_target=True
    )
    if not target_uid:
        target_uid = ev.user_id

    if is_for_other and ev.user_pm > 3:
        await bot.send("无操作权限！", at=True)
        return

    existing = await MCQQUserBind.get_by_user_id(target_uid)
    if not existing:
        await bot.send("未查找到相关绑定！")
        return

    old_player = existing.player_name
    res = await MCQQUserBind.delete_row(user_id=target_uid)
    if res:
        logger.info(
            f"[MC·游戏绑定] 角色解绑：{target_uid} <-/-> {old_player}"
        )
        if is_for_other:
            await bot.send(f"解绑成功：{target_uid} <-/-> {old_player}")
        else:
            await bot.send("解绑成功！")
    else:
        await bot.send("解绑失败，检查控制台！")


@sv_mcqq_player_bind.on_command(("查看绑定", "查询绑定"), block=True)
async def check_player_bind_command(bot: Bot, ev: Event) -> None:
    """查询绑定信息。
    用法：
      mc我的绑定
      mc查看绑定 [@用户/QQ号]
    """
    target_uid, _, is_for_other = extract_single_target_user(
        ev, default_to_sender=True, allow_bare_target=True
    )
    if not target_uid:
        target_uid = ev.user_id

    existing = await MCQQUserBind.get_by_user_id(target_uid)
    if not existing:
        await bot.send("未查找到相关绑定！")
        return

    msg = (
        f"绑定信息：\n"
        f" - 用户名 | {target_uid}\n"
        f" - 游戏名 | {existing.player_name}"
    )
    await bot.send(msg)
