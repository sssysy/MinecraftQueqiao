import asyncio
import re
from typing import Any, List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_core import send_rcon_command
from ..mcqq_database import MCQQBind, MCQQServer
from ..mcqq_ws import ws_manager
from ..utils.helpers.server_select import resolve_servers

try:
    from mcstatus import JavaServer
except ImportError:
    JavaServer = None  # type: ignore

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


def parse_rcon_list(
    out_str: str,
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """从 RCON list 指令返回文本解析在线人数、最大人数和玩家列表"""
    # 匹配英文：There are X of a max of Y players online: name1, name2
    match_en = re.search(
        r"There are (\d+) of a max(?:imum)? of (\d+) players online(?::\s*(.*))?",
        out_str,
        re.IGNORECASE,
    )
    if match_en:
        online = int(match_en.group(1))
        max_p = int(match_en.group(2))
        names = (match_en.group(3) or "").strip()
        return online, max_p, names if names else "无"

    # 匹配中文：当前有 X/Y 名玩家在线：name1, name2
    match_zh = re.search(
        r"当前有\s*(\d+)\s*(?:/|个玩家在线.*?最大\s*|名玩家在线.*?最大\s*)(\d+)",
        out_str,
    )
    if match_zh:
        online = int(match_zh.group(1))
        max_p = int(match_zh.group(2))
        colon_idx = out_str.find("：")
        if colon_idx == -1:
            colon_idx = out_str.find(":")
        names = out_str[colon_idx + 1 :].strip() if colon_idx != -1 else ""
        return online, max_p, names if names else "无"

    return None, None, None


async def query_mc_status(address: str, timeout: float = 3.5) -> Any:
    """使用 mcstatus 异步查询 Minecraft 服务器直连状态"""
    if JavaServer is None:
        logger.warning("[MCQueQiao] 未安装 mcstatus 库，无法进行直连状态查询")
        return None

    try:
        server = await asyncio.wait_for(
            JavaServer.async_lookup(address), timeout=timeout
        )
        status = await asyncio.wait_for(server.async_status(), timeout=timeout)
        return status
    except Exception as e:
        logger.debug(f"[MCQueQiao] mcstatus 查询 [{address}] 失败: {e}")
        return None


async def get_server_status_text(server: MCQQServer) -> str:
    """通过 mcstatus 查询服务器状态并格式化文本"""
    name = server.display_name or server.server_name
    addr = server.server_address.strip() if server.server_address else ""
    if not addr:
        addr = server.server_name.strip()

    status = await query_mc_status(addr) if addr else None

    # 直连成功
    if status is not None:
        version_text = clean_motd(status.version.name)
        raw_desc = getattr(status, "description", None) or getattr(
            status, "motd", None
        )
        desc_text = clean_motd(raw_desc) or "无"
        online_cnt = status.players.online
        max_cnt = status.players.max

        player_names = []
        if status.players.sample:
            player_names = [
                p.name for p in status.players.sample if p and p.name
            ]

        # 若服务端隐藏了玩家列表，但在 WS 连接状态下可调用 RCON /list 获取玩家名
        if (
            not player_names
            and online_cnt > 0
            and ws_manager.is_connected(server.server_name)
        ):
            succ, out = await send_rcon_command(
                server.server_name, "list", timeout=3.0
            )
            if succ and out:
                _, _, rcon_p = parse_rcon_list(str(out))
                if rcon_p and rcon_p != "无":
                    player_names = [
                        p.strip() for p in rcon_p.split(",") if p.strip()
                    ]

        if player_names:
            player_list_str = ", ".join(player_names)
        elif online_cnt == 0:
            player_list_str = "无"
        else:
            player_list_str = "（已隐藏）"

        lines = [
            f"[{name}] 服务器状态：",
            f"服务器地址：{addr}",
            "在线状态：在线",
            f"游戏版本：{version_text}",
            f"服务器简介：{desc_text}",
            f"玩家数量：{online_cnt} / {max_cnt}",
            f"玩家列表：{player_list_str}",
        ]
        return "\n".join(lines)

    # 直连失败/离线
    lines = [
        f"[{name}] 服务器状态：",
        f"服务器地址：{addr if addr else '未配置'}",
        "在线状态：离线",
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

    # 并发查询所有目标服务器状态
    tasks = [get_server_status_text(server) for server in targets]
    results = await asyncio.gather(*tasks)

    await bot.send("\n\n".join(results))




