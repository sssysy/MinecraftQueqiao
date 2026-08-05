import httpx
from typing import Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_database import MCQQBind, MCQQServer

sv_mcqq_status = SV("鹊桥服务器状态指令")

# mcsrvstat.us v3 接口，{ip} 支持 domain 或 domain:port
STATUS_API = "https://api.mcsrvstat.us/3/{}"


def _build_status_block(name: str, display_domain: str, data: dict) -> str:
    """根据 API 返回数据组装单个服务器的状态文本块。"""
    online: bool = bool(data.get("online", False))

    # 服务器地址：优先用 API 返回的 hostname，缺失则回退配置的 display_domain
    addr = data.get("hostname") or display_domain
    status_text = "在线" if online else "离线"

    # 游戏版本：优先 protocol.name，其次 version；离线时显示"未知"
    if online:
        protocol = data.get("protocol") or {}
        version = protocol.get("name") or data.get("version") or "未知"
    else:
        version = "未知"

    # 服务器简介：motd.clean 用空格连接；离线或无内容时显示"无"
    motd = data.get("motd") or {}
    clean = motd.get("clean") or []
    intro = " ".join(clean).strip() if online else "无"
    if not intro:
        intro = "无"

    # 玩家数量与列表：离线时显示"- / -"与"无"
    if online:
        players = data.get("players") or {}
        online_n = players.get("online", 0)
        max_n = players.get("max", 0)
        count_text = f"{online_n} / {max_n}"
        player_list = players.get("list") or []
        names = [p.get("name", "") for p in player_list if p.get("name")]
        list_text = ", ".join(names) if names else "无"
    else:
        count_text = "- / -"
        list_text = "无"

    return (
        f"========服务器{name}状态========\n"
        f"服务器地址：{addr}\n"
        f"在线状态：{status_text}\n"
        f"游戏版本：{version}\n"
        f"服务器简介：{intro}\n"
        f"玩家数量：{count_text}\n"
        f"玩家列表：{list_text}\n"
        f"==============================="
    )


@sv_mcqq_status.on_prefix("查看")
async def status_command(bot: Bot, ev: Event) -> None:
    # 仅在群聊中执行
    if ev.user_type != "group" or not ev.group_id:
        await bot.send("请在群聊中使用 mc查看 [服务器ID] 指令")
        return

    text = ev.text.strip()

    # 解析可选的服务器ID：纯数字作为 ID 过滤，非数字提示用法，空则查询全部
    server_id: Optional[int] = None
    if text:
        if text.isdigit():
            server_id = int(text)
        else:
            await bot.send("用法：mc查看 或 mc查看 <服务器ID>，例如 mc查看 1")
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
        if server_id is not None and server.id != server_id:
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
            results.append(f"「{name}」未配置服务器查询地址")
            continue

        url = STATUS_API.format(display_domain)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data: dict = resp.json()
            results.append(_build_status_block(name, display_domain, data))
        except Exception as e:
            logger.error(
                f"[MCQueQiao] [{name}] 查询服务器状态失败: {e}"
            )
            results.append(f"「{name}」查询失败，请稍后重试")

    # 多服务器间用空行分隔
    await bot.send("\n\n".join(results))
