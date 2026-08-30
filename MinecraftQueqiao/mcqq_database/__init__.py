from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlmodel import Field, select
from sqlalchemy.ext.asyncio import AsyncSession

from gsuid_core.utils.database.base_models import BaseIDModel, with_session
from gsuid_core.webconsole.mount_app import GsAdminModel, PageSchema, site
from gsuid_core.utils.database.startup import exec_list

T_MCQQServer = TypeVar("T_MCQQServer", bound="MCQQServer")
T_MCQQBind = TypeVar("T_MCQQBind", bound="MCQQBind")
T_MCQQRconWhitelist = TypeVar("T_MCQQRconWhitelist", bound="MCQQRconWhitelist")

exec_list.extend(
    [
        "ALTER TABLE MCQQServer ADD COLUMN chatimage_enabled INTEGER DEFAULT 0",
        "ALTER TABLE MCQQServer ADD COLUMN display_name TEXT DEFAULT ''",
    ]
)


class MCQQServer(BaseIDModel, table=True):
    """鹊桥服务器配置表（反向 WebSocket）"""

    __tablename__ = "MCQQServer"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    enabled: bool = Field(default=True, title="是否启用")
    server_name: str = Field(
        default="Server",
        title="ServerName",
    )
    display_name: str = Field(
        default="",
        title="服务器外显名",
    )
    access_token: str = Field(
        default="",
        title="access_token",
    )
    chatimage_enabled: bool = Field(
        default=False,
        title="启用 ChatImage",
    )

    @classmethod
    @with_session
    async def get_all_enabled(
        cls: Type[T_MCQQServer], session: AsyncSession
    ) -> List["MCQQServer"]:
        """获取所有启用的服务器配置"""
        result = await session.execute(
            select(cls).where(cls.enabled == True)  # type: ignore
        )
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def get_by_name(
        cls: Type[T_MCQQServer], session: AsyncSession, server_name: str
    ) -> Optional["MCQQServer"]:
        """按服务器名称（WS名）查询配置"""
        result = await session.execute(
            select(cls).where(cls.server_name == server_name)  # type: ignore
        )
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def get_by_id(
        cls: Type[T_MCQQServer], session: AsyncSession, server_id: int
    ) -> Optional["MCQQServer"]:
        """按主键ID查询配置"""
        result = await session.execute(
            select(cls).where(cls.id == server_id)  # type: ignore
        )
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def get_by_display_name(
        cls: Type[T_MCQQServer],
        session: AsyncSession,
        display_name: str,
    ) -> List["MCQQServer"]:
        """按外显名称查询所有配置"""
        result = await session.execute(
            select(cls).where(cls.display_name == display_name)  # type: ignore
        )
        return list(result.scalars().all())


class MCQQBind(BaseIDModel, table=True):
    """群服绑定表"""

    __tablename__ = "MCQQBind"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    server_id: int = Field(default=0, title="服务器ID")
    server_name: str = Field(default="", title="服务器名称")
    group_id: str = Field(default="", title="群号")
    ws_bot_id: str = Field(default="", title="WS机器人ID")
    bot_id: str = Field(default="", title="平台")
    bot_self_id: str = Field(default="", title="机器人自身ID")
    user_type: str = Field(default="group", title="发送类型")
    msg_id: str = Field(default="", title="消息ID")
    user_id: str = Field(default="", title="操作人")

    @classmethod
    @with_session
    async def get_by_server_name(
        cls: Type[T_MCQQBind], session: AsyncSession, server_name: str
    ) -> List["MCQQBind"]:
        """按服务器名称查询所有绑定"""
        result = await session.execute(
            select(cls).where(cls.server_name == server_name)  # type: ignore
        )
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def get_by_group_id(
        cls: Type[T_MCQQBind], session: AsyncSession, group_id: str
    ) -> List["MCQQBind"]:
        """按群号查询所有绑定"""
        result = await session.execute(
            select(cls).where(cls.group_id == group_id)  # type: ignore
        )
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def get_by_server_group(
        cls: Type[T_MCQQBind],
        session: AsyncSession,
        server_name: str,
        group_id: str,
    ) -> Optional["MCQQBind"]:
        """按服务器名称+群号查询绑定"""
        result = await session.execute(
            select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.group_id == group_id,  # type: ignore
            )
        )
        return result.scalar_one_or_none()


class MCQQRconWhitelist(BaseIDModel, table=True):
    """RCON 白名单表"""

    __tablename__ = "MCQQRconWhitelist"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    server_name: str = Field(default="", title="ServerName")
    user_id: str = Field(default="", title="user_id")

    @classmethod
    @with_session
    async def get_by_server_name(
        cls: Type[T_MCQQRconWhitelist],
        session: AsyncSession,
        server_name: str,
    ) -> List["MCQQRconWhitelist"]:
        """按服务器名称查询所有白名单记录"""
        result = await session.execute(
            select(cls).where(cls.server_name == server_name)  # type: ignore
        )
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def get_by_user_id(
        cls: Type[T_MCQQRconWhitelist],
        session: AsyncSession,
        user_id: str,
    ) -> List["MCQQRconWhitelist"]:
        """按用户ID查询所有关联的服务器白名单记录"""
        result = await session.execute(
            select(cls).where(cls.user_id == user_id)  # type: ignore
        )
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def get_by_server_and_user(
        cls: Type[T_MCQQRconWhitelist],
        session: AsyncSession,
        server_name: str,
        user_id: str,
    ) -> Optional["MCQQRconWhitelist"]:
        """按服务器名称和用户ID查询白名单记录"""
        result = await session.execute(
            select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.user_id == user_id,  # type: ignore
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def is_whitelisted(
        cls: Type[T_MCQQRconWhitelist],
        session: AsyncSession,
        server_name: str,
        user_id: str,
    ) -> bool:
        """检查指定用户是否在指定服务器的 RCON 白名单中"""
        result = await session.execute(
            select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.user_id == user_id,  # type: ignore
            )
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    @with_session
    async def get_all(
        cls: Type[T_MCQQRconWhitelist],
        session: AsyncSession,
    ) -> List["MCQQRconWhitelist"]:
        """获取所有白名单记录"""
        result = await session.execute(select(cls))
        return list(result.scalars().all())


@site.register_admin
class MCQQServerAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="绑定服务器",
        icon="fa fa-server",
    )  # type: ignore
    model = MCQQServer


@site.register_admin
class MCQQBindAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="群服绑定表",
        icon="fa fa-link",
    )  # type: ignore
    model = MCQQBind


@site.register_admin
class MCQQRconWhitelistAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="RCON白名单",
        icon="fa fa-shield",
    )  # type: ignore
    model = MCQQRconWhitelist

