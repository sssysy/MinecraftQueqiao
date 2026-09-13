from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from .searcher import search_mcmod

sv_mcmod_search = SV("MC百科MOD搜索")


@sv_mcmod_search.on_command(
    ("mod搜索", "搜索mod"),
    block=True,
    to_ai="""在【我的世界 (Minecraft)】中文模组百科 (MCMOD) 中搜索指定模组的资料与链接。
当用户询问某个 MC 模组怎么玩、怎么下载、模组链接、模组介绍，或询问模组物品/机器/工具如何使用时调用。

注意：仅限 Minecraft (我的世界) 相关模组！严禁用于其他游戏（如原神、星露谷等）、日常非MC软件或普通闲聊。若用户未提及 Minecraft/MC 且非已知 MC 模组，切勿调用本工具。

Args:
    text: 要搜索的模组名称或关键词，例如 "JEI"、"机械动力"、"暮色森林"、"应用能源2"。
""",
)
async def mod_search_command(bot: Bot, ev: Event) -> None:
    keyword = ev.text.strip()
    if not keyword:
        await bot.send("请输入要搜索的模组名称，例如：mcmod搜索 jei")
        return

    result = await search_mcmod(keyword)
    await bot.send(result)
