import re
from typing import Any

from mcstatus import JavaServer
from mcstatus.motd import Motd

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_status = SV("鹊桥服务器状态指令")

# 本地直连查询（Server List Ping 协议）超时时间（秒）
STATUS_TIMEOUT = 10


def _motd_to_plain(description: Any) -> str:
    """将服务器返回的 MOTD（可能是纯文本或 JSON chat component）转为纯文本。"""
    try:
        return Motd.parse(description).to_plain().strip()
    except Exception:
        return str(description).strip()


def _build_status_block(
    name: str, display_domain: str, status_data: Any | None
) -> str:
    """根据本地直连查询结果组装单个服务器的状态文本块。"""
    online = status_data is not None

    # 服务器地址：本地直连无远端 hostname，直接使用配置的 display_domain
    addr = display_domain
    status_text = "在线" if online else "离线"

    # 游戏版本：status.version.name 去格式码；离线时显示"未知"
    if online:
        version = re.sub(
            r"§[0-9a-fk-or]", "", status_data.version.name
        ) or "未知"
    else:
        version = "未知"

    # 服务器简介：MOTD 转纯文本；离线或无内容时显示"无"
    if online:
        intro = _motd_to_plain(status_data.description) or "无"
    else:
        intro = "无"

    # 玩家数量与列表：离线时显示"- / -"与"无"
    if online:
        online_n = status_data.players.online
        max_n = status_data.players.max
        count_text = f"{online_n} / {max_n}"
        sample = status_data.players.sample or []
        # 玩家名可能携带 § 格式码，清理后再展示
        names = [
            re.sub(r"§[0-9a-fk-or]", "", p.name) for p in sample if p.name
        ]
        list_text = ", ".join(names) if names else "无"
    else:
        count_text = "- / -"
        list_text = "无"

    return (
        f"[{name}] 服务器状态：\n"
        f"服务器地址：{addr}\n"
        f"在线状态：{status_text}\n"
        f"游戏版本：{version}\n"
        f"服务器简介：{intro}\n"
        f"玩家数量：{count_text}\n"
        f"玩家列表：{list_text}\n"
    )


@sv_mcqq_status.on_command("查看")
async def status_command(bot: Bot, ev: Event) -> None:
    # 仅在群聊中执行
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mc查看 [服务器] 指令")
        return

    text = ev.text.strip()

    # 解析可选的服务器选择：空则查询全部，否则按 ID/内部名/外显名筛选
    servers, err = await resolve_servers(text)
    if err:
        await bot.send(err)
        return

    # 查询群绑定的服务器
    binds = await MCQQBind.get_by_group_id(ev.group_id)
    if not binds:
        await bot.send("当前群未绑定任何服务器，请先使用 mc群服绑定 指令")
        return

    targets = []
    for bind in binds:
        server = await MCQQServer.get_by_name(bind.server_name)
        if server is None:
            continue
        if servers is not None and server.id not in {s.id for s in servers}:
            continue
        targets.append(server)

    if not targets:
        await bot.send("未找到匹配的服务器")
        return

    # 逐个查询并汇总结果
    results = []
    for server in targets:
        # 外显名称回退：display_name 为空则使用 server_name
        name = server.display_name or server.server_name
        display_domain = (server.display_domain or "").strip()
        if not display_domain:
            results.append(f" [{name}] 未配置服务器查询地址")
            continue

        try:
            server_obj = await JavaServer.async_lookup(
                display_domain, timeout=STATUS_TIMEOUT
            )
            status_data = await server_obj.async_status()
            results.append(
                _build_status_block(name, display_domain, status_data)
            )
        except (OSError, TimeoutError) as e:
            logger.error(f"[MCQueQiao] [{name}] 直连服务器失败: {e}")
            results.append(f" [{name}] 服务器离线或无法直连")
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{name}] 查询服务器状态失败: {e}"
            )
            results.append(f" [{name}] 查询失败，请稍后重试")

    # 多服务器间用空行分隔
    await bot.send("\n\n".join(results))
