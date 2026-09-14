import time
from typing import Any, Dict, List, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQPoll, MCQQRconWhitelist, MCQQServer
from ..utils.helpers.arg_parse import decode_arg, split_cmd_args
from ..utils.helpers.server_resolve import resolve_servers

sv_mcqq_server_manage = SV("鹊桥服务器管理指令", pm=3)

SESSION_TIMEOUT = 300.0

_USAGE = (
    "用法：mc添加服务器 <服务器名> <IP[:端口]> [外显名] [access_token] [ChatImage是/否]\n"
    "可选参数缺省请写「跳过」，参数内空格用 \\+\n"
    "例如：mc添加服务器 香草 mc.example.com:25565 香草 跳过 否"
)

_MISSING_HINT = (
    "字段顺序：服务器名 IP 外显名 access_token ChatImage\n"
    "请向用户追问缺失字段后，携带完整参数再次调用本工具；不要编造 IP 或 access_token。"
)


def _is_skip(value: str) -> bool:
    cleaned = value.strip().strip("\"'“”‘’「」")
    return cleaned in {"", "跳过", "skip", "SKIP"}


def _parse_chatimage(raw: str) -> bool:
    return raw.strip().lower() in {"是", "y", "yes", "true", "开"}


def _ai_return(text: str) -> None:
    try:
        from gsuid_core.ai_core.trigger_bridge import ai_return

        ai_return(text)
    except Exception:
        pass


def _is_ai_bot(bot: Bot) -> bool:
    try:
        from gsuid_core.ai_core.trigger_bridge import MockBot

        return isinstance(bot, MockBot)
    except Exception:
        return False


def _parse_add_args(
    text: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[str]]:
    """解析单次添加服务器参数。

    位置顺序：服务器名 IP [外显名] [access_token] [ChatImage]
    Returns:
        (data, err, missing) — data 为已解析字段；err 为用法错误；missing 为缺失必填项。
    """
    tokens = split_cmd_args(text)
    if len(tokens) > 5:
        return None, _USAGE, []

    decoded = [decode_arg(t) for t in tokens]
    data: Dict[str, Any] = {}
    missing: List[str] = []

    if len(decoded) >= 1 and not _is_skip(decoded[0]):
        data["server_name"] = decoded[0].strip()
    else:
        missing.append("服务器名")

    if len(decoded) >= 2 and not _is_skip(decoded[1]):
        data["server_address"] = decoded[1].strip()
    else:
        missing.append("服务器IP")

    if len(decoded) >= 3:
        data["display_name"] = (
            "" if _is_skip(decoded[2]) else decoded[2].strip()
        )
    else:
        data["display_name"] = ""

    if len(decoded) >= 4:
        data["access_token"] = (
            "" if _is_skip(decoded[3]) else decoded[3].strip()
        )
    else:
        data["access_token"] = ""

    if len(decoded) >= 5:
        data["chatimage_enabled"] = _parse_chatimage(decoded[4])
    else:
        data["chatimage_enabled"] = False

    return data, None, missing


async def _upsert_server(
    server_name: str,
    display_name: str,
    access_token: str,
    server_address: str,
    chatimage_enabled: bool,
) -> str:
    """写入或覆盖服务器配置，返回「新增」/「更新」。"""
    existing = await MCQQServer.get_by_name(server_name)
    if existing:
        await MCQQServer.update_data_by_data(
            {"server_name": server_name},
            {
                "display_name": display_name,
                "access_token": access_token,
                "server_address": server_address,
                "chatimage_enabled": chatimage_enabled,
                "enabled": True,
            },
        )
        logger.info(f"[MCQueQiao] 服务器 '{server_name}' 配置已覆盖更新")
        return "更新"

    await MCQQServer.full_insert_data(
        server_name=server_name,
        display_name=display_name,
        access_token=access_token,
        server_address=server_address,
        chatimage_enabled=chatimage_enabled,
        enabled=True,
    )
    logger.info(f"[MCQueQiao] 新增服务器 '{server_name}' 成功")
    return "新增"


async def _finish_add(bot: Bot, data: Dict[str, Any]) -> None:
    action = await _upsert_server(
        server_name=data["server_name"],
        display_name=data.get("display_name", ""),
        access_token=data.get("access_token", ""),
        server_address=data["server_address"],
        chatimage_enabled=bool(data.get("chatimage_enabled", False)),
    )
    _ai_return(
        f"{action}服务器 '{data['server_name']}' 成功："
        f"地址={data['server_address']}，"
        f"外显名={data.get('display_name') or '(空)'}，"
        f"ChatImage={'开' if data.get('chatimage_enabled') else '关'}。"
        "提醒用户到群内使用 mc群服绑定。"
    )
    await bot.send(
        "服务器添加完毕\n请回到群内通过 [mc群服绑定] 进行群服绑定"
    )


@sv_mcqq_server_manage.on_command(
    "添加服务器",
    block=True,
    to_ai="""添加或更新一个 Minecraft 鹊桥服务器配置。仅限私聊。
当用户要添加服务器、配置鹊桥、接入 MC 服务器时调用。
若返回缺少字段，向用户追问补齐后再调用；不要编造 IP 或 access_token。
同名服务器会覆盖更新。成功后需在群内 mc群服绑定。

Args:
    text: 空格分隔，位置固定 5 段，后 3 段可省略或写「跳过」：
          <服务器名> <IP[:端口]> [外显名] [access_token] [ChatImage是/否]
          参数内空格用 \\+ 转义。
          例1: "香草 mc.example.com:25565"
          例2: "香草 mc.example.com:25565 香草 跳过 否"
          例3: "myserver 1.2.3.4:25565 跳过 mytoken 是"
""",
)
async def add_server_command(bot: Bot, ev: Event) -> None:
    if ev.user_type != "direct":
        _ai_return("错误：添加服务器仅支持私聊，请让用户私聊机器人后再调用。")
        await bot.send("请私聊添加服务器")
        return

    text = (ev.text or "").strip()

    if _is_ai_bot(bot):
        data, err, missing = _parse_add_args(text)
        if err:
            _ai_return(f"参数错误：{err}")
            await bot.send(err)
            return
        if missing:
            _ai_return(
                f"错误：缺少{'、'.join(missing)}。{_MISSING_HINT}"
            )
            await bot.send(f"缺少参数：{'、'.join(missing)}\n{_USAGE}")
            return
        await _finish_add(bot, data)
        return

    if text:
        data, err, missing = _parse_add_args(text)
        if err:
            await bot.send(f"{err}\n也可直接发送「mc添加服务器」进入分步添加")
            return
        if missing:
            await bot.send(
                f"缺少参数：{'、'.join(missing)}\n"
                "请直接发送「mc添加服务器」进入分步添加"
            )
            return
        await _finish_add(bot, data)
        return

    start_time = time.time()

    async def _ask_step(prompt: str) -> Optional[str]:
        remaining = SESSION_TIMEOUT - (time.time() - start_time)
        if remaining <= 0:
            return None
        resp = await bot.receive_resp(prompt, timeout=remaining)
        if resp is None or not hasattr(resp, "text"):
            return None
        return resp.text.strip()

    server_name = await _ask_step("[1/5] 请输入服务器名称(鹊桥 server_name)")
    if server_name is None:
        _ai_return(
            f"错误：交互未完成，缺少服务器名、服务器IP等参数。{_MISSING_HINT}"
        )
        await bot.send("绑定超时，请重新开始。")
        return

    display_name_raw = await _ask_step(
        '[2/5] 请输入服务器外显名(若无输入"跳过")'
    )
    if display_name_raw is None:
        _ai_return(
            f"错误：交互未完成，缺少外显名、服务器IP等参数。{_MISSING_HINT}"
        )
        await bot.send("绑定超时，请重新开始。")
        return
    display_name = "" if _is_skip(display_name_raw) else display_name_raw

    access_token_raw = await _ask_step(
        '[3/5] 请输入access_token(若无输入"跳过")'
    )
    if access_token_raw is None:
        _ai_return(
            f"错误：交互未完成，缺少 access_token、服务器IP等参数。{_MISSING_HINT}"
        )
        await bot.send("绑定超时，请重新开始。")
        return
    access_token = "" if _is_skip(access_token_raw) else access_token_raw

    server_address = await _ask_step("[4/5] 请输入 MC 服务器 IP")
    if server_address is None:
        _ai_return(f"错误：交互未完成，缺少服务器IP。{_MISSING_HINT}")
        await bot.send("绑定超时，请重新开始。")
        return

    chatimage_raw = await _ask_step("[5/5] 启用 ChatImage Mod(是 / 否)")
    if chatimage_raw is None:
        _ai_return(
            "错误：交互未完成，ChatImage 未确认，可默认否后重试。"
            f"{_MISSING_HINT}"
        )
        await bot.send("绑定超时，请重新开始。")
        return

    await _finish_add(
        bot,
        {
            "server_name": server_name,
            "display_name": display_name,
            "access_token": access_token,
            "server_address": server_address,
            "chatimage_enabled": _parse_chatimage(chatimage_raw),
        },
    )


@sv_mcqq_server_manage.on_command("删除服务器", block=True)
async def delete_server_command(bot: Bot, ev: Event) -> None:
    tokens = split_cmd_args(ev.text)
    if len(tokens) != 1:
        await bot.send(
            "参数传递错误\n用法：mc删除服务器 <服务器>\n例如：mc删除服务器 香草纪元"
        )
        return

    servers, err = await resolve_servers(decode_arg(tokens[0]))
    if err:
        await bot.send(err)
        return
    if not servers or len(servers) != 1:
        await bot.send(
            "未找到服务器 / 服务器名称冲突！\n请通过服务器内部名称删除"
        )
        return
    server = servers[0]

    # 先清理从表关联记录（RCON 白名单、群绑定、定时公告）
    await MCQQRconWhitelist.delete_row(server_name=server.server_name)
    await MCQQBind.delete_row(server_name=server.server_name)
    await MCQQPoll.delete_row(server_name=server.server_name)

    # 删除服务器记录
    res = await MCQQServer.delete_row(id=server.id)
    if res:
        logger.info(
            f"[MC·游戏绑定] 已删除服务器 '{server.server_name}' (ID={server.id}) 及其关联白名单、绑定与定时任务"
        )
        await bot.send(f"服务器 [{server.server_name}] 删除成功")
    else:
        await bot.send("删除失败，未找到该服务器或已被删除")
