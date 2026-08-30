from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..mcqq_poll import get_poll_jobs_status, refresh_poll_jobs

sv_mcqq_poll = SV("鹊桥定时公告指令", pm=3)


@sv_mcqq_poll.on_fullmatch("刷新定时公告")
async def refresh_poll_command(bot: Bot, ev: Event) -> None:
    """mc刷新定时公告: 重新读取数据库并注册定时公告任务"""
    total_enabled, registered_count, details = await refresh_poll_jobs()

    lines = [
        "⏰【MCQueQiao 定时公告刷新结果】",
        f"📊 已启用配置: {total_enabled} 条 | 成功注册任务: {registered_count} 个",
        "----------------------",
    ]

    if not details:
        lines.append("当前数据库中暂无已启用的定时公告配置。")
    else:
        for item in details:
            status_icon = "✅" if item["status"] == "registered" else "⚠️"
            server_str = f"[{item['server_name']}]" if item["server_name"] else "[全部服务器]"
            line = f"{status_icon} ID:{item['id']} {server_str} - {item['desc']}"
            if item.get("next_run_time"):
                line += f"\n   ⏳ 下次运行: {item['next_run_time']}"
            content_preview = (
                item["content"][:25] + "..."
                if len(item["content"]) > 25
                else item["content"]
            )
            line += f"\n   📝 内容: {content_preview}"
            lines.append(line)

    await bot.send("\n".join(lines))


@sv_mcqq_poll.on_command(("查看定时公告", "定时公告列表"))
async def list_poll_command(bot: Bot, ev: Event) -> None:
    """mc查看定时公告 / mc定时公告列表: 查看当前所有定时公告配置与运行状态"""
    status_list = await get_poll_jobs_status()

    if not status_list:
        await bot.send(
            "当前数据库中暂无任何定时公告记录。\n可前往 Gscore 网页控制台 -> 数据库管理 -> MinecraftQueqiao -> 定时公告 进行添加。"
        )
        return

    lines = [
        "📋【MCQueQiao 定时公告列表】",
        "----------------------",
    ]

    for item in status_list:
        enabled_icon = "🟢" if item["enabled"] else "🔴"
        active_icon = "⏳" if item["is_active"] else "⏹️"
        server_str = f"[{item['server_name']}]" if item["server_name"] else "[全部服务器]"

        line = (
            f"{enabled_icon} ID:{item['id']} {server_str} ({item['desc']})\n"
            f"   状态: {'启用' if item['enabled'] else '禁用'} | 任务: {'运行中 ' + active_icon if item['is_active'] else '未运行'}\n"
            f"   下次运行: {item['next_run_time']}"
        )

        if item.get("remark"):
            line += f"\n   备注: {item['remark']}"

        content_preview = (
            item["content"][:25] + "..."
            if len(item["content"]) > 25
            else item["content"]
        )
        line += f"\n   内容: {content_preview}"
        lines.append(line)

    lines.append("----------------------")
    lines.append("💡 提示: 修改配置后请发送「mc刷新定时公告」生效。")

    await bot.send("\n".join(lines))
