from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlmodel import Field, select
from sqlalchemy.ext.asyncio import AsyncSession

from gsuid_core.utils.database.base_models import BaseIDModel, with_session
from gsuid_core.webconsole.mount_app import GsAdminModel, PageSchema, site
from gsuid_core.utils.database.startup import exec_list

T_MCQQServer = TypeVar("T_MCQQServer", bound="MCQQServer")
T_MCQQBind = TypeVar("T_MCQQBind", bound="MCQQBind")

exec_list.extend(
    [
        "ALTER TABLE MCQQServer ADD COLUMN show_server_name INTEGER DEFAULT 1",
        "ALTER TABLE MCQQServer ADD COLUMN rcon_enabled INTEGER DEFAULT 0",
        "ALTER TABLE MCQQServer ADD COLUMN rcon_host TEXT DEFAULT ''",
        "ALTER TABLE MCQQServer ADD COLUMN rcon_port INTEGER DEFAULT 25575",
        "ALTER TABLE MCQQServer ADD COLUMN rcon_password TEXT DEFAULT ''",
        "ALTER TABLE MCQQServer ADD COLUMN chatimage_enabled INTEGER DEFAULT 0",
        "ALTER TABLE MCQQServer ADD COLUMN display_name TEXT DEFAULT ''",
        "ALTER TABLE MCQQServer ADD COLUMN display_domain TEXT DEFAULT ''",
        "ALTER TABLE MCQQServer ADD COLUMN ws_mode TEXT DEFAULT 'client'",
    ]
)

class MCQQServer(BaseIDModel, table=True):
    """鹊桥服务器配置表"""

    __tablename__ = "MCQQServer"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    enabled: bool = Field(default=True, title="是否启用")
    ws_mode: str = Field(default="client", title="WS模式 (client(正向)/server(反向))")
    ws_url: str = Field(
        default="ws://127.0.0.1:8080/minecraft/ws",
        title="正向 / 反向 WebSocket 地址",
    )
    server_name: str = Field(default="Server", title="服务器内部名称 (不建议重复)")
    display_name: str = Field(default="", title="服务器外显名称 (不建议重复)")
    display_domain: str = Field(default="", title="服务器外显域名")
    access_token: str = Field(default="", title="access_token (选填)")
    queqiao_version: str = Field(default="v2", title="鹊桥版本 (v1/v2)")
    chatimage_enabled: bool = Field(
        default=False, title="支持聊天框图片显示(ChatImage) MOD"
    )
    show_server_name: bool = Field(
        default=True, title="MC -> 群聊 是否显示服务器名称"
    )
    rcon_enabled: bool = Field(default=False, title="是否开启 RCON")
    rcon_host: str = Field(default="", title="RCON 地址")
    rcon_port: int = Field(default=25575, title="RCON 端口")
    rcon_password: str = Field(default="", title="RCON 密码")




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
        """按服务器名称查询配置"""
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
        """按外显名称查询所有配置（外显名允许重复）"""
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
        label="群群绑定表",
        icon="fa fa-link",
    )  # type: ignore
    model = MCQQBind
