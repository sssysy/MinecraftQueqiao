from __future__ import annotations

CAPE_NAME_MAP: dict[str, str] = {
    "Migrator": "迁移者披风",
    "MapMaker": "Realms 地图制作者披风",
    "Moderator": "Mojira 管理员披风",
    "Translator-Chinese": "Crowdin 中文翻译者披风",
    "Translator": "Crowdin 翻译者披风",
    "Cobalt": "Cobalt 披风",
    "Vanilla": "原版披风",
    "Minecon2011": "Minecon 2011 参与者披风",
    "Minecon2012": "Minecon 2012 参与者披风",
    "Minecon2013": "Minecon 2013 参与者披风",
    "Minecon2015": "Minecon 2015 参与者披风",
    "Minecon2016": "Minecon 2016 参与者披风",
    "Cherry Blossom": "樱花披风",
    "15th Anniversary": "15 周年纪念披风",
    "Purple Heart": "紫色心形披风",
    "Follower's": "追随者披风",
    "MCC 15th Year": "MCC 15 周年披风",
    "Minecraft Experience": "村民救援披风",
    "Mojang Office": "Mojang 办公室披风",
    "Home": "家园披风",
    "Menace": "入侵披风",
    "Yearn": "渴望披风",
    "Common": "普通披风",
    "Pan": "薄煎饼披风",
    "Founder's": "创始人披风",
    "Copper": "铜披风",
    "Zombie Horse": "僵尸马披风",
    "Builder": "建造者披风",
    "Crafter": "工匠披风",
    "Moonlight Trail": "月光小径披风",
    "Scrolls Champion": "Scrolls 冠军披风",
    "Mojang": "Mojang 披风",
}


def get_display_name(alias: str) -> str:
    """未知 alias 原样返回英文。"""
    return CAPE_NAME_MAP.get(alias, alias)
