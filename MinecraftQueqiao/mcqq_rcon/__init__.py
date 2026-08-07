import asyncio
import struct

import aiomcrcon

from ..mcqq_database import MCQQServer
from ..utils.utils.format_code import strip_minecraft_formatting_codes

# 超时（秒）
CONNECT_TIMEOUT: float = 5.0
COMMAND_TIMEOUT: float = 10.0
# aio-mc-rcon 的命令长度上限
MAX_CMD_LENGTH: int = 1446


class RCONError(Exception):
    """RCON 操作错误：连接/认证/执行失败等，向调用方统一暴露。"""


# 以 server.id 为键的持久连接池
_connections: dict[int, aiomcrcon.Client] = {}  # type: ignore
# 以 server.id 为键的连接建立/释放锁
_locks: dict[int, asyncio.Lock] = {}


def _get_lock(server_id: int) -> asyncio.Lock:
    """获取（惰性创建）指定服务器的连接锁。"""
    lock = _locks.get(server_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[server_id] = lock
    return lock


def _validate_config(server: MCQQServer) -> None:
    """校验服务器 RCON 配置，不满足抛 RCONError。"""
    if not server.rcon_enabled:
        raise RCONError(f"服务器 [{server.server_name}] 未开启 RCON")
    if not server.rcon_host or not server.rcon_password:
        raise RCONError(f"服务器 [{server.server_name}] RCON 配置不完整")


async def _connect(server: MCQQServer) -> aiomcrcon.Client:  # type: ignore
    """创建并连接一个 RCON 客户端。失败抛 RCONError，绝不返回未连接实例。"""
    _validate_config(server)
    client = aiomcrcon.Client(
        server.rcon_host, server.rcon_port, server.rcon_password
    )
    try:
        await client.connect(timeout=CONNECT_TIMEOUT)
    except aiomcrcon.IncorrectPasswordError:
        raise RCONError(
            f"服务器 [{server.server_name}] RCON 认证失败，请检查密码"
        )
    except aiomcrcon.RCONConnectionError as e:
        raise RCONError(
            f"服务器 [{server.server_name}] RCON 连接失败: {e}"
        )
    except Exception as e:
        raise RCONError(
            f"服务器 [{server.server_name}] RCON 连接异常: {e}"
        )
    return client


async def _discard(server: MCQQServer) -> None:
    """关闭并从池中移除指定服务器的连接（幂等，吞掉关闭异常）。"""
    client = _connections.pop(server.id, None)
    if client is not None:
        try:
            await client.close()
        except Exception:
            pass


def _is_stale_connection_error(e: Exception) -> bool:
    """判断是否为连接失效类错误（连接被服务器关闭/断开）。"""
    if isinstance(
        e,
        (
            aiomcrcon.ClientNotConnectedError,
            aiomcrcon.RCONConnectionError,
            OSError,
            asyncio.IncompleteReadError,
            struct.error,
        ),
    ):
        return True
    return False


async def execute(server: MCQQServer, command: str) -> str:
    """对指定服务器执行 RCON 指令，懒加载持久连接。

    连接失效（如服务器关闭了空闲连接）时自动丢弃并重建一次后重试，
    仍失败则抛 RCONError。
    """
    if not command:
        raise RCONError("指令内容为空")
    if len(command) > MAX_CMD_LENGTH:
        raise RCONError(f"指令过长（超过 {MAX_CMD_LENGTH} 字符）")

    # 连接失效时最多重建+重试一次；首次失败若为连接失效则重试，避免误伤真实指令错误
    for attempt in range(2):
        # 懒加载 + 双重检查锁
        client = _connections.get(server.id)
        if client is None:
            async with _get_lock(server.id):
                client = _connections.get(server.id)
                if client is None:
                    client = await _connect(server)
                    _connections[server.id] = client

        try:
            resp, _ = await client.send_cmd(command, timeout=COMMAND_TIMEOUT)
        except aiomcrcon.ClientNotConnectedError:
            await _discard(server)
            if attempt == 0:
                continue
            raise RCONError(
                f"服务器 [{server.server_name}] RCON 连接已断开，"
                f"请使用 mc刷新rcon连接 后重试"
            )
        except Exception as e:
            await _discard(server)
            if attempt == 0 and _is_stale_connection_error(e):
                continue
            raise RCONError(
                f"服务器 [{server.server_name}] RCON 执行指令失败: {e}"
            )

        return strip_minecraft_formatting_codes(resp).strip()

    # 理论上不可达（循环最多 2 次，第二次必然 return 或 raise）
    raise RCONError(f"服务器 [{server.server_name}] RCON 执行指令失败")


async def refresh(server: MCQQServer) -> None:
    """关闭并立即重建指定服务器的 RCON 连接。失败抛 RCONError。"""
    async with _get_lock(server.id):
        await _discard(server)
        client = await _connect(server)
        _connections[server.id] = client


async def close_all() -> None:
    """关闭所有持久连接（插件卸载/进程退出时调用）。"""
    for sid in list(_connections.keys()):
        client = _connections.pop(sid, None)
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass
