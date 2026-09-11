from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.helpers.whisper_helper import handle_whisper

sv_mcqq_whisper = SV("鹊桥私聊指令")


@sv_mcqq_whisper.on_command(("私聊", "私信"), block=True)
async def whisper_command(bot: Bot, ev: Event) -> None:
    """向 Minecraft 玩家发送私聊消息（通过 tellraw）。
    用法：
      mc私聊 <@用户 / QQ号 / 游戏ID> <私聊内容>
    """
    await handle_whisper(bot, ev)
