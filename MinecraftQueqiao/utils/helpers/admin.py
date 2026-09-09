from typing import Optional

from gsuid_core.logger import logger
from gsuid_core.models import Event

from ...mcqq_database import MCQQRconWhitelist, MCQQUserBind


async def is_admin(
    server_name: str,
    ev: Optional[Event] = None,
    user_id: Optional[str] = None,
    user_pm: int = 6,
    player_name: Optional[str] = None,
) -> bool:
    """判断用户是否具备服务器管理员权限。

    鉴权依据（任一满足即为管理员）：
      1. 是否为群管理员：
         - 传入 Event 时：ev.user_pm <= 3（Bot主人0、超管1、群主2、群管3）
           或 ev.sender 中的 role 属性为 "admin" / "owner"
         - 显式传入 user_pm <= 3 时视为具备管理权限
         - 游戏内触发（无 Event）时：若绑定的 QQ 账号为 Bot 主人或超管亦视为具备管理权限
      2. 是否在对应服务器的 RCON 白名单内：
         - 查询 MCQQRconWhitelist 数据库表
         - 游戏内触发时通过玩家绑定表 (MCQQUserBind) 查找绑定的 QQ 用户后校验白名单

    Args:
        server_name: 目标服务器名称
        ev: GsuidCore Event 对象（群聊触发时传入）
        user_id: 用户 QQ 号（可选）
        user_pm: 用户权限等级（默认 6，<=3 为管理权限）
        player_name: MC 游戏角色名（可选，游戏内触发或已知角色名时传入）

    Returns:
        bool: 是否具备管理员权限
    """
    effective_user_id = user_id
    effective_pm = user_pm

    # 1. 检查是否为群管理员
    if ev is not None:
        if not effective_user_id:
            effective_user_id = ev.user_id
        effective_pm = ev.user_pm

        # 1.1 基于 user_pm 判断（主人 0、超管 1、群主 2、群管 3）
        if effective_pm <= 3:
            return True

        # 1.2 基于 sender role 兜底
        if isinstance(ev.sender, dict):
            role = str(ev.sender.get("role", "")).lower()
            if role in ("admin", "owner"):
                return True
    else:
        # 无 ev 时若显式传入了有效管理权限
        if effective_pm <= 3:
            return True

    # 2. 尝试解析绑定的 MC 角色名或解析 QQ 用户 ID
    bound_user_id: Optional[str] = effective_user_id
    if not bound_user_id and player_name:
        bind = await MCQQUserBind.get_by_player_name(player_name)
        if bind and bind.user_id:
            bound_user_id = bind.user_id

    # 1.3 无 ev 场景（如游戏内触发）：若绑定的 QQ 是 Bot 主人或超管，也视为具备管理权限
    if bound_user_id:
        try:
            from gsuid_core.config import core_config

            masters = core_config.get_config("masters")
            if hasattr(masters, "data"):
                masters = masters.data
            masters = masters or []

            superusers = core_config.get_config("superusers")
            if hasattr(superusers, "data"):
                superusers = superusers.data
            superusers = superusers or []

            if bound_user_id in masters or bound_user_id in superusers:
                return True
        except Exception as e:
            logger.debug(f"[MCQueQiao] 读取 core_config 主人/超管配置失败: {e}")

    # 2. 检查是否在对应服务器的 RCON 白名单内
    if bound_user_id:
        if await MCQQRconWhitelist.is_whitelisted(server_name, bound_user_id):
            return True

    return False
