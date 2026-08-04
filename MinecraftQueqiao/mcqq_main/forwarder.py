from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import Plugins, SV

from mcqq_config import mcqq_config
from mcqq_database import MCQQBind

sv_mcqq_chat = SV("MC鹊桥聊天转发")


@sv_mcqq_chat.on_message()
async def qq_to_mc_forward(bot: Bot, ev: Event) -> None:
    """QQ群消息转发到MC服务器。

    当 qq_to_mc_enabled 开关开启时，将QQ群内的聊天消息
    转发到与该群关联的Minecraft服务器。
    """
    # 延迟导入，避免 mcqq_core <-> mcqq_main 循环导入
    from mcqq_core import send_broadcast

    if not mcqq_config.get_config("qq_to_mc_enabled").data:
        return

    # 只处理群消息
    if ev.user_type != "group" or not ev.group_id:
        return

    # 获取原始文本内容
    raw_text = ev.raw_text.strip()
    if not raw_text:
        return

    # 检查触发前缀
    prefix = mcqq_config.get_config("qq_to_mc_prefix").data
    if prefix:
        if not raw_text.startswith(prefix):
            return
        raw_text = raw_text[len(prefix):].strip()
        if not raw_text:
            return

    # 查询与当前群号绑定的MC服务器
    binds = await MCQQBind.get_by_group_id(ev.group_id)
    if not binds:
        logger.debug(
            f"[MCQueQiao] 群 {ev.group_id} 未绑定任何MC服务器，跳过转发"
        )
        return

    # 获取发送者昵称
    sender_nickname = ev.sender.get("nickname", "") or ev.user_id
    group_id = ev.group_id
    formatted = f"[{group_id}] <{sender_nickname}> {raw_text}"

    for bind in binds:
        success = await send_broadcast(bind.server_name, formatted)
        if success:
            logger.info(
                f"[MCQueQiao] 已将QQ消息转发到服务器 "
                f"'{bind.server_name}': {formatted}"
            )
        else:
            logger.error(
                f"[MCQueQiao] 转发QQ消息到服务器 "
                f"'{bind.server_name}' 失败"
            )