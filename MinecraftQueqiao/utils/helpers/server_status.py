import asyncio
import ipaddress
import re
from typing import Any, Optional

from gsuid_core.logger import logger

from ...mcqq_config import mcqq_config
from ...mcqq_database import MCQQServer
from .prefix_match import is_fake_player
from ..utils.format_code import strip_minecraft_formatting_codes

try:
    from mcstatus import JavaServer
except ImportError:
    JavaServer = None  # type: ignore


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
        logger.warning("[MC·服务器状态] 未安装 mcstatus 库，无法进行直连状态查询")
        return None

    try:
        server = await asyncio.wait_for(
            JavaServer.async_lookup(address), timeout=timeout
        )
        status = await asyncio.wait_for(server.async_status(), timeout=timeout)
        return status
    except Exception as e:
        logger.debug(f"[MC·服务器状态] mcstatus 查询 [{address}] 失败: {e}")
        return None


def format_status_lines(name: str, addr: str, status: Any) -> str:
    """格式化 mcstatus 返回的服务器状态"""
    lines = ["服务器状态"]
    if addr and addr != "未配置":
        lines.append(f"地址：{addr}")

    # 直连查询成功
    if status is not None:
        lines.append("状态：在线")

        # 延迟信息
        latency_val = getattr(status, "latency", None)
        if latency_val is not None:
            lines.append(f"延迟：{round(latency_val, 1)}ms")

        version_text = clean_motd(status.version.name)
        if version_text and version_text != "无":
            lines.append(f"版本：{version_text}")

        raw_desc = getattr(status, "description", None) or getattr(
            status, "motd", None
        )
        desc_text = clean_motd(raw_desc)
        if desc_text and desc_text != "无":
            lines.append(f"简介：{desc_text}")

        online_cnt = status.players.online
        max_cnt = status.players.max
        lines.append(f"人数：{online_cnt} / {max_cnt}")

        # 从协议原生 players.sample 提取在线玩家列表并过滤假人
        if online_cnt > 0 and status.players.sample:
            fake_filter = mcqq_config.get_config("fake_player_filter").data
            player_names = [
                p.name
                for p in status.players.sample
                if p and p.name and not is_fake_player(p.name, fake_filter)
            ]
            if player_names:
                lines.append(f"列表：{', '.join(player_names)}")

        return "\n".join(lines)

    # 直连失败/离线
    lines.append("状态：离线")
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
