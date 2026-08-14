from PIL import Image
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV
from gsuid_core.logger import logger
from gsuid_core.help.utils import register_help

from .help import ICON, get_help

sv_mcqq_help = SV("鹊桥帮助", priority=5)


@sv_mcqq_help.on_fullmatch("帮助", block=True,)
async def send_help_img(bot: Bot, ev: Event):
    logger.info("开始执行[鹊桥帮助]")
    await bot.send(await get_help(ev.user_pm))


register_help(
    "MinecraftQueqiao",
    "mc帮助",
    Image.open(ICON),
)
