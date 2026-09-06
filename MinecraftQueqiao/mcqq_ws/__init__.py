import asyncio
import json
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote_plus

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from gsuid_core.app_life import app
from gsuid_core.logger import logger

from ..mcqq_database import MCQQServer


class WSManager:
    """管理反向 WebSocket 连接与请求响应通信"""

    _instance: Optional["WSManager"] = None

    def __new__(cls) -> "WSManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            # server_name -> WebSocket
            self.active_connections: Dict[str, WebSocket] = {}
            # echo -> Future[dict]
            self._pending_requests: Dict[str, asyncio.Future[dict]] = {}
            # 外部事件处理器回调 (server_name, raw_message) -> None
            self.message_handler: Optional[
                Callable[[str, str], Awaitable[None]]
            ] = None
            self._send_locks: Dict[str, asyncio.Lock] = {}
            self._initialized: bool = True

    def set_message_handler(
        self, handler: Callable[[str, str], Awaitable[None]]
    ) -> None:
        """设置接收消息时的外部处理回调"""
        self.message_handler = handler

    def is_connected(self, server_name: str) -> bool:
        """判断指定服务器是否已建立反向 WS 连接"""
        ws = self.active_connections.get(server_name)
        return (
            ws is not None
            and ws.application_state == WebSocketState.CONNECTED
        )

    def get_connected_servers(self) -> List[str]:
        """获取所有已连接的服务器名称列表"""
        return [
            name
            for name, ws in self.active_connections.items()
            if ws.application_state == WebSocketState.CONNECTED
        ]

    def _get_send_lock(self, server_name: str) -> asyncio.Lock:
        if server_name not in self._send_locks:
            self._send_locks[server_name] = asyncio.Lock()
        return self._send_locks[server_name]

    async def register_connection(
        self, server_name: str, websocket: WebSocket
    ) -> None:
        """注册新的 WebSocket 连接，断开旧有连接"""
        old_ws = self.active_connections.get(server_name)
        if old_ws is not None and old_ws is not websocket:
            try:
                await old_ws.close(code=1000, reason="Replaced by new connection")
            except Exception:
                pass
        self.active_connections[server_name] = websocket
        logger.info(
            f"[MCQueQiao] [{server_name}] 鹊桥反向 WebSocket 已连接 (已在线: {self.get_connected_servers()})"
        )

    async def remove_connection(
        self, server_name: str, websocket: Optional[WebSocket] = None
    ) -> None:
        """移除 WebSocket 连接并取消相关等待中的请求"""
        current_ws = self.active_connections.get(server_name)
        if websocket is None or current_ws is websocket:
            self.active_connections.pop(server_name, None)
            logger.info(f"[MCQueQiao] [{server_name}] 鹊桥反向 WebSocket 已断开")

    async def send_json(self, server_name: str, message: dict) -> bool:
        """向指定服务器发送 JSON 消息包"""
        ws = self.active_connections.get(server_name)
        if not ws or ws.application_state != WebSocketState.CONNECTED:
            logger.warning(
                f"[MCQueQiao] [{server_name}] 无法发送消息：WebSocket 未连接"
            )
            return False

        lock = self._get_send_lock(server_name)
        try:
            raw_text = json.dumps(message, ensure_ascii=False)
            async with lock:
                await ws.send_text(raw_text)
            logger.debug(
                f"[MCQueQiao] [{server_name}] 已发送 WS 消息: api={message.get('api')}"
            )
            return True
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{server_name}] 发送 WS 消息失败: {e}"
            )
            return False

    async def request(
        self,
        server_name: str,
        api: str,
        data: Optional[dict] = None,
        timeout: float = 8.0,
    ) -> Tuple[bool, Any]:
        """向指定服务器发送带 echo 的 API 请求，并异步等待响应结果。

        Returns:
            (success: bool, result_or_error_msg: Any)
        """
        if not self.is_connected(server_name):
            return False, "服务器未连接"

        echo = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict] = loop.create_future()
        self._pending_requests[echo] = future

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
                f"[MCQueQiao] [{server_name}] API 请求超时 ({timeout}s): api={api}, echo={echo}"
            )
            return False, "指令执行超时"
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{server_name}] API 请求异常: {e}"
            )
            return False, f"请求异常: {e}"
        finally:
            self._pending_requests.pop(echo, None)

    def resolve_response(self, echo: str, response_data: dict) -> bool:
        """如果收到 API 响应包，根据 echo 唤醒等待中的 Future"""
        future = self._pending_requests.get(echo)
        if future is not None and not future.done():
            future.set_result(response_data)
            return True
        return False


ws_manager = WSManager()


def _get_server_name_from_headers(websocket: WebSocket) -> str:
    """从 Header 获取 x-self-name"""
    raw_name = (
        websocket.headers.get("x-self-name")
        or websocket.headers.get("X-Self-Name")
        or ""
    )
    return unquote_plus(raw_name).strip()


def _get_token_from_request(websocket: WebSocket) -> str:
    """从 Header (Authorization) 或 Query 参数提取 access_token"""
    auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    if auth:
        return auth.strip()
    return websocket.query_params.get("token", "").strip()


async def _handle_queqiao_ws_session(
    websocket: WebSocket, server_name_from_path: Optional[str] = None
) -> None:
    """处理单个反向 WebSocket 连接生命周期"""
    # 优先使用 URL 路径中的 server_name，其次从 Header 提取
    server_name = server_name_from_path or _get_server_name_from_headers(websocket)

    if not server_name:
        logger.warning(
            f"[MCQueQiao] 拒绝反向 WS 连接：未指定 server_name (路径或 Header 均为空)"
        )
        await websocket.close(code=1008, reason="Missing server_name")
        return

    # 防回环校验
    origin = websocket.headers.get("x-client-origin") or ""
    if origin.lower() == "gsuid_core":
        logger.warning(
            f"[MCQueQiao] 拒绝来自 gsuid_core 自身的回环反向连接: server_name={server_name}"
        )
        await websocket.close(code=1008, reason="Origin cannot be gsuid_core")
        return

    # 查询数据库配置
    server = await MCQQServer.get_by_name(server_name)
    if server is None:
        logger.warning(
            f"[MCQueQiao] 拒绝反向 WS 连接：未知服务器 '{server_name}'（请先在控制台添加）"
        )
        await websocket.close(code=1008, reason="Unknown server_name")
        return

    if not server.enabled:
        logger.warning(
            f"[MCQueQiao] 拒绝反向 WS 连接：服务器 '{server_name}' 当前处于禁用状态"
        )
        await websocket.close(code=1008, reason="Server is disabled")
        return

    # Token 鉴权
    if server.access_token:
        client_token = _get_token_from_request(websocket)
        if client_token != server.access_token:
            logger.warning(
                f"[MCQueQiao] 拒绝反向 WS 连接：服务器 '{server_name}' 鉴权失败"
            )
            await websocket.close(code=1008, reason="Invalid access token")
            return

    # 握手成功
    await websocket.accept()
    await ws_manager.register_connection(server_name, websocket)

    try:
        while True:
            raw_message = await websocket.receive_text()
            if not raw_message:
                continue

            # 优先检查是否为 API Response 包
            try:
                data = json.loads(raw_message)
                if isinstance(data, dict):
                    echo = str(data.get("echo", ""))
                    if echo and ws_manager.resolve_response(echo, data):
                        # 已作为 API 响应消费
                        continue
            except json.JSONDecodeError:
                pass

            # 分发至事件处理器
            if ws_manager.message_handler:
                try:
                    await ws_manager.message_handler(server_name, raw_message)
                except Exception as e:
                    logger.error(
                        f"[MCQueQiao] [{server_name}] 事件处理器异常: {e}"
                    )

    except WebSocketDisconnect:
        logger.info(f"[MCQueQiao] [{server_name}] 客户端断开连接")
    except Exception as e:
        logger.error(f"[MCQueQiao] [{server_name}] WebSocket 连接异常: {e}")
    finally:
        await ws_manager.remove_connection(server_name, websocket)


# 挂载到 GsCore FastAPI 端点 1：带路径参数（如 ws://IP:PORT/minecraft/ws/Server1）
@app.websocket("/minecraft/ws/{server_name}")
async def queqiao_reverse_ws_with_path(websocket: WebSocket, server_name: str):
    await _handle_queqiao_ws_session(websocket, server_name)


# 挂载到 GsCore FastAPI 端点 2：固定路径（从 Header 获取 server_name，如 ws://IP:PORT/minecraft/ws）
@app.websocket("/minecraft/ws")
async def queqiao_reverse_ws_default(websocket: WebSocket):
    await _handle_queqiao_ws_session(websocket, None)
