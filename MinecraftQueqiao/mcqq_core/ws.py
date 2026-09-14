"""鹊桥 WebSocket 连接与 API 发送（协议层，不依赖 command/waypoint）。"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote_plus

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from gsuid_core.app_life import app
from gsuid_core.logger import logger

from ..mcqq_config import mcqq_config
from ..mcqq_database import MCQQServer


class WSManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self._pending_requests: Dict[str, Tuple[str, asyncio.Future[dict]]] = {}
        self.message_handler: Optional[
            Callable[[str, str], Awaitable[None]]
        ] = None
        self._send_locks: Dict[str, asyncio.Lock] = {}

    def set_message_handler(
        self, handler: Callable[[str, str], Awaitable[None]]
    ) -> None:
        self.message_handler = handler

    def is_connected(self, server_name: str) -> bool:
        ws = self.active_connections.get(server_name)
        return ws is not None and ws.application_state == WebSocketState.CONNECTED

    def get_connected_servers(self) -> List[str]:
        return [
            name
            for name, ws in self.active_connections.items()
            if ws.application_state == WebSocketState.CONNECTED
        ]

    def _get_send_lock(self, server_name: str) -> asyncio.Lock:
        if server_name not in self._send_locks:
            self._send_locks[server_name] = asyncio.Lock()
        return self._send_locks[server_name]

    def _cancel_pending_requests(
        self, server_name: str, reason: str = "服务器连接已断开"
    ) -> None:
        to_cancel = [
            (echo, future)
            for echo, (sname, future) in self._pending_requests.items()
            if sname == server_name
        ]
        for echo, future in to_cancel:
            self._pending_requests.pop(echo, None)
            if not future.done():
                future.set_exception(ConnectionError(reason))
        if to_cancel:
            logger.debug(
                f"[MC·Websocket] [{server_name}] 已取消 {len(to_cancel)} 个等待中的请求: {reason}"
            )

    async def register_connection(
        self, server_name: str, websocket: WebSocket
    ) -> None:
        old_ws = self.active_connections.get(server_name)
        if old_ws is not None and old_ws is not websocket:
            try:
                await old_ws.close(code=1000, reason="Replaced by new connection")
            except Exception:
                pass
            self._cancel_pending_requests(server_name, "连接已被新连接替换")
        self.active_connections[server_name] = websocket
        logger.info(f"[MC·Websocket] [{server_name}] ws建立连接")

    async def remove_connection(
        self, server_name: str, websocket: Optional[WebSocket] = None
    ) -> None:
        current_ws = self.active_connections.get(server_name)
        if websocket is None or current_ws is websocket:
            self.active_connections.pop(server_name, None)
            self._cancel_pending_requests(server_name, "服务器连接已断开")
            logger.info(f"[MC·Websocket] [{server_name}] ws断开连接")

    async def send_json(self, server_name: str, message: dict) -> bool:
        ws = self.active_connections.get(server_name)
        if not ws or ws.application_state != WebSocketState.CONNECTED:
            logger.warning(
                f"[MC·Websocket] [{server_name}] 无法发送消息：WebSocket 未连接"
            )
            return False

        lock = self._get_send_lock(server_name)
        try:
            raw_text = json.dumps(message, ensure_ascii=False)
            async with lock:
                await ws.send_text(raw_text)
            logger.debug(
                f"[MC·Websocket] [{server_name}] 已发送 WS 消息: api={message.get('api')}"
            )
            return True
        except Exception as e:
            logger.error(f"[MC·Websocket] [{server_name}] 发送 WS 消息失败: {e}")
            return False

    async def request(
        self,
        server_name: str,
        api: str,
        data: Optional[dict] = None,
        timeout: float = 8.0,
    ) -> Tuple[bool, Any]:
        if not self.is_connected(server_name):
            return False, "服务器未连接"

        echo = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict] = loop.create_future()
        self._pending_requests[echo] = (server_name, future)

        message = {
            "api": api,
            "data": data or {},
            "echo": echo,
        }

        sent = await self.send_json(server_name, message)
        if not sent:
            self._pending_requests.pop(echo, None)
            return False, "发送请求失败"

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            status = response.get("status", "")
            if status == "SUCCESS" or response.get("code") == 200:
                return True, response.get("data", "")
            return False, response.get("message", "执行失败")
        except asyncio.TimeoutError:
            logger.warning(
                f"[MC·Websocket] [{server_name}] API 请求超时 ({timeout}s): api={api}, echo={echo}"
            )
            return False, "指令执行超时"
        except ConnectionError as e:
            logger.warning(f"[MC·Websocket] [{server_name}] API 请求连接中断: {e}")
            return False, "服务器连接已断开"
        except Exception as e:
            logger.error(f"[MC·Websocket] [{server_name}] API 请求异常: {e}")
            return False, f"请求异常: {e}"
        finally:
            self._pending_requests.pop(echo, None)

    def resolve_response(self, echo: str, response_data: dict) -> bool:
        item = self._pending_requests.get(echo)
        if item is not None:
            _, future = item
            if not future.done():
                future.set_result(response_data)
                return True
        return False


ws_manager = WSManager()


def _get_server_name_from_headers(websocket: WebSocket) -> str:
    raw_name = (
        websocket.headers.get("x-self-name")
        or websocket.headers.get("X-Self-Name")
        or ""
    )
    return unquote_plus(raw_name).strip()


def _get_token_from_request(websocket: WebSocket) -> str:
    auth = (
        websocket.headers.get("authorization")
        or websocket.headers.get("Authorization")
        or ""
    )
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    if auth:
        return auth.strip()
    return websocket.query_params.get("token", "").strip()


async def _safe_dispatch_message(
    handler: Callable[[str, str], Awaitable[None]],
    server_name: str,
    raw_message: str,
) -> None:
    try:
        await handler(server_name, raw_message)
    except Exception as e:
        logger.error(f"[MC·Websocket] [{server_name}] 事件处理器异常: {e}")


async def _handle_queqiao_ws_session(
    websocket: WebSocket, server_name_from_path: Optional[str] = None
) -> None:
    server_name = server_name_from_path or _get_server_name_from_headers(websocket)

    if not server_name:
        logger.warning("[MC·Websocket] ws连接拒绝：未指定ServerName")
        await websocket.close(code=1008, reason="Missing server_name")
        return

    origin = websocket.headers.get("x-client-origin") or ""
    if origin.lower() == "gsuid_core":
        logger.warning("[MC·Websocket] 拒绝连接：gsuid_core")
        await websocket.close(code=1008, reason="Origin cannot be gsuid_core")
        return

    server = await MCQQServer.get_by_name(server_name)
    if server is None:
        logger.warning(
            f"[MC·Websocket] ws连接拒绝：未配置服务器 {server_name}，请先添加服务器再连接"
        )
        await websocket.close(code=1008, reason="Unknown server_name")
        return

    if not server.enabled:
        logger.warning("[MC·Websocket] ws连接拒绝：服务器被禁用")
        await websocket.close(code=1008, reason="Server is disabled")
        return

    if server.access_token:
        client_token = _get_token_from_request(websocket)
        if client_token != server.access_token:
            logger.warning(f"[MC·Websocket] ws连接拒绝：{server_name} 鉴权失败")
            await websocket.close(code=1008, reason="Invalid access token")
            return
    else:
        client_ip = websocket.client.host if websocket.client else ""
        trusted_ips: List[str] = mcqq_config.get_config("trusted_ips").data
        if client_ip not in trusted_ips:
            logger.warning(
                f"[MC·Websocket] ws连接拒绝：{server_name} 未配置 access_token 且客户端 IP '{client_ip}' 不在受信任列表中"
            )
            await websocket.close(code=1008, reason="Untrusted IP address")
            return

    await websocket.accept()
    await ws_manager.register_connection(server_name, websocket)

    try:
        while True:
            raw_message = await websocket.receive_text()
            if not raw_message:
                continue

            try:
                data = json.loads(raw_message)
                if isinstance(data, dict):
                    echo = str(data.get("echo", ""))
                    if echo and ws_manager.resolve_response(echo, data):
                        continue
            except json.JSONDecodeError:
                pass

            if ws_manager.message_handler:
                asyncio.create_task(
                    _safe_dispatch_message(
                        ws_manager.message_handler, server_name, raw_message
                    )
                )

    except WebSocketDisconnect:
        logger.info(f"[MC·Websocket] [{server_name}] 客户端断开连接")
    except Exception as e:
        logger.error(f"[MC·Websocket] [{server_name}] WebSocket 连接异常: {e}")
    finally:
        await ws_manager.remove_connection(server_name, websocket)


@app.websocket("/minecraft/ws/{server_name}")
async def queqiao_reverse_ws_with_path(websocket: WebSocket, server_name: str):
    await _handle_queqiao_ws_session(websocket, server_name)


@app.websocket("/minecraft/ws")
async def queqiao_reverse_ws_default(websocket: WebSocket):
    await _handle_queqiao_ws_session(websocket, None)
