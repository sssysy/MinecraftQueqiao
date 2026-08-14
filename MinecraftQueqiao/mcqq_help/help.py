import json
from pathlib import Path
from typing import Dict

from PIL import Image

from gsuid_core.sv import get_plugin_available_prefix
from gsuid_core.help.draw_new_plugin_help import get_new_help
from gsuid_core.help.model import PluginHelp

from ..version import MCQQVersion

ICON = Path(__file__).parent.parent.parent / "ICON.png"
HELP_DATA = Path(__file__).parent / "help.json"
ICON_PATH = Path(__file__).parent / "icon_path"
TEXT_PATH = Path(__file__).parent / "texture2d"


def get_footer() -> Image.Image:
    return Image.open(TEXT_PATH / "footer.png")


def get_help_data() -> Dict[str, PluginHelp]:
    if not HELP_DATA.exists():
        return {}
    with open(HELP_DATA, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


async def get_help(pm: int):
    prefix = get_plugin_available_prefix("MinecraftQueqiao")
    return await get_new_help(
        plugin_name="MinecraftQueqiao",
        plugin_info={f"v{MCQQVersion}": ""},
        plugin_icon=Image.open(ICON),
        plugin_help=get_help_data(),
        plugin_prefix=prefix,
        help_mode="dark",
        banner_bg=Image.open(TEXT_PATH / "banner_bg.jpg"),
        banner_sub_text="连接QQ与Minecraft的鹊桥",
        help_bg=Image.open(TEXT_PATH / "bg.jpg"),
        cag_bg=Image.open(TEXT_PATH / "cag_bg.png"),
        item_bg=Image.open(TEXT_PATH / "item.png"),
        icon_path=ICON_PATH,
        footer=get_footer(),
        enable_cache=True,
        column=3,
        pm=pm,
    )
