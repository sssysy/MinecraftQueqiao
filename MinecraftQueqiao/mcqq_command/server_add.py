import time
from typing import Optional

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV, get_plugin_available_prefix

from ..mcqq_database import MCQQBind, MCQQServer
from ..utils.helpers.server_select import resolve_servers

sv_mcqq_server_manage = SV("鹊桥服务器管理指令", pm=3)

SESSION_TIMEOUT = 300.0


@sv_mcqq_server_manage.on_command("添加服务器")
async def add_server_command(bot: Bot, ev: Event) -> None:
    # 仅允许在私聊中进行添加服务器多步会话
    if ev.user_type != "direct":
        await bot.send("请私聊执行此命令")
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

    # Step 1: 服务器名称
    server_name = await _ask_step("[1/5] 请输入服务器名称(鹊桥 server_name)")
    if server_name is None:
        await bot.send("添加服务器会话超时，已自动取消")
        return

    # Step 2: 服务器外显名
    display_name_raw = await _ask_step("[2/5] 请输入服务器外显名(若无输入\"跳过\")")
    if display_name_raw is None:
        await bot.send("添加服务器会话超时，已自动取消")
        return
    display_name = (
        ""
        if display_name_raw in ["跳过", '"跳过"', '“跳过”', "'跳过'"]
        else display_name_raw
    )

    # Step 3: access_token
    access_token_raw = await _ask_step("[3/5] 请输入access_token(若无输入\"跳过\")")
    if access_token_raw is None:
        await bot.send("添加服务器会话超时，已自动取消")
        return
    access_token = (
        ""
        if access_token_raw in ["跳过", '"跳过"', '“跳过”', "'跳过'"]
        else access_token_raw
    )

    # Step 4: 服务器地址
    server_address = await _ask_step("[4/5] 请输入服务器地址")
    if server_address is None:
        await bot.send("添加服务器会话超时，已自动取消")
        return

    # Step 5: 启用 ChatImage Mod
    chatimage_raw = await _ask_step("[5/5] 启用 ChatImage Mod(是 / 否)")
    if chatimage_raw is None:
        await bot.send("添加服务器会话超时，已自动取消")
        return
    chatimage_enabled = chatimage_raw == "是"

    # 写入数据库：若已存在则更新，不存在则插入
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
    else:
        await MCQQServer.full_insert_data(
            server_name=server_name,
            display_name=display_name,
            access_token=access_token,
            server_address=server_address,
            chatimage_enabled=chatimage_enabled,
            enabled=True,
        )
        logger.info(f"[MCQueQiao] 新增服务器 '{server_name}' 成功")

    prefix = get_plugin_available_prefix("MinecraftQueqiao")
    await bot.send(
        f"服务器绑定成功，请回到群内使用 [{prefix}群服绑定] 以绑定服务器！"
    )


@sv_mcqq_server_manage.on_command("删除服务器")
async def delete_server_command(bot: Bot, ev: Event) -> None:
    server_text = ev.text.strip()
    if not server_text:
        await bot.send("格式错误，请使用 mc删除服务器<服务器>，例如 mc删除服务器香草纪元")
        return

    servers, err = await resolve_servers(server_text)
    if err:
        await bot.send(err)
        return
    if servers is None or len(servers) != 1:
        await bot.send(
            "请指定一个服务器：mc删除服务器<服务器>，例如 mc删除服务器香草纪元"
        )
        return
    server = servers[0]

    # 删除服务器记录
    res = await MCQQServer.delete_row(id=server.id)
    if res:
        # 同时清理该服务器关联的群绑定记录
        await MCQQBind.delete_row(server_name=server.server_name)
        logger.info(
            f"[MCQueQiao] 已删除服务器 '{server.server_name}' (ID={server.id}) 及其关联绑定"
        )
        await bot.send(f"服务器 [{server.server_name}] 删除成功")
    else:
        await bot.send("删除失败，未找到该服务器或已被删除")
