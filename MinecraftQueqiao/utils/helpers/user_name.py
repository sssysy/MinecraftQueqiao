from gsuid_core.logger import logger


async def resolve_user_name(bot_id: str, user_id: str, group_id: str) -> str:
    """id查名称"""
    try:
        from gsuid_core.utils.database.models import CoreUser

        user = await CoreUser.base_select_data(
            bot_id=bot_id, user_id=user_id, group_id=group_id
        )
        name = (user.user_name if user else "") or ""
        if name and name != "1":
            return str(name)
    except Exception as e:
        logger.debug(f"[MCQueQiao] 查询用户昵称失败: {e}")
    return ""