from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from .login_service import logout, start_device_login

sv_mc_login = SV("微软账号登录", priority=4)


@sv_mc_login.on_command("登录", block=True)
async def ms_login_command(bot: Bot, ev: Event) -> None:
    await start_device_login(bot, ev)


@sv_mc_login.on_command("退出登录", block=True)
async def ms_logout_command(bot: Bot, ev: Event) -> None:
    msg = await logout(ev.user_id)
    await bot.send(msg)
