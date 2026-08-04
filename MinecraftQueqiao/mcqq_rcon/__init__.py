import asyncio
import struct

RCON_TIMEOUT = 10


class RCONError(Exception):
    """RCON 协议错误"""


def _build_packet(request_id: int, ptype: int, payload: str) -> bytes:
    """按协议打包：4字节长度 + 请求ID + 类型 + 负载 + 2个\\0。"""
    body = (
        struct.pack("<ii", request_id, ptype)
        + payload.encode("utf-8")
        + b"\x00\x00"
    )
    return struct.pack("<i", len(body)) + body


async def _read_packet(reader: asyncio.StreamReader):
    """读取一个 RCON 数据包，返回 (request_id, ptype, payload)。"""
    header = await reader.readexactly(4)
    length = struct.unpack("<i", header)[0]
    if length < 10 or length > 16384:
        raise RCONError(f"无效的RCON数据包长度: {length}")
    body = await reader.readexactly(length)
    request_id, ptype = struct.unpack("<ii", body[:8])
    payload = body[8:-2].decode("utf-8", errors="replace")
    return request_id, ptype, payload


async def rcon_run(
    host: str,
    port: int,
    password: str,
    command: str,
    timeout: float = RCON_TIMEOUT,
) -> str:
    """连接 RCON 服务器，登录并执行指令，返回指令输出。"""

    async def _run() -> str:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            # 登录：类型 3（AUTH），负载为密码
            writer.write(_build_packet(1, 3, password))
            await writer.drain()
            req_id, _, _ = await _read_packet(reader)
            if req_id == -1:
                raise RCONError("RCON 认证失败，请检查密码")

            # 执行指令：类型 2（EXECCOMMAND）
            writer.write(_build_packet(2, 2, command))
            await writer.drain()

            # 拼接类型 0（RESPONSE_VALUE）输出，遇到类型 2（结束包）停止
            output = ""
            while True:
                req_id, ptype, payload = await _read_packet(reader)
                if ptype == 0 and req_id == 2:
                    output += payload
                elif ptype == 2:
                    break
            return output
        finally:
            writer.close()
            await writer.wait_closed()

    return await asyncio.wait_for(_run(), timeout)