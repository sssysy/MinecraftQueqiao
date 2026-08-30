import asyncio
import re
from typing import Any, Dict, List, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core import get_server_status_api
from ..mcqq_database import MCQQBind, MCQQServer
from ..mcqq_ws import ws_manager
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_status = SV("鹊桥服务器状态指令")


def clean_motd(motd: Any) -> str:
    """清理 MOTD 中的 Minecraft 颜色代码和多余换行与空格"""
    if motd is None:
        return ""
    if hasattr(motd, "to_plain"):
        text = motd.to_plain()
    elif isinstance(motd, dict):
        text = motd.get("text", "") or ""
    elif isinstance(motd, list):
        text = "".join(clean_motd(item) for item in motd)
    else:
        text = str(motd)

    # 去除 § 与 \u00a7 颜色格式化代码
    text = re.sub(r"[§\u00a7][0-9a-fk-orA-FK-OR]", "", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines) if lines else "无"


async def get_server_status_text(server: MCQQServer) -> str:
    """通过鹊桥原生 get_status API 获取并格式化服务器状态"""
    name = server.display_name or server.server_name
    addr = server.server_address.strip() if server.server_address else ""

    # 检查反向 WebSocket 是否已连接
    if not ws_manager.is_connected(server.server_name):
        lines = [
            f"[{name}] 服务器状态：",
            f"服务器地址：{addr if addr else server.server_name}",
            "在线状态：离线",
        ]
        return "\n".join(lines)

    # 调用原生 get_status API
    success, data = await get_server_status_api(server.server_name, timeout=4.0)
    if not success or not isinstance(data, dict):
        lines = [
            f"[{name}] 服务器状态：",
            f"服务器地址：{addr if addr else server.server_name}",
            "在线状态：离线",
        ]
        return "\n".join(lines)

    # 服务器地址
    display_addr = (
        addr
        or data.get("address")
        or data.get("ip")
        or data.get("host")
        or server.server_name
    )

    # 游戏版本
    version_val = (
        data.get("version")
        or data.get("game_version")
        or data.get("version_name")
        or "未知"
    )
    if isinstance(version_val, dict):
        version_val = version_val.get("name", "未知")
    version_text = clean_motd(version_val)

    # 服务器简介
    motd_val = data.get("motd") or data.get("description") or "无"
    desc_text = clean_motd(motd_val)

    # 在线人数与最大人数
    online_p = (
        data.get("online_players")
        or data.get("current_players")
        or data.get("online")
    )
    max_p = data.get("max_players") or data.get("max")

    # 玩家列表
    raw_players = data.get("players") or data.get("player_list") or []
    player_names = []
    if isinstance(raw_players, list):
        for p in raw_players:
            if isinstance(p, str) and p.strip():
                player_names.append(p.strip())
            elif isinstance(p, dict) and p.get("name"):
                player_names.append(str(p["name"]).strip())
            elif isinstance(p, dict) and p.get("nickname"):
                player_names.append(str(p["nickname"]).strip())

    if online_p is None and player_names:
        online_p = len(player_names)
    elif online_p is None and isinstance(raw_players, (int, float)):
        online_p = int(raw_players)

    if online_p is not None and max_p is not None:
        players_count_str = f"{online_p} / {max_p}"
    elif online_p is not None:
        players_count_str = f"{online_p}"
    else:
        players_count_str = "未知"

    if player_names:
        player_list_str = ", ".join(player_names)
    elif online_p == 0:
        player_list_str = "无"
    else:
        player_list_str = "无"

    lines = [
        f"[{name}] 服务器状态：",
        f"服务器地址：{display_addr}",
        "在线状态：在线",
        f"游戏版本：{version_text}",
        f"服务器简介：{desc_text}",
        f"玩家数量：{players_count_str}",
        f"玩家列表：{player_list_str}",
    ]
    return "\n".join(lines)


@sv_mcqq_status.on_command(
    ("查看", "查看服务器", "查询服务器", "服务器信息", "服务器状态")
)
async def status_command(bot: Bot, ev: Event) -> None:
    text = ev.text.strip()
    servers: Optional[List[MCQQServer]] = None

    if text:
        resolved, err = await resolve_servers(text)
        if err:
            await bot.send(err)
            return
        servers = resolved

    if servers is not None:
        targets = servers
    elif ev.user_type == "group" and ev.group_id:
        binds = await MCQQBind.get_by_group_id(ev.group_id)
        if not binds:
            await bot.send(
                "当前群未绑定任何服务器，请指定服务器（例如：mc查看 生存服）或先执行 mc群服绑定"
            )
            return
        targets = []
        for bind in binds:
            server = await MCQQServer.get_by_name(bind.server_name)
            if server:
                targets.append(server)
        if not targets:
            await bot.send("未找到当前群绑定的有效服务器")
            return
    else:
        targets = await MCQQServer.get_all_enabled()
        if not targets:
            await bot.send("当前未配置任何启用的 MC 服务器")
            return

    # 并发请求各服务器原生状态
    tasks = [get_server_status_text(server) for server in targets]
    results = await asyncio.gather(*tasks)

    await bot.send("\n\n".join(results))




