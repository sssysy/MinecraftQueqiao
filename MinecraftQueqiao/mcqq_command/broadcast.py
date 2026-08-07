import json
from typing import List, Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer
from ..mcqq_rcon import RCONError, execute
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_broadcast = SV("鹊桥广播指令", pm=3)


def _build_title_json(content: str) -> str:
    """将纯文本构建为黄色加粗的 title JSON 文本。"""
    return json.dumps(
        {"text": content, "color": "yellow", "bold": True},
        ensure_ascii=False,
    )


async def _get_targets(
    group_id: str, servers: Optional[List[MCQQServer]]
) -> List[MCQQServer]:
    """按群绑定 + 选择器筛选目标服务器。servers 为 None 表示全部绑定。"""
    binds = await MCQQBind.get_by_group_id(group_id)
    if not binds:
        return []
    selected_ids = {s.id for s in servers} if servers is not None else None
    targets: List[MCQQServer] = []
    for bind in binds:
        server = await MCQQServer.get_by_name(bind.server_name)
        if server is None:
            continue
        if selected_ids is not None and server.id not in selected_ids:
            continue
        targets.append(server)
    return targets


@sv_mcqq_broadcast.on_prefix("广播")
async def broadcast_command(bot: Bot, ev: Event) -> None:
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mc广播 <内容> 指令")
        return

    text = ev.text.strip()
    if not text:
        await bot.send(
            "用法：mc广播 <广播内容> 或 mc广播 [服务器] <广播内容>"
        )
        return

    # JSON 内容直接透传，不参与服务器选择器解析
    try:
        json.loads(text)
    except json.JSONDecodeError:
        is_json = False
    else:
        is_json = True

    if is_json:
        command = f"title @a title {text}"
        servers: Optional[List[MCQQServer]] = None
    else:
        servers = None
        parts = text.split(maxsplit=1)
        resolved, err = await resolve_servers(parts[0])
        if err:
            await bot.send(err)
            return
        if resolved is not None:
            servers = resolved
            content = parts[1].strip() if len(parts) > 1 else ""
            if not content:
                await bot.send("广播内容为空，请提供要广播的文本")
                return
        else:
            content = text
        command = f"title @a title {_build_title_json(content)}"

    targets = await _get_targets(ev.group_id, servers)
    if not targets:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    # 明确指定服务器：该服务器未开启 RCON 则提示功能依赖
    if servers is not None:
        server = targets[0]
        if not server.rcon_enabled:
            await bot.send(
                f"服务器 [{server.server_name}] 未开启 RCON 功能，"
                "此功能依赖 RCON，请先在网页控制台开启后重试"
            )
            return
        try:
            out = await execute(server, command)
            await bot.send(
                f" [{server.server_name}] 广播成功:\n "
                f"{out if out else '(无输出)'}"
            )
        except RCONError as e:
            logger.error(
                f"[MCQueQiao] [{server.server_name}] 广播失败: {e}"
            )
            await bot.send(f"推送失败：{e}")
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{server.server_name}] 广播未知错误: {e}"
            )
            await bot.send(f" [{server.server_name}] 推送失败，详见控制台")
        return

    # 广播到全部绑定服务器：跳过未开启 RCON 的服务器
    enabled = [s for s in targets if s.rcon_enabled]
    skipped = len(targets) - len(enabled)
    if not enabled:
        await bot.send(
            "推送失败：当前群绑定的服务器均未开启 RCON 功能，"
            "此功能依赖 RCON"
        )
        return

    results = []
    success = 0
    for server in enabled:
        try:
            out = await execute(server, command)
            success += 1
            results.append(
                f" [{server.server_name}] 广播成功:\n "
                f"{out if out else '(无输出)'}"
            )
        except RCONError as e:
            logger.error(
                f"[MCQueQiao] [{server.server_name}] 广播失败: {e}"
            )
            results.append(f" [{server.server_name}] 推送失败: {e}")
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{server.server_name}] 广播未知错误: {e}"
            )
            results.append(f" [{server.server_name}] 推送失败，详见控制台")

    if skipped:
        results.append("部分服务器未开启rcon功能，无法推送")

    if success == 0:
        await bot.send("推送失败：\n" + "\n".join(results))
    else:
        await bot.send("\n".join(results))
