from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional, Set

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQUserBind
from ..utils.helpers.ms_auth import (
    DeviceCodeSession,
    ms_token_to_mc_profile,
    poll_for_ms_token,
    request_device_code,
)

# 正在等待授权的用户，防止重复发起
_pending_login_users: Set[str] = set()
_pending_tasks: Dict[str, asyncio.Task[None]] = {}


def _get_client_id() -> Optional[str]:
    client_id = str(mcqq_config.get_config("ms_client_id").data or "").strip()
    return client_id or None


def _get_login_timeout() -> int:
    try:
        return max(int(mcqq_config.get_config("ms_login_timeout").data or 900), 60)
    except (TypeError, ValueError):
        return 900


async def start_device_login(bot: Bot, ev: Event) -> None:
    """mc登录 入口：校验配置 → 申请设备码 → 回复 → 后台轮询。"""
    client_id = _get_client_id()
    if not client_id:
        await bot.send(
            "尚未配置微软应用客户端 ID\n请在插件配置中填写 ms_client_id 后重试"
        )
        return

    user_id = ev.user_id
    if user_id in _pending_login_users:
        await bot.send("你已有一项登录正在进行，请先完成或等待超时")
        return

    session, err = await request_device_code(client_id)
    if err or session is None:
        await bot.send(err or "请求微软设备代码失败，请稍后重试")
        return

    _pending_login_users.add(user_id)
    task = asyncio.create_task(
        _poll_and_complete(
            bot=bot,
            user_id=user_id,
            bot_id=ev.bot_id,
            client_id=client_id,
            session=session,
        )
    )
    _pending_tasks[user_id] = task
    task.add_done_callback(lambda t, uid=user_id: _on_task_done(uid, t))

    await bot.send(
        f"请访问 {session.verification_uri} 后输入验证码 {session.user_code} 进行登录！\n"
        f"验证码约 {session.expires_in // 60} 分钟内有效，请勿泄露给他人。"
    )


def _on_task_done(user_id: str, task: asyncio.Task[None]) -> None:
    _pending_login_users.discard(user_id)
    _pending_tasks.pop(user_id, None)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(f"[MC·微软登录] 用户 {user_id} 登录任务异常: {exc!r}")


async def _poll_and_complete(
    *,
    bot: Bot,
    user_id: str,
    bot_id: str,
    client_id: str,
    session: DeviceCodeSession,
) -> None:
    """后台：轮询授权 → 认证链 → 写库 → 回复结果。"""
    timeout = min(session.expires_in, _get_login_timeout())
    ms_payload, err = await poll_for_ms_token(
        client_id=client_id,
        device_code=session.device_code,
        interval=session.interval,
        timeout=timeout,
    )
    if err or not ms_payload:
        await bot.send(err or "登录失败，请稍后重试")
        return

    ms_access = ms_payload.get("access_token")
    ms_refresh = ms_payload.get("refresh_token")
    if not ms_access or not ms_refresh:
        await bot.send("微软登录响应异常，请稍后重试")
        return

    profile, err = await ms_token_to_mc_profile(ms_access, ms_refresh)
    if err or profile is None:
        await bot.send(err or "登录失败，请稍后重试")
        return

    token_payload: Dict[str, Any] = {
        "ms_refresh_token": profile.ms_refresh_token,
        "mc_access_token": profile.mc_access_token,
        "expires_at": time.time() + profile.expires_in - 300,
    }
    token_json = json.dumps(token_payload, ensure_ascii=False)

    try:
        existing = await MCQQUserBind.get_by_user_id(user_id)
        row = {
            "user_id": user_id,
            "player_name": profile.player_name,
            "bot_id": bot_id,
            "token": token_json,
        }
        if existing:
            await MCQQUserBind.update_data_by_data({"user_id": user_id}, row)
        else:
            await MCQQUserBind.full_insert_data(**row)
    except Exception as e:
        logger.error(f"[MC·微软登录] 写库失败 user={user_id}: {e!r}")
        await bot.send("登录成功但保存失败，请检查控制台后重试")
        return

    logger.info(
        f"[MC·微软登录] 登录成功：{user_id} <-> {profile.player_name}"
    )
    await bot.send(
        f"微软账号登录成功！\n已绑定正版角色：{profile.player_name}"
    )


async def logout(user_id: str) -> str:
    """mc退出登录：删除绑定行（清 token 并解绑）。返回给用户的文案。"""
    # 若正在登录，先取消
    task = _pending_tasks.get(user_id)
    if task is not None and not task.done():
        task.cancel()
        _pending_tasks.pop(user_id, None)
        _pending_login_users.discard(user_id)

    existing = await MCQQUserBind.get_by_user_id(user_id)
    if not existing:
        return "你尚未登录微软账号"

    old_name = existing.player_name
    ok = await MCQQUserBind.delete_row(user_id=user_id)
    if not ok:
        logger.error(f"[MC·微软登录] 解绑失败 user={user_id}")
        return "退出登录失败，请检查控制台"

    logger.info(f"[MC·微软登录] 退出登录：{user_id} <-/-> {old_name}")
    return f"已退出微软登录并解绑：{old_name}"
