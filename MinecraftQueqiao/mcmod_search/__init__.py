from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from .searcher import search_mcmod

sv_mcmod_search = SV("MC百科MOD搜索")


@sv_mcmod_search.on_command(
    ("mod搜索", "搜索mod"),
    block=True,
    to_ai="""在【我的世界 (Minecraft)】中文模组百科 (MCMOD) 中搜索指定模组的资料与链接。

Args:
    text: 要搜索的模组名称（单个参数，空格请用 \\+），例如 "JEI"、"机械动力"。
""",
)
async def mod_search_command(bot: Bot, ev: Event) -> None:
    tokens = split_cmd_args(ev.text)
    if len(tokens) != 1:
        await bot.send(
            "参数传递错误\n用法：mcmod搜索 <模组名>（空格请用 \\+）\n例如：mcmod搜索 机械动力"
        )
        return
    result = await search_mcmod(decode_arg(tokens[0]))
    await bot.send(result)