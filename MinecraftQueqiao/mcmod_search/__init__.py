from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from .searcher import search_mcmod

sv_mcmod_search = SV("MC百科MOD搜索")


@sv_mcmod_search.on_command(("mod搜索", "搜索mod", "mod搜"), block=True)
async def mod_search_command(bot: Bot, ev: Event) -> None:
    keyword = ev.text.strip()
    if not keyword:
        await bot.send("请输入要搜索的模组名称，例如：mcmod搜索 jei")
        return

    result = await search_mcmod(keyword)
    await bot.send(result)
