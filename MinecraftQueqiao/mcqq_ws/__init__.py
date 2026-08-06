import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple
from urllib.parse import unquote_plus, urlparse

import websockets
from gsuid_core.logger import logger


def _parse_ws_url(ws_url: str) -> Tuple[str, int, str]:
    """从 ws_url 解析出 host / port / path，正反向共用。"""
    parsed = urlparse(ws_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    return host, port, path


# 共享反向 WebSocket 服务端：(host, port) -> SharedReverseServer
_SHARED_SERVERS: Dict[Tuple[str, int], "SharedReverseServer"] = {}
_SHARED_LOCK = asyncio.Lock()


class SharedReverseServer:
    """可被多个服务器共用的反向 WebSocket 服务端，按 x-self-name 路由。"""

    def __init__(self, host: str, port: int, path: str) -> None:
        self.host = host
        self.port = port
        self.path = path if path.startswith("/") else f"/{path}"
        self.ws_server: Optional[Any] = None
        self._running: bool = False
        # server_name -> QueqiaoWSClient (server 模式)
        self.clients: Dict[str, "QueqiaoWSClient"] = {}

    def register(self, server_name: str, client: "QueqiaoWSClient") -> None:
        self.clients[server_name] = client
        logger.info(
            f"[MCQueQiao] 反向 WS 注册 server_name={server_name} -> "
            f"ws://{self.host}:{self.port}{self.path}"
        )

    def unregister(self, server_name: str) -> None:
        self.clients.pop(server_name, None)

    @property
    def is_empty(self) -> bool:
        return len(self.clients) == 0

    async def start(self) -> None:
        if self._running:
            return
        try:
            self.ws_server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port,
                process_request=self._process_request,
                ping_interval=30,
                ping_timeout=10,
            )
            self._running = True
            logger.info(
                f"[MCQueQiao] 反向 WebSocket 服务端已启动: "
                f"ws://{self.host}:{self.port}{self.path}"
            )
        except OSError as e:
            logger.error(
                f"[MCQueQiao] 反向 WebSocket 服务端启动失败 "
                f"({self.host}:{self.port}): {e}"
            )
            raise

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self.ws_server is not None:
            self.ws_server.close()
            try:
                await asyncio.wait_for(
                    self.ws_server.wait_closed(), timeout=5
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[MCQueQiao] 等待反向 WebSocket 服务端关闭超时"
                )
            self.ws_server = None
        logger.info(
            f"[MCQueQiao] 反向 WebSocket 服务端已停止: "
            f"{self.host}:{self.port}"
        )

    def _get_header(self, headers: Any, name: str) -> Optional[str]:
        """兼容不同 websockets 版本的 header 读取。"""
        if headers is None:
            return None
        try:
            value = headers.get(name)
            if value is not None:
                return value
        except Exception:
            pass
        try:
            value = headers.get(name.lower())
            if value is not None:
                return value
        except Exception:
            pass
        if isinstance(headers, dict):
            for k, v in headers.items():
                if str(k).lower() == name.lower():
                    return v
        return None

    async def _process_request(
        self, connection: Any, request: Any
    ) -> Any:
        """握手阶段校验 path / 防回环 / server_name / 鉴权。"""
        path = getattr(request, "path", None) or getattr(
            connection, "path", ""
        )
        if path and "?" in path:
            path = path.split("?", 1)[0]

        # 单一路径匹配
        if path != self.path:
            logger.warning(
                f"[MCQueQiao] 反向 WS 路径不匹配: "
                f"期望 {self.path}, 实际 {path}"
            )
            return connection.respond(404, "Invalid path")

        headers = getattr(request, "headers", None)
        self_name_raw = self._get_header(headers, "x-self-name")
        if not self_name_raw:
            logger.warning(
                "[MCQueQiao] 反向 WS 缺少 x-self-name Header"
            )
            return connection.respond(400, "Missing X-Self-Name Header")

        self_name = unquote_plus(self_name_raw)

        # 防回环：拒绝来自 gsuid_core 自身的连接
        origin = self._get_header(headers, "x-client-origin")
        if origin and origin.lower() == "gsuid_core":
            logger.warning(
                "[MCQueQiao] 反向 WS 拒绝 x-client-origin=gsuid_core 的连接"
            )
            return connection.respond(
                403, "X-Client-Origin cannot be gsuid_core"
            )

        client = self.clients.get(self_name)
        if client is None:
            logger.warning(
                f"[MCQueQiao] 反向 WS 未知 server_name={self_name}，"
                f"已注册: {list(self.clients.keys())}"
            )
            return connection.respond(
                404, f"Unknown server_name: {self_name}"
            )

        # Token 鉴权（每服务器独立 access_token）
        expected = client.access_token
        if expected:
            auth = self._get_header(headers, "Authorization") or ""
            token = auth[7:] if auth.startswith("Bearer ") else auth
            if token != expected:
                logger.warning(
                    f"[MCQueQiao] 反向 WS 鉴权失败: "
                    f"server_name={self_name}"
                )
                return connection.respond(401, "Invalid access token")

        return None  # 允许握手

    async def _handle_connection(self, websocket: Any) -> None:
        headers = getattr(websocket, "request_headers", None)
        if headers is None and hasattr(websocket, "request"):
            headers = getattr(websocket.request, "headers", None)

        self_name_raw = self._get_header(headers, "x-self-name") or ""
        self_name = unquote_plus(self_name_raw)
        client = self.clients.get(self_name)
        if client is None:
            logger.warning(
                f"[MCQueQiao] 反向 WS 连接后找不到 client: {self_name}"
            )
            await websocket.close(1008, "Unknown server")
            return

        remote = getattr(websocket, "remote_address", None)
        logger.info(
            f"[MCQueQiao] [{self_name}] 反向 WS 客户端已连接: "
            f"remote={remote}"
        )
        await client._on_server_client_connected(websocket)


class QueqiaoWSClient:
    """鹊桥 WebSocket 客户端

    支持两种模式：
    - client（默认）：主动连接鹊桥的 WebSocket Server（正向）
    - server：本端作为 WebSocket Server，等待鹊桥 Client 连入（反向）
    """

    FATAL_CLOSE_CODES = {1008, 1003, 1010}
    FATAL_STATUS_CODES = {401, 403, 404}

    def __init__(
        self,
        server_name: str,
        ws_url: str = "",
        access_token: str = "",
        queqiao_version: str = "v2",
        reconnect_interval: int = 10,
        max_retries: int = 5,
        message_handler: Optional[Callable[[str, str], Awaitable[None]]] = None,
        ws_mode: str = "client",
    ) -> None:
        self.server_name = server_name
        self.ws_url = ws_url
        self.access_token = access_token
        self.queqiao_version = queqiao_version
        self.reconnect_interval = reconnect_interval
        self.max_retries = max_retries
        self.message_handler = message_handler

        # 模式校验与规范化
        self.ws_mode = (ws_mode or "client").strip().lower()
        if self.ws_mode not in ("client", "server"):
            logger.warning(
                f"[MCQueQiao] [{server_name}] "
                f"未知 ws_mode={ws_mode}，回退为 client"
            )
            self.ws_mode = "client"

        # 正反向均从 ws_url 解析 host / port / path
        self.server_host, self.server_port, self.server_path = _parse_ws_url(
            ws_url
        )

        self.connected: bool = False
        self.websocket: Optional[Any] = None
        self.should_reconnect: bool = True
        self.total_retries: int = 0
        self._send_lock: asyncio.Lock = asyncio.Lock()

        # server 模式内部状态
        self._shared_server: Optional[SharedReverseServer] = None
        self._closed: asyncio.Event = asyncio.Event()

    def _build_headers(self) -> dict[str, str]:
        """构造连接鹊桥所需的 Header。"""
        headers: dict[str, str] = {
            "x-self-name": self.server_name,
            "x-client-origin": "gsuid_core",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _is_fatal_error(self, error: Exception) -> bool:
        """判断是否为致命错误（不应重试）。"""
        if isinstance(error, websockets.exceptions.ConnectionClosed):
            return error.code in self.FATAL_CLOSE_CODES
        # 兼容不同 websockets 版本的异常名
        invalid_status = (
            getattr(websockets.exceptions, "InvalidStatusCode", None)
            or getattr(websockets.exceptions, "InvalidStatus", None)
        )
        if invalid_status and isinstance(error, invalid_status):
            status = getattr(error, "status_code", None) or getattr(
                error, "status", None
            )
            return status in self.FATAL_STATUS_CODES
        return False

    async def start(self) -> None:
        """启动 WebSocket（client 循环 或 server 监听）。"""
        self.should_reconnect = True
        self._closed.clear()
        if self.ws_mode == "server":
            await self._run_server_mode()
        else:
            await self._run_client_loop()

    async def _run_client_loop(self) -> None:
        """正向 WS 连接循环，带自动重连。"""
        while self.should_reconnect:
            logger.info(
                f"[MCQueQiao] [{self.server_name}] "
                f"正在尝试连接 WebSocket: {self.ws_url}"
            )
            try:
                async with websockets.connect(
                    self.ws_url,
                    additional_headers=self._build_headers(),
                    ping_interval=30,
                    ping_timeout=10,
                    proxy=None,
                ) as websocket:
                    self.websocket = websocket
                    self.connected = True
                    self.total_retries = 0
                    logger.info(
                        f"[MCQueQiao] [{self.server_name}] "
                        f"已连接到鹊桥 WebSocket: {self.ws_url}"
                    )

                    async for message in websocket:
                        if self.message_handler:
                            await self.message_handler(
                                self.server_name, message # type: ignore
                            )

            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                ConnectionRefusedError,
                asyncio.TimeoutError,
                OSError,
            ) as e:
                self.connected = False
                self.websocket = None

                if not self.should_reconnect:
                    break

                if self._is_fatal_error(e):
                    logger.error(
                        f"[MCQueQiao] [{self.server_name}] "
                        f"致命错误，停止重试: {e}"
                    )
                    self.should_reconnect = False
                    break

                self.total_retries += 1
                if self.max_retries > 0 and self.total_retries > self.max_retries:
                    logger.error(
                        f"[MCQueQiao] [{self.server_name}] "
                        f"连接失败次数已达上限({self.max_retries}次)，停止重试"
                    )
                    self.should_reconnect = False
                    break

                wait_time = min(
                    self.reconnect_interval * self.total_retries, 60
                )
                logger.warning(
                    f"[MCQueQiao] [{self.server_name}] "
                    f"WebSocket 连接错误: {e}，"
                    f"将在 {wait_time} 秒后重试"
                    f"(第 {self.total_retries} 次)"
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                self.connected = False
                self.websocket = None
                logger.error(
                    f"[MCQueQiao] [{self.server_name}] "
                    f"WebSocket 未知错误: {e}"
                )
                if not self.should_reconnect:
                    break
                await asyncio.sleep(self.reconnect_interval)

        self.connected = False
        self.websocket = None

    async def _run_server_mode(self) -> None:
        """反向：作为 Server 等待鹊桥 Client 连入。"""
        async with _SHARED_LOCK:
            key = (self.server_host, self.server_port)
            shared = _SHARED_SERVERS.get(key)
            if shared is None:
                shared = SharedReverseServer(
                    self.server_host,
                    self.server_port,
                    self.server_path,
                )
                _SHARED_SERVERS[key] = shared
            # 同端口 path 不一致时告警（共享端口只用第一个 path）
            if shared.path != self.server_path:
                logger.warning(
                    f"[MCQueQiao] [{self.server_name}] 反向 WS 端口 "
                    f"{self.server_port} 已使用 path={shared.path}，"
                    f"当前 path={self.server_path} 将被忽略"
                )
            shared.register(self.server_name, self)
            self._shared_server = shared
            await shared.start()

        logger.info(
            f"[MCQueQiao] [{self.server_name}] 进入反向模式，"
            f"等待鹊桥 Client 连接 "
            f"ws://{self.server_host}:{self.server_port}"
            f"{self._shared_server.path}"
        )

        # 阻塞直到 stop() 被调用
        try:
            await self._closed.wait()
        finally:
            await self._detach_from_shared_server()

    async def _on_server_client_connected(
        self, websocket: Any
    ) -> None:
        """server 模式：处理单个鹊桥 Client 连接生命周期。"""
        # 替换旧连接
        old = self.websocket
        if old is not None and old is not websocket:
            try:
                await old.close(1000, "Replaced by new connection")
            except Exception:
                pass

        self.websocket = websocket
        self.connected = True
        logger.info(
            f"[MCQueQiao] [{self.server_name}] 反向 WebSocket 已建立"
        )

        try:
            async for message in websocket:
                if self.message_handler:
                    await self.message_handler(
                        self.server_name, message  # type: ignore
                    )
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(
                f"[MCQueQiao] [{self.server_name}] 反向 WS 连接关闭: "
                f"code={e.code}, reason={e.reason}"
            )
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{self.server_name}] 反向 WS 连接异常: {e}"
            )
        finally:
            if self.websocket is websocket:
                self.websocket = None
                self.connected = False
            logger.info(
                f"[MCQueQiao] [{self.server_name}] "
                f"反向 WebSocket 已断开"
            )

    async def _detach_from_shared_server(self) -> None:
        """从共享服务端注销，无引用时关闭服务端。"""
        if self._shared_server is None:
            return
        async with _SHARED_LOCK:
            self._shared_server.unregister(self.server_name)
            key = (
                self._shared_server.host,
                self._shared_server.port,
            )
            if self._shared_server.is_empty:
                await self._shared_server.stop()
                _SHARED_SERVERS.pop(key, None)
            self._shared_server = None

    async def send(self, message: dict) -> bool:
        """通过 WebSocket 发送 JSON 消息。

        Args:
            message: 要发送的字典消息

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        if not self.connected or not self.websocket:
            logger.error(
                f"[MCQueQiao] [{self.server_name}] "
                f"无法发送：WebSocket 未连接"
            )
            return False
        try:
            async with self._send_lock:
                await self.websocket.send(
                    json.dumps(message, ensure_ascii=False)
                )
            logger.debug(
                f"[MCQueQiao] [{self.server_name}] "
                f"已发送消息: {message.get('api', 'unknown')}"
            )
            return True
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{self.server_name}] "
                f"发送消息失败: {e}"
            )
            return False

    async def stop(self) -> None:
        """停止 WebSocket 连接 / 服务端。"""
        self.should_reconnect = False
        ws = self.websocket
        self.websocket = None
        self.connected = False
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        self._closed.set()
        if self.ws_mode == "server":
            await self._detach_from_shared_server()
        logger.info(
            f"[MCQueQiao] [{self.server_name}] WebSocket 已关闭"
        )


class WSManager:
    """多服务器 WebSocket 连接管理器"""

    _instance: Optional["WSManager"] = None

    def __new__(cls) -> "WSManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self.clients: dict[str, QueqiaoWSClient] = {}
            self._tasks: list[asyncio.Task[Any]] = []
            self._initialized: bool = True

    async def start_all(
        self,
        servers: list[Any],
        reconnect_interval: int,
        max_retries: int,
        message_handler: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """为每个服务器配置创建 WebSocket 客户端并启动连接。

        Args:
            servers: 服务器配置列表（MCQQServer 实例）
            reconnect_interval: 重连间隔秒数
            max_retries: 最大重连次数，0 表示无限
            message_handler: 消息处理回调函数 (server_name, raw_message)
        """
        for server in servers:
            if not server.server_name:
                logger.warning("[MCQueQiao] 跳过无服务器名称的配置")
                continue
            if server.server_name in self.clients:
                logger.warning(
                    f"[MCQueQiao] 服务器 '{server.server_name}' 已存在连接，跳过"
                )
                continue

            client = QueqiaoWSClient(
                server_name=server.server_name,
                ws_url=server.ws_url,
                access_token=server.access_token,
                queqiao_version=server.queqiao_version,
                reconnect_interval=reconnect_interval,
                max_retries=max_retries,
                message_handler=message_handler,
                ws_mode=server.ws_mode,
            )
            self.clients[server.server_name] = client
            task = asyncio.create_task(
                client.start(),
                name=f"mcqq_ws_{server.server_name}",
            )
            self._tasks.append(task)
            logger.info(
                f"[MCQueQiao] 已启动服务器 '{server.server_name}' 的 WebSocket 连接任务"
            )

    async def stop_all(self) -> None:
        """停止所有 WebSocket 客户端连接。"""
        for client in self.clients.values():
            await client.stop()
        self.clients.clear()

        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._tasks.clear()
        logger.info("[MCQueQiao] 所有 WebSocket 连接已停止")

    def get_client(self, server_name: str) -> Optional[QueqiaoWSClient]:
        """按服务器名获取客户端实例。"""
        return self.clients.get(server_name)

    async def send_to_server(
        self, server_name: str, message: dict
    ) -> bool:
        """向指定服务器发送消息。

        Args:
            server_name: 服务器名称
            message: 要发送的字典消息

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        client = self.get_client(server_name)
        if client is None:
            logger.error(
                f"[MCQueQiao] 未找到服务器 '{server_name}' 的连接"
            )
            return False
        return await client.send(message)


ws_manager = WSManager()
