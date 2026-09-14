"""游戏内 TPA 互传业务：pending 状态机 + 在线校验 + 组件拼装。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from gsuid_core.logger import logger

from ...mcqq_core.api import send_private_msg, send_rcon_command
from ...mcqq_config import mcqq_config
from ..helpers.component import clickable_command
from ..helpers.ingame_cmd import read_ingame_prefix
from ..helpers.player_online import is_player_online
from ..waypoint.service import tellraw

# key: (server_name, target_player) —— 每个目标同时只保留一条，新的覆盖旧的
_pending: Dict[Tuple[str, str], "TpaRequest"] = {}


def _tpa_timeout() -> float:
    try:
        raw = mcqq_config.get_config("tpa_timeout").data
        return max(10.0, float(raw))
    except Exception:
        return 60.0


def tpa_usage() -> str:
    return (
        "用法: tpa <目标玩家>\n"
        "同意: tpa accept | tpa 同意\n"
        "拒绝: tpa deny | tpa 拒绝"
    )


@dataclass
class TpaRequest:
    server_name: str
    requester: str
    target: str
    created_at: float


def _is_expired(req: TpaRequest, now: Optional[float] = None) -> bool:
    ts = now if now is not None else time.time()
    return ts - req.created_at > _tpa_timeout()


def _pop_pending(server_name: str, target: str) -> Optional[TpaRequest]:
    key = (server_name, target.lower())
    req = _pending.pop(key, None)
    if req is None:
        return None
    if _is_expired(req):
        return None
    return req


def _put_pending(server_name: str, requester: str, target: str) -> TpaRequest:
    key = (server_name, target.lower())
    _pending.pop(key, None)
    req = TpaRequest(
        server_name=server_name,
        requester=requester,
        target=target,
        created_at=time.time(),
    )
    _pending[key] = req
    return req


def build_request_components(requester: str) -> List[dict]:
    prefix = read_ingame_prefix()
    accept_cmd = f"{prefix}tpa accept"
    deny_cmd = f"{prefix}tpa deny"
    timeout = _tpa_timeout()
    return [
        {"text": f"[TPA] {requester} ", "color": "yellow"},
        {"text": "申请传送至您", "color": "white"},
        {"text": "\n"},
        clickable_command(
            "√同意",
            accept_cmd,
            f"点击同意 {requester} 的传送申请",
            color="green",
        ),
        {"text": "  |  ", "color": "gray"},
        clickable_command(
            "×拒绝",
            deny_cmd,
            f"点击拒绝 {requester} 的传送申请",
            color="red",
        ),
        {
            "text": f"\n（{timeout:.0f} 秒内有效，也可输入 {accept_cmd} / {deny_cmd}）",
            "color": "gray",
        },
    ]


async def request_tp(server_name: str, requester: str, target: str) -> Tuple[bool, str]:
    if not target:
        return False, f"未指定目标玩家\n{tpa_usage()}"
    if target.lower() == requester.lower():
        return False, "不能向自己发起传送申请"

    if not await is_player_online(server_name, target):
        return False, f"玩家 {target} 不在线，无法发起传送申请"

    _put_pending(server_name, requester, target)
    components = build_request_components(requester)
    ok, out = await send_private_msg(server_name, target, components)
    if not ok:
        _pending.pop((server_name, target.lower()), None)
        logger.warning(f"[MC·TPA] [{server_name}] 向 {target} 发送申请失败: {out}")
        return False, f"发送传送申请失败: {out}"

    logger.info(f"[MC·TPA] [{server_name}] {requester} → {target} 发起传送申请")
    return True, f"已向 {target} 发送传送申请，等待对方同意"


async def accept_tp(server_name: str, target_player: str) -> Tuple[bool, str]:
    req = _pop_pending(server_name, target_player)
    if req is None:
        return False, "当前没有待处理的传送申请（可能已过期或已被处理）"

    if not await is_player_online(server_name, req.requester):
        return False, f"申请人 {req.requester} 已不在线，传送取消"

    if not await is_player_online(server_name, req.target):
        return False, "您似乎已离线，传送取消"

    ok, out = await send_rcon_command(
        server_name, f"tp {req.requester} {req.target}"
    )
    if not ok:
        logger.warning(
            f"[MC·TPA] [{server_name}] tp {req.requester} → {req.target} 失败: {out}"
        )
        return False, f"传送失败: {out}"

    logger.info(
        f"[MC·TPA] [{server_name}] {req.target} 同意，{req.requester} 传送至 {req.target}"
    )
    await tellraw(
        server_name,
        req.requester,
        f"[TPA] {req.target} 同意了您的传送申请，已传送至对方身边",
        "green",
    )
    return True, f"[TPA] 已将 {req.requester} 传送至您身边"


@dataclass
class DenyResult:
    ok: bool
    to_target: str
    requester: Optional[str] = None
    to_requester: Optional[str] = None


async def deny_tp(server_name: str, target_player: str) -> DenyResult:
    req = _pop_pending(server_name, target_player)
    if req is None:
        return DenyResult(
            ok=False,
            to_target="当前没有待处理的传送申请（可能已过期或已被处理）",
        )
    logger.info(
        f"[MC·TPA] [{server_name}] {req.target} 拒绝 {req.requester} 的传送申请"
    )
    return DenyResult(
        ok=True,
        to_target=f"[TPA] 已拒绝 {req.requester} 的传送申请",
        requester=req.requester,
        to_requester=f"{req.target} 拒绝了您的传送请求",
    )
