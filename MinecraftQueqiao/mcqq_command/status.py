import asyncio
import ipaddress
import re
from typing import Any, List, Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.prefix_match import is_fake_player
from ..utils.helpers.server_select import resolve_servers
from ..utils.utils.format_code import strip_minecraft_formatting_codes

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
    text = strip_minecraft_formatting_codes(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines) if lines else "无"


def is_server_address(addr: str) -> bool:
    """检查字符串是否为 Minecraft 服务器地址（域名、IPv4、IPv6，可包含端口）"""
    addr = addr.strip()
    if not addr or addr.isdigit():
        return False
    if " " in addr:
        return False

    host = addr
    port_str: Optional[str] = None

    if addr.startswith("["):
        m = re.match(r"^\[([a-fA-F0-9:]+)\](?::(\d+))?$", addr)
        if not m:
            return False
        host, port_str = m.group(1), m.group(2)
    elif ":" in addr:
        if addr.count(":") == 1:
            host, port_str = addr.split(":", 1)
        else:
            try:
                ipaddress.IPv6Address(addr)
                return True
            except ValueError:
                return False

    if port_str is not None:
        if not (port_str.isdigit() and 1 <= int(port_str) <= 65535):
            return False

    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass

    if host.lower() == "localhost":
        return True

    labels = host.split(".")
    if len(labels) >= 2:
        label_regex = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
        if all(label_regex.match(l) for l in labels) and re.search(r"[a-zA-Z]", labels[-1]):
            return True

    return False


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


def format_status_lines(name: str, addr: str, status: Any) -> str:
    """格式化 mcstatus 返回的服务器状态"""
    # 直连查询成功
    if status is not None:
        version_text = clean_motd(status.version.name)
        raw_desc = getattr(status, "description", None) or getattr(
            status, "motd", None
        )
        desc_text = clean_motd(raw_desc) or "无"
        online_cnt = status.players.online
        max_cnt = status.players.max

        # 从协议原生 players.sample 提取在线玩家列表并过滤假人
        if status.players.sample:
            fake_filter = mcqq_config.get_config("fake_player_filter").data
            player_names = [
                p.name
                for p in status.players.sample
                if p and p.name and not is_fake_player(p.name, fake_filter)
            ]
            player_list_str = ", ".join(player_names) if player_names else "无"
        elif online_cnt == 0:
            player_list_str = "无"
        else:
            player_list_str = "（已隐藏）"

        # 延迟信息
        latency_val = getattr(status, "latency", None)
        latency_text = (
            f"{round(latency_val, 1)}ms" if latency_val is not None else "未知"
        )

        lines = [
            f"[{name}] 服务器状态：",
            f"服务器地址：{addr}",
            "在线状态：在线",
            f"延迟：{latency_text}",
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


async def get_server_status_text(server: MCQQServer) -> str:
    """通过 mcstatus 原生协议直接获取并格式化服务器状态"""
    name = server.display_name or server.server_name
    addr = server.server_address.strip() if server.server_address else ""
    if not addr:
        addr = server.server_name.strip()

    status = await query_mc_status(addr) if addr else None
    return format_status_lines(name, addr, status)


async def get_address_status_text(addr: str) -> str:
    """通过 mcstatus 原生协议直接获取并格式化指定 IP / 域名的服务器状态"""
    status = await query_mc_status(addr)
    return format_status_lines(addr, addr, status)


@sv_mcqq_status.on_command(
    ("查看", "服务器状态")
)
async def status_command(bot: Bot, ev: Event) -> None:
    text = ev.text.strip()
    servers: Optional[List[MCQQServer]] = None

    if text:
        resolved, err = await resolve_servers(text)
        if resolved:
            servers = resolved
        else:
            if is_server_address(text):
                res = await get_address_status_text(text)
                await bot.send(res)
                return

            if err:
                await bot.send(err)
                return

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




