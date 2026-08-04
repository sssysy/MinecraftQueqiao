import os
from typing import Dict

from gsuid_core.data_store import get_res_path
from gsuid_core.utils.plugins_config.gs_config import StringConfig
from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsBoolConfig,
    GsIntConfig,
    GsListStrConfig,
    GsStrConfig,
)

CONFIG_DEFAULT: Dict[str, GSC] = {
    "mc_to_qq_enabled": GsBoolConfig(
        "接收 MC 事件", "把 MC 服务器事件转发到绑定的其他平台。需要开启对应订阅事件", True
    ),
    "qq_to_mc_enabled": GsBoolConfig(
        "发送消息到 MC", "把绑定的其他平台消息转发到 MC 服务器", False
    ),
    "subscribe_events": GsListStrConfig(
        "订阅事件",
        "需要订阅的玩家事件，可多选",
        [
            "玩家聊天",
            "玩家加入",
            "玩家退出",
        ],
        options=[
            "玩家聊天",
            "玩家加入",
            "玩家退出",
            "玩家死亡",
            "玩家命令",
            "玩家成就",
        ],
    ),
    "reconnect_interval": GsIntConfig(
        "重连间隔(秒)", "WebSocket重连间隔秒数", 10
    ),
    "max_reconnect_times": GsIntConfig(
        "最大重连次数", "0表示无限重连", 5
    ),
    "qq_to_mc_prefix": GsStrConfig(
        "转发到 MC 服务器的消息前缀", "触发转发到 MC 服务器需要的前缀，留空则全部转发", "mc说"
    ),
    "mc_to_qq_prefix": GsStrConfig(
        "转发到群聊的消息前缀", "触发转发到群聊需要的前缀，留空则全部转发", ""
    ),
}

CONFIG_PATH = get_res_path() / "MinecraftQueqiao" / "config.json"
os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

mcqq_config = StringConfig("MinecraftQueqiao", CONFIG_PATH, CONFIG_DEFAULT)
