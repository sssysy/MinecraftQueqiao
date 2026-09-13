from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.helpers.whisper_helper import handle_whisper

sv_mcqq_whisper = SV("鹊桥私聊指令")


@sv_mcqq_whisper.on_command(
    ("私聊", "私信"),
    block=True,
    to_ai="""向 Minecraft 服务器内正在游玩的指定玩家发送游戏内私信 (tellraw)。
仅当用户明确表示要向服务器内的某位玩家发消息/传话时调用（例如"告诉服务器里的Notch快来联机"、"私信Alex让他来主城"）。

Args:
    text: 格式为 "<目标玩家名或QQ号> <私聊文本内容>"。
          例如 "Notch 来我家拿物资"、"Alex 今晚打末影龙吗"。
""",
)
async def whisper_command(bot: Bot, ev: Event) -> None:
    """向 Minecraft 玩家发送私聊消息（通过 tellraw）。
    用法：
      mc私聊 <@用户 / QQ号 / 游戏ID> <私聊内容>
    """
    await handle_whisper(bot, ev)
