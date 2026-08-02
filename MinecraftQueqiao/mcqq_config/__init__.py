import os
from typing import Dict

from gsuid_core.data_store import get_res_path
from gsuid_core.utils.plugins_config.gs_config import StringConfig
from gsuid_core.utils.plugins_config.models import GSC, GsBoolConfig, GsIntConfig

CONFIG_DEFAULT: Dict[str, GSC] = {
    "subscribe_player_chat": GsBoolConfig(
        "订阅-玩家聊天", "是否接收玩家聊天事件", True
    ),
    "subscribe_player_join": GsBoolConfig(
        "订阅-玩家加入", "是否接收玩家加入事件", True
    ),
    "subscribe_player_quit": GsBoolConfig(
        "订阅-玩家退出", "是否接收玩家退出事件", True
    ),
    "subscribe_player_death": GsBoolConfig(
        "订阅-玩家死亡", "是否接收玩家死亡事件", True
    ),
    "subscribe_player_command": GsBoolConfig(
        "订阅-玩家命令", "是否接收玩家命令事件", True
    ),
    "subscribe_player_achievement": GsBoolConfig(
        "订阅-玩家成就", "是否接收玩家成就事件", True
    ),
    "reconnect_interval": GsIntConfig(
        "重连间隔(秒)", "WebSocket重连间隔秒数", 10
    ),
    "max_reconnect_times": GsIntConfig(
        "最大重连次数", "0表示无限重连", 5
    ),
}

CONFIG_PATH = get_res_path() / "MinecraftQueqiao" / "config.json"
os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

mcqq_config = StringConfig("MinecraftQueqiao", CONFIG_PATH, CONFIG_DEFAULT)
