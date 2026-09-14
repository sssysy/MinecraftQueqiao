from typing import Optional

from gsuid_core.ai_core.trigger_bridge import ai_return
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV

from ..mcqq_database import MCQQUserBind
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.user_name import resolve_user_name
from ..utils.helpers.user_select import extract_at_user_ids
from ..utils.render.draw_bind_card import draw_bind_card

sv_mcqq_player_bind = SV("鹊桥玩家绑定", priority=4)


@sv_mcqq_player_bind.on_command("绑定", block=True)
async def bind_player_command(bot: Bot, ev: Event) -> None:
    """mc绑定 <游戏ID> 或 mc绑定 <@用户|QQ号> <游戏ID>"""
    at_users = extract_at_user_ids(ev)
    tokens = split_cmd_args(ev.text)

    target_uid = ev.user_id
    is_for_other = False

    if at_users:
        if len(tokens) != 1:
            await bot.send(
                "参数传递错误\n用法：mc绑定 @用户 <游戏名>（空格请用 \\+）"
            )
            return
        target_uid = at_users[0]
        player_name = decode_arg(tokens[0])
        is_for_other = True
    else:
        if len(tokens) == 1:
            player_name = decode_arg(tokens[0])
        elif len(tokens) == 2:
            raw_target = decode_arg(tokens[0]).lstrip("@")
            if not raw_target.isdigit():
                await bot.send(
                    "参数传递错误\n用法：mc绑定 <游戏名> 或 mc绑定 <QQ号> <游戏名>"
                )
                return
            target_uid = raw_target
            player_name = decode_arg(tokens[1])
            is_for_other = True
        else:
            await bot.send(
                "参数传递错误\n用法：mc绑定 <游戏名> 或 mc绑定 <@用户|QQ号> <游戏名>"
            )
            return

    if is_for_other and ev.user_pm > 3:
        await bot.send("无操作权限！", at=True)
        return

    if not player_name:
        await bot.send("用法：mc绑定 <游戏名>\n如：mc绑定 Notch")
        return

    bound_user = await MCQQUserBind.get_by_player_name(player_name)
    if bound_user and bound_user.user_id != target_uid:
        await bot.send("该玩家已被绑定！")
        return

    existing = await MCQQUserBind.get_by_user_id(target_uid)
    if existing:
        await MCQQUserBind.update_data_by_data(
            {"user_id": target_uid},
            {
                "player_name": player_name,
                "bot_id": ev.bot_id,
            },
        )
        logger.info(f"[MC·游戏绑定] 绑定更新：{target_uid} <-> {player_name}")
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
        logger.info(f"[MC·游戏绑定] 角色绑定：{target_uid} <-> {player_name}")
        if is_for_other:
            await bot.send(f"绑定成功：{target_uid} <-> {player_name}")
        else:
            await bot.send("绑定成功！")


def _resolve_optional_target(ev: Event) -> tuple[str, bool, Optional[str]]:
    """返回 (target_uid, is_for_other, err)。"""
    at_users = extract_at_user_ids(ev)
    tokens = split_cmd_args(ev.text)
    if at_users:
        if len(tokens) > 0:
            return ev.user_id, False, "参数传递错误\n用法：mc解绑 [@用户]"
        return at_users[0], True, None
    if len(tokens) == 0:
        return ev.user_id, False, None
    if len(tokens) == 1:
        raw = decode_arg(tokens[0]).lstrip("@")
        if raw.isdigit():
            return raw, True, None
        return ev.user_id, False, "参数传递错误\n用法：mc解绑 [@用户|QQ号]"
    return ev.user_id, False, "参数传递错误\n用法：mc解绑 [@用户|QQ号]"


@sv_mcqq_player_bind.on_command(("解绑", "解除绑定"), block=True)
async def unbind_player_command(bot: Bot, ev: Event) -> None:
    target_uid, is_for_other, err = _resolve_optional_target(ev)
    if err:
        await bot.send(err)
        return

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


@sv_mcqq_player_bind.on_command(
    ("查看绑定", "查询绑定"),
    block=True,
    to_ai="""查询当前用户或指定用户在 Minecraft 服务器中绑定的游戏角色名及绑定信息。
当用户询问"我绑定了什么游戏ID"、"我绑定的MC名字叫什么"、"查看我的绑定卡片"或查询某人绑定时调用。

Args:
    text: 可选。要查询的目标用户（QQ号或@提及）。留空或空字符串则默认查询当前发送者自己。
""",
)
async def check_player_bind_command(bot: Bot, ev: Event) -> None:
    """mc查看绑定 / mc查看绑定 [@用户|QQ号]"""
    at_users = extract_at_user_ids(ev)
    tokens = split_cmd_args(ev.text)

    if at_users:
        if tokens:
            await bot.send("参数传递错误\n用法：mc查看绑定 [@用户]")
            return
        target_uid = at_users[0]
        is_for_other = True
    elif len(tokens) == 0:
        target_uid = ev.user_id
        is_for_other = False
    elif len(tokens) == 1:
        raw = decode_arg(tokens[0]).lstrip("@")
        if not raw.isdigit():
            await bot.send("参数传递错误\n用法：mc查看绑定 [@用户|QQ号]")
            return
        target_uid = raw
        is_for_other = True
    else:
        await bot.send("参数传递错误\n用法：mc查看绑定 [@用户|QQ号]")
        return

    existing = await MCQQUserBind.get_by_user_id(target_uid)
    if not existing:
        await bot.send("未查找到相关绑定！")
        return

    if is_for_other or target_uid != ev.user_id:
        user_name = await resolve_user_name(
            ev.bot_id, target_uid, ev.group_id or ""
        )
        if not user_name:
            user_name = target_uid
    else:
        user_name = (
            ev.sender.get("nickname", "") if isinstance(ev.sender, dict) else ""
        ) or target_uid

    ai_return(
        f"绑定信息：用户 {user_name} (ID: {target_uid}) "
        f"当前绑定的 Minecraft 角色名为：{existing.player_name}"
    )

    try:
        img_bytes = await draw_bind_card(
            player_name=existing.player_name,
            user_name=str(user_name),
        )
    except Exception as e:
        logger.warning(f"[MCQueQiao] 绘制绑定卡片失败，回退文本: {e}")
        msg = (
            f"绑定信息：\n"
            f" - 用户名 | {user_name}\n"
            f" - 游戏名 | {existing.player_name}"
        )
        await bot.send(msg)
        return

    await bot.send(MessageSegment.image(img_bytes))
