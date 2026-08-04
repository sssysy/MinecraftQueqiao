from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlmodel import Field, select
from sqlalchemy.ext.asyncio import AsyncSession

from gsuid_core.utils.database.base_models import BaseIDModel, with_session
from gsuid_core.webconsole.mount_app import GsAdminModel, PageSchema, site

T_MCQQServer = TypeVar("T_MCQQServer", bound="MCQQServer")


class MCQQServer(BaseIDModel, table=True):
    """鹊桥服务器配置表"""

    __tablename__ = "MCQQServer"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    server_name: str = Field(default="", title="服务器名称")
    ws_url: str = Field(
        default="ws://127.0.0.1:8080/minecraft/ws",
        title="WebSocket地址",
    )
    access_token: str = Field(default="", title="访问令牌")
    queqiao_version: str = Field(default="v2", title="鹊桥版本(v1/v2)")
    enabled: bool = Field(default=True, title="是否启用")
    group_ids: str = Field(default="", title="关联群号(逗号分隔)")

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


@site.register_admin
class MCQQServerAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="鹊桥服务器管理",
        icon="fa fa-server",
    )  # type: ignore
    model = MCQQServer
