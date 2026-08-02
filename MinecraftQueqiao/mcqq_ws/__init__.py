import asyncio
import json
from typing import Any, Awaitable, Callable, Optional

import websockets
from gsuid_core.logger import logger


class QueqiaoWSClient:
    """鹊桥 WebSocket 客户端，连接单个 MC 服务器。

    仅支持正向 WS（作为 Client 连接鹊桥 Server）。
    """

    FATAL_CLOSE_CODES = {1008, 1003, 1010}
    FATAL_STATUS_CODES = {401, 403, 404}

    def __init__(
        self,
        server_name: str,
        ws_url: str,
        access_token: str = "",
        queqiao_version: str = "v2",
        reconnect_interval: int = 10,
        max_retries: int = 5,
        message_handler: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
        self.server_name = server_name
        self.ws_url = ws_url
        self.access_token = access_token
        self.queqiao_version = queqiao_version
        self.reconnect_interval = reconnect_interval
        self.max_retries = max_retries
        self.message_handler = message_handler

        self.connected: bool = False
        self.websocket: Optional[Any] = None
        self.should_reconnect: bool = True
        self.total_retries: int = 0
        self._send_lock: asyncio.Lock = asyncio.Lock()

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
        """启动 WebSocket 客户端连接循环。"""
        self.should_reconnect = True
        await self._run_client_loop()

    async def _run_client_loop(self) -> None:
        """正向 WS 连接循环，带自动重连。"""
        while self.should_reconnect:
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
                                self.server_name, message
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
            logger.info(
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
        """停止 WebSocket 客户端，不再重连。"""
        self.should_reconnect = False
        ws = self.websocket
        self.websocket = None
        self.connected = False
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        logger.info(
            f"[MCQueQiao] [{self.server_name}] WebSocket 已关闭"
        )


class WSManager:
    """多服务器 WebSocket 连接管理器（单例）。"""

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
