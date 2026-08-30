from typing import Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQUserBind

sv_mcqq_player_bind = SV("鹊桥玩家绑定")


def _parse_target_and_val(
    ev: Event,
) -> Tuple[str, str, bool]:
    """解析目标用户 ID 与后置参数值。

    Returns:
        (target_user_id, remaining_text, is_for_other)
    """
    raw_text = ev.text.strip()

    # 检查 @用户
    if ev.at_list:
        for at_item in ev.at_list:
            if at_item and str(at_item).strip():
                return str(at_item).strip(), raw_text, True
    elif ev.at and ev.at.strip():
        return ev.at.strip(), raw_text, True

    tokens = raw_text.split(maxsplit=1)
    if len(tokens) >= 2:
        first_tok = tokens[0].lstrip("@")
        if first_tok.isdigit():
            return first_tok, tokens[1].strip(), True

    return ev.user_id, raw_text, False


@sv_mcqq_player_bind.on_prefix("绑定")
async def bind_player_command(bot: Bot, ev: Event) -> None:
    """绑定 Minecraft 游戏角色名。
    用法：
      mc绑定 <游戏ID>
      mc绑定 <@用户/QQ号> <游戏ID> (代绑)
    """
    target_uid, player_name, is_for_other = _parse_target_and_val(ev)

    if is_for_other and ev.user_pm > 3:
        await bot.send("权限不足：只有管理员可以为其他用户绑定 MC 角色")
        return

    player_name = player_name.strip()
    if not player_name:
        await bot.send("用法：mc绑定 <游戏ID> 或 mc绑定 <@用户/QQ号> <游戏ID>")
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
            f"[MCQueQiao] 用户 {target_uid} 的 MC 绑定已更新为: {player_name} (操作人: {ev.user_id})"
        )
        if is_for_other:
            await bot.send(f"绑定更新成功：已将用户 {target_uid} 的 MC 角色更新为 {player_name}")
        else:
            await bot.send(f"绑定更新成功：已将您的 MC 角色更新为 {player_name}")
    else:
        await MCQQUserBind.full_insert_data(
            user_id=target_uid,
            player_name=player_name,
            bot_id=ev.bot_id,
        )
        logger.info(
            f"[MCQueQiao] 用户 {target_uid} 已成功绑定 MC 角色: {player_name} (操作人: {ev.user_id})"
        )
        if is_for_other:
            await bot.send(f"绑定成功：已将用户 {target_uid} 绑定至 MC 角色 {player_name}")
        else:
            await bot.send(f"绑定成功：已将您的账号绑定至 MC 角色 {player_name}")


@sv_mcqq_player_bind.on_prefix(("解绑", "解除绑定"))
async def unbind_player_command(bot: Bot, ev: Event) -> None:
    """解除 Minecraft 游戏角色名绑定。
    用法：
      mc解绑
      mc解绑 <@用户/QQ号> (管理员代解绑)
    """
    raw_text = ev.text.strip()
    target_uid = ev.user_id
    is_for_other = False

    if ev.at_list:
        for at_item in ev.at_list:
            if at_item and str(at_item).strip():
                target_uid = str(at_item).strip()
                is_for_other = True
                break
    elif ev.at and ev.at.strip():
        target_uid = ev.at.strip()
        is_for_other = True
    elif raw_text:
        tok = raw_text.split()[0].lstrip("@")
        if tok.isdigit():
            target_uid = tok
            is_for_other = True

    if is_for_other and ev.user_pm > 3:
        await bot.send("权限不足：只有管理员可以为其他用户解除 MC 绑定")
        return

    existing = await MCQQUserBind.get_by_user_id(target_uid)
    if not existing:
        if is_for_other:
            await bot.send(f"用户 {target_uid} 尚未绑定任何 MC 角色，无需解绑")
        else:
            await bot.send("您尚未绑定任何 MC 角色，无需解绑")
        return

    old_player = existing.player_name
    res = await MCQQUserBind.delete_row(user_id=target_uid)
    if res:
        logger.info(
            f"[MCQueQiao] 已解除用户 {target_uid} 的 MC 角色绑定 ({old_player}) (操作人: {ev.user_id})"
        )
        if is_for_other:
            await bot.send(f"解绑成功：已解除用户 {target_uid} 的 MC 角色绑定 ({old_player})")
        else:
            await bot.send(f"解绑成功：已解除您的 MC 角色绑定 ({old_player})")
    else:
        await bot.send("解绑失败，请稍后重试")


@sv_mcqq_player_bind.on_prefix(("我的绑定", "查看绑定", "查询绑定", "玩家绑定"))
async def check_player_bind_command(bot: Bot, ev: Event) -> None:
    """查询绑定信息。
    用法：
      mc我的绑定
      mc查看绑定 [@用户/QQ号]
    """
    raw_text = ev.text.strip()
    target_uid = ev.user_id
    is_for_other = False

    if ev.at_list:
        for at_item in ev.at_list:
            if at_item and str(at_item).strip():
                target_uid = str(at_item).strip()
                is_for_other = True
                break
    elif ev.at and ev.at.strip():
        target_uid = ev.at.strip()
        is_for_other = True
    elif raw_text:
        tok = raw_text.split()[0].lstrip("@")
        if tok.isdigit():
            target_uid = tok
            is_for_other = True

    existing = await MCQQUserBind.get_by_user_id(target_uid)
    if not existing:
        if is_for_other:
            await bot.send(
                f"用户 {target_uid} 尚未绑定任何 MC 角色\n"
                f"可发送 mc绑定 @用户 <游戏ID> 为其绑定"
            )
        else:
            await bot.send(
                "您尚未绑定任何 MC 角色\n"
                "发送 mc绑定 <游戏ID> 即可进行绑定"
            )
        return

    msg = (
        f"[MC 玩家服务器绑定信息]\n"
        f"• 用户 ID：{target_uid}\n"
        f"• MC 游戏角色：{existing.player_name}"
    )
    await bot.send(msg)
