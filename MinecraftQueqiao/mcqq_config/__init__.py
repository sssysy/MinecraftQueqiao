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
    "show_server_name": GsBoolConfig(
        "群聊显示服务器外显名",
        "把 MC 服务器消息转发到群聊时，是否在消息前显示服务器名",
        True,
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
    "rcon_timeout": GsIntConfig(
        "RCON 超时时间(秒)", "通过 WebSocket 执行 RCON 命令的等待超时秒数", 8
    ),
    "qq_to_mc_enabled": GsBoolConfig(
        "群聊消息转发", "群聊消息转发到 MC 开关", False
    ),
    "qq_to_mc_whitelist": GsListStrConfig(
        "群聊 -> MC 消息白名单",
        "触发转发到 MC 服务器需要的前缀或正则表达式列表。详情参考 README",
        ["mcqq"],
    ),
    "qq_to_mc_blacklist": GsListStrConfig(
        "群聊 -> MC 消息黑名单",
        "屏蔽转发到 MC 服务器的前缀或正则表达式列表。白名单为空时生效。详情参考 README",
        ["mc", "ww"],
    ),
    "mc_to_qq_whitelist": GsListStrConfig(
        "MC -> 群聊 消息白名单",
        "触发转发到群聊需要的前缀或正则表达式列表。详情参考 README",
        [],
    ),
    "mc_to_qq_blacklist": GsListStrConfig(
        "MC -> 群聊 消息黑名单",
        "屏蔽转发到群聊的前缀或正则表达式列表。白名单为空时生效。详情参考 README",
        [],
    ),
}

CONFIG_PATH = get_res_path() / "MinecraftQueqiao" / "config.json"
os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

mcqq_config = StringConfig("MinecraftQueqiao", CONFIG_PATH, CONFIG_DEFAULT)
