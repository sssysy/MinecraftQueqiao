"""微软账号认证链：Device Code → MS Token → XBL → XSTS → MC Token"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx
from gsuid_core.logger import logger

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQUserBind

MS_DEVICE_CODE_URL = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
)
MS_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBL_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN_URL = (
    "https://api.minecraftservices.com/authentication/login_with_xbox"
)
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"
SCOPE = "XboxLive.signin offline_access"
HTTP_TIMEOUT = 15.0
HTTP_HEADERS = {
    "User-Agent": "MCQueQiao/2.0 (ms-login; +https://github.com)",
    "Accept": "application/json",
}

# 懒续期缓冲：临期 5 分钟内视为已过期
TOKEN_EXPIRE_BUFFER = 300


@dataclass
class DeviceCodeSession:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass
class McProfile:
    player_id: str
    player_name: str
    mc_access_token: str
    expires_in: int
    ms_refresh_token: str


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS)


async def request_device_code(
    client_id: str,
) -> Tuple[Optional[DeviceCodeSession], Optional[str]]:
    """申请设备代码，返回会话或错误文案。"""
    try:
        async with _client() as client:
            resp = await client.post(
                MS_DEVICE_CODE_URL,
                data={
                    "client_id": client_id,
                    "scope": SCOPE,
                },
            )
            data = resp.json()
    except Exception as e:
        logger.warning(f"[MC·微软登录] 请求设备代码失败: {type(e).__name__}: {e}")
        return None, "请求微软设备代码失败，请稍后重试"

    if resp.status_code != 200:
        err = data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}"
        logger.warning(f"[MC·微软登录] 设备代码接口拒绝: {err}")
        return None, f"请求微软设备代码失败：{err}"

    try:
        session = DeviceCodeSession(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data.get("verification_uri")
            or data.get("verification_uri_complete", "https://www.microsoft.com/link"),
            expires_in=int(data.get("expires_in", 900)),
            interval=max(int(data.get("interval", 5)), 1),
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"[MC·微软登录] 设备代码响应字段异常: {e}")
        return None, "微软设备代码响应异常，请稍后重试"
    return session, None


async def poll_for_ms_token(
    client_id: str,
    device_code: str,
    interval: int,
    timeout: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """轮询设备代码授权结果。

    Returns:
        (ms_token_payload, err)
        成功时 payload 含 access_token / refresh_token / expires_in。
    """
    deadline = time.monotonic() + timeout
    wait = interval

    async with _client() as client:
        while time.monotonic() < deadline:
            await asyncio.sleep(wait)
            try:
                resp = await client.post(
                    MS_TOKEN_URL,
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code": device_code,
                        "client_id": client_id,
                    },
                )
                data = resp.json()
            except Exception as e:
                logger.warning(f"[MC·微软登录] 轮询异常: {type(e).__name__}: {e}")
                wait = min(wait + 2, 15)
                continue

            if resp.status_code == 200 and data.get("access_token"):
                return data, None

            error = data.get("error", "")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                wait = min(wait + 2, 15)
                continue
            if error == "expired_token":
                return None, "登录码已过期，请重新发送 mc登录"
            if error == "access_denied":
                return None, "你已取消登录"
            if error:
                desc = data.get("error_description") or error
                logger.warning(f"[MC·微软登录] 轮询失败: {desc}")
                return None, f"微软登录失败：{desc}"
            wait = min(wait + 1, 15)

    return None, "登录超时，请重新发送 mc登录"


async def _xbox_authenticate(
    client: httpx.AsyncClient, ms_access_token: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """MS token → Xbox Live user token。返回 (xbox_token, user_hash, err)。"""
    try:
        resp = await client.post(
            XBL_AUTH_URL,
            json={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": f"d={ms_access_token}",
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT",
            },
        )
        data = resp.json()
    except Exception as e:
        logger.warning(f"[MC·微软登录] Xbox 认证异常: {type(e).__name__}: {e}")
        return None, None, "Xbox Live 认证失败，请稍后重试"

    if resp.status_code != 200:
        logger.warning(
            f"[MC·微软登录] Xbox 认证拒绝: HTTP {resp.status_code} body={data}"
        )
        return None, None, "Xbox Live 认证失败，请稍后重试"

    token = data.get("Token")
    uhs = (data.get("DisplayClaims") or {}).get("xui", [{}])[0].get("uhs")
    if not token or not uhs:
        logger.warning("[MC·微软登录] Xbox 认证响应缺少 Token/uhs")
        return None, None, "Xbox Live 认证响应异常"
    return token, uhs, None


async def _xsts_authorize(
    client: httpx.AsyncClient, xbox_token: str
) -> Tuple[Optional[str], Optional[str]]:
    """Xbox token → XSTS token。返回 (xsts_token, err)。"""
    try:
        resp = await client.post(
            XSTS_AUTH_URL,
            json={
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [xbox_token],
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT",
            },
        )
        data = resp.json()
    except Exception as e:
        logger.warning(f"[MC·微软登录] XSTS 异常: {type(e).__name__}: {e}")
        return None, "Xbox 授权失败，请稍后重试"

    if resp.status_code != 200:
        xerr = data.get("XErr")
        logger.warning(
            f"[MC·微软登录] XSTS 拒绝: HTTP {resp.status_code} XErr={xerr} body={data}"
        )
        if xerr == 2148916233:
            return None, "该微软账号未加入 Xbox，请先注册 Xbox 档案"
        if xerr == 2148916238:
            return None, "该账号为儿童账号，无法完成登录"
        return None, "Xbox 授权失败，请稍后重试"

    token = data.get("Token")
    if not token:
        logger.warning("[MC·微软登录] XSTS 响应缺少 Token")
        return None, "Xbox 授权响应异常"
    return token, None


async def _mc_login_with_xbox(
    client: httpx.AsyncClient, user_hash: str, xsts_token: str
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """XSTS → Minecraft access_token。返回 (mc_token, expires_in, err)。"""
    try:
        resp = await client.post(
            MC_LOGIN_URL,
            json={
                "identityToken": f"XBL3.0 x={user_hash};{xsts_token}",
            },
        )
        data = resp.json()
    except Exception as e:
        logger.warning(f"[MC·微软登录] MC 登录异常: {type(e).__name__}: {e}")
        return None, None, "Minecraft 登录失败，请稍后重试"

    if resp.status_code != 200:
        # 403 = 国际版服务未在该微软账号下查到 Minecraft 资格
        logger.warning(
            f"[MC·微软登录] MC 登录拒绝: HTTP {resp.status_code} body={data}"
        )
        if resp.status_code == 403:
            return None, None, (
                "Minecraft 登录被拒绝（无正版资格）\n"
                "请确认：\n"
                "1. 使用的是拥有【国际版 Java 版】的微软账号（中国版/网易版不适用）\n"
                "2. 不是仅拥有基岩版、主机版或仅通过家庭共享\n"
                "3. 可先用该账号打开一次 https://www.minecraft.net 确认角色名可见"
            )
        return None, None, "Minecraft 登录失败，请稍后重试"

    token = data.get("access_token")
    if not token:
        logger.warning("[MC·微软登录] MC 登录响应缺少 access_token")
        return None, None, "Minecraft 登录响应异常"
    expires_in = int(data.get("expires_in", 86400))
    return token, expires_in, None


async def _fetch_profile(
    client: httpx.AsyncClient, mc_access_token: str
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """拉取正版档案。返回 (player_id, player_name, err)。"""
    try:
        resp = await client.get(
            MC_PROFILE_URL,
            headers={"Authorization": f"Bearer {mc_access_token}"},
        )
        data = resp.json()
    except Exception as e:
        logger.warning(f"[MC·微软登录] 拉取档案异常: {type(e).__name__}: {e}")
        return None, None, "获取 Minecraft 档案失败，请稍后重试"

    if resp.status_code != 200:
        logger.warning(f"[MC·微软登录] 拉取档案拒绝: HTTP {resp.status_code}")
        return None, None, "获取 Minecraft 档案失败，请确认该账号已拥有正版 Minecraft"

    player_id = data.get("id")
    player_name = data.get("name")
    if not player_id or not player_name:
        logger.warning("[MC·微软登录] 档案响应缺少 id/name")
        return None, None, "Minecraft 档案响应异常"
    return player_id, player_name, None


async def ms_token_to_mc_profile(
    ms_access_token: str, ms_refresh_token: str
) -> Tuple[Optional[McProfile], Optional[str]]:
    """MS access_token → 完整认证链 → MC 档案。"""
    async with _client() as client:
        xbox_token, user_hash, err = await _xbox_authenticate(
            client, ms_access_token
        )
        if err or not xbox_token or not user_hash:
            return None, err

        xsts_token, err = await _xsts_authorize(client, xbox_token)
        if err or not xsts_token:
            return None, err

        mc_token, expires_in, err = await _mc_login_with_xbox(
            client, user_hash, xsts_token
        )
        if err or not mc_token or expires_in is None:
            return None, err

        player_id, player_name, err = await _fetch_profile(client, mc_token)
        if err or not player_id or not player_name:
            return None, err

    return (
        McProfile(
            player_id=player_id,
            player_name=player_name,
            mc_access_token=mc_token,
            expires_in=expires_in,
            ms_refresh_token=ms_refresh_token,
        ),
        None,
    )


async def refresh_ms_token(
    client_id: str, refresh_token: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """用 refresh_token 刷新微软 access_token。"""
    try:
        async with _client() as client:
            resp = await client.post(
                MS_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                },
            )
            data = resp.json()
    except Exception as e:
        logger.warning(f"[MC·微软登录] 刷新 token 异常: {type(e).__name__}: {e}")
        return None, "刷新登录态失败，请稍后重试"

    if resp.status_code != 200 or not data.get("access_token"):
        err = data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}"
        logger.warning(f"[MC·微软登录] 刷新 token 失败: {err}")
        return None, "登录已失效，请重新发送 mc登录"
    return data, None


def is_token_valid(token_payload: Dict[str, Any]) -> bool:
    """MC access_token 是否仍在有效期内（含缓冲）。"""
    expires_at = token_payload.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return False
    return float(expires_at) - time.time() > TOKEN_EXPIRE_BUFFER


async def ensure_mc_token(
    client_id: str,
    token_payload: Dict[str, Any],
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """确保拿到可用的 MC access_token。

    Returns:
        (mc_access_token, updated_payload, err)
        updated_payload 仅在发生续期时非 None，调用方需回写存储。
    """
    if is_token_valid(token_payload):
        mc_token = token_payload.get("mc_access_token")
        if mc_token:
            return mc_token, None, None

    refresh_token = token_payload.get("ms_refresh_token")
    if not refresh_token:
        return None, None, "登录已失效，请重新发送 mc登录"

    ms_data, err = await refresh_ms_token(client_id, refresh_token)
    if err or not ms_data:
        return None, None, err

    # 微软可能轮换 refresh_token，必须保存新的
    new_refresh = ms_data.get("refresh_token") or refresh_token
    profile, err = await ms_token_to_mc_profile(
        ms_data["access_token"], new_refresh
    )
    if err or not profile:
        return None, None, err

    updated = {
        "ms_refresh_token": profile.ms_refresh_token,
        "mc_access_token": profile.mc_access_token,
        "expires_at": time.time() + profile.expires_in - TOKEN_EXPIRE_BUFFER,
    }
    return profile.mc_access_token, updated, None


async def get_user_mc_token(user_id: str) -> Tuple[Optional[str], Optional[str]]:
    """user_id → 可用 MC access_token；必要时续期并回写绑定表。

    Returns:
        (mc_access_token, err)
    """
    bind = await MCQQUserBind.get_by_user_id(user_id)
    if not bind or not bind.token:
        return None, "你尚未登录微软账号，请先发送 mc登录"

    try:
        payload = json.loads(bind.token)
    except (TypeError, json.JSONDecodeError):
        return None, "登录态异常，请重新发送 mc登录"

    client_id = str(mcqq_config.get_config("ms_client_id").data or "").strip()
    if not client_id:
        return None, "尚未配置微软应用客户端 ID，请在插件配置中填写 ms_client_id"

    token, updated, err = await ensure_mc_token(client_id, payload)
    if err or not token:
        return None, err or "登录已失效，请重新发送 mc登录"

    if updated:
        try:
            new_payload = {**payload, **updated}
            await MCQQUserBind.update_data_by_data(
                {"user_id": user_id},
                {"token": json.dumps(new_payload, ensure_ascii=False)},
            )
        except Exception as e:
            logger.warning(f"[MC·微软登录] token 续期回写失败 user={user_id}: {e}")

    return token, None
