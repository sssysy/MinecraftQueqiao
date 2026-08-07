from gsuid_core.logger import logger


async def get_group_name(group_id: str) -> str:
    """数据库查群聊名称，未找到返回空字符串。"""
    try:
        from gsuid_core.utils.database.models import CoreGroup

        group = await CoreGroup.base_select_data(group_id=group_id)
        if group is not None and group.group_name and group.group_name != "1":
            return str(group.group_name)
    except Exception as e:
        logger.debug(f"[MCQueQiao] 获取群名称失败: {e}")
    return ""