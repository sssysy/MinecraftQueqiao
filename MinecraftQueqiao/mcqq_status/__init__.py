"""插件额外信息：向 gsuid_core「插件额外信息」区块上报三项统计。"""

from pathlib import Path

from PIL import Image

from gsuid_core.status.plugin_status import register_status

from ..mcqq_core import ws_manager
from ..mcqq_database import MCQQServer, MCQQUserBind

ICON = Path(__file__).parent.parent.parent / "ICON.png"


async def get_connected_server_num() -> int:
    """当前已建立鹊桥 WebSocket 连接的服务器数量"""
    return len(ws_manager.get_connected_servers())


async def get_enabled_server_num() -> int:
    """已启用的服务器数量"""
    return len(await MCQQServer.get_all_enabled())


async def get_bind_player_num() -> int:
    """已绑定游戏账号的玩家数量"""
    return len(await MCQQUserBind.get_all())


register_status(
    Image.open(ICON).convert("RGBA"),
    "MinecraftQueqiao",
    {
        "连接服务器": get_connected_server_num,
        "启用服务器": get_enabled_server_num,
        "绑定玩家数": get_bind_player_num,
    },
)
