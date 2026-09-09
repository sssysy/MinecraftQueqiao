from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlmodel import Field, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gsuid_core.utils.database.base_models import BaseIDModel, with_session
from gsuid_core.webconsole.mount_app import GsAdminModel, PageSchema, site
from gsuid_core.utils.database.startup import exec_list

T_MCQQServer = TypeVar("T_MCQQServer", bound="MCQQServer")
T_MCQQBind = TypeVar("T_MCQQBind", bound="MCQQBind")
T_MCQQRconWhitelist = TypeVar("T_MCQQRconWhitelist", bound="MCQQRconWhitelist")
T_MCQQUserBind = TypeVar("T_MCQQUserBind", bound="MCQQUserBind")
T_MCQQPoll = TypeVar("T_MCQQPoll", bound="MCQQPoll")
T_MCQQWaypoint = TypeVar("T_MCQQWaypoint", bound="MCQQWaypoint")

exec_list.extend(
    [
        "ALTER TABLE MCQQServer ADD COLUMN chatimage_enabled INTEGER DEFAULT 0",
        "ALTER TABLE MCQQServer ADD COLUMN display_name TEXT DEFAULT ''",
        "ALTER TABLE MCQQServer ADD COLUMN server_address TEXT DEFAULT ''",
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
    server_address: str = Field(
        default="",
        title="服务器地址(IP/域名)",
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


class MCQQUserBind(BaseIDModel, table=True):
    """玩家绑定表（用户与MC游戏角色名绑定）"""

    __tablename__ = "MCQQUserBind"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    user_id: str = Field(default="", title="用户ID")
    player_name: str = Field(default="", title="MC游戏ID")
    bot_id: str = Field(default="", title="平台")

    @classmethod
    @with_session
    async def get_by_user_id(
        cls: Type[T_MCQQUserBind],
        session: AsyncSession,
        user_id: str,
    ) -> Optional["MCQQUserBind"]:
        """按用户ID查询绑定记录"""
        result = await session.execute(
            select(cls).where(cls.user_id == user_id)  # type: ignore
        )
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def get_by_player_name(
        cls: Type[T_MCQQUserBind],
        session: AsyncSession,
        player_name: str,
    ) -> Optional["MCQQUserBind"]:
        """按MC游戏ID查询绑定记录"""
        result = await session.execute(
            select(cls).where(cls.player_name == player_name)  # type: ignore
        )
        return result.scalars().first()

    @classmethod
    @with_session
    async def get_all(
        cls: Type[T_MCQQUserBind],
        session: AsyncSession,
    ) -> List["MCQQUserBind"]:
        """获取所有玩家绑定记录"""
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


@site.register_admin
class MCQQUserBindAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="玩家绑定表",
        icon="fa fa-user",
    )  # type: ignore
    model = MCQQUserBind


class MCQQPoll(BaseIDModel, table=True):
    """定时公告配置表"""

    __tablename__ = "MCQQPoll"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    enabled: bool = Field(default=True, title="是否启用")
    server_name: str = Field(default="", title="ServerName")
    content: str = Field(default="", title="公告内容")
    schedule_rule: str = Field(
        default="",
        title="推送时间/间隔(五位 cron 或 Unix 时间戳)",
    )
    remark: str = Field(default="", title="备注")

    @classmethod
    @with_session
    async def get_all_enabled(
        cls: Type[T_MCQQPoll], session: AsyncSession
    ) -> List["MCQQPoll"]:
        """获取所有启用的定时公告配置"""
        result = await session.execute(
            select(cls).where(cls.enabled == True)  # type: ignore
        )
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def get_all(
        cls: Type[T_MCQQPoll], session: AsyncSession
    ) -> List["MCQQPoll"]:
        """获取所有定时公告记录"""
        result = await session.execute(select(cls))
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def get_by_id(
        cls: Type[T_MCQQPoll], session: AsyncSession, poll_id: int
    ) -> Optional["MCQQPoll"]:
        """按主键ID查询定时公告"""
        result = await session.execute(
            select(cls).where(cls.id == poll_id)  # type: ignore
        )
        return result.scalar_one_or_none()

    @classmethod
    @with_session
    async def get_by_server_name(
        cls: Type[T_MCQQPoll], session: AsyncSession, server_name: str
    ) -> List["MCQQPoll"]:
        """按服务器名称查询定时公告"""
        result = await session.execute(
            select(cls).where(cls.server_name == server_name)  # type: ignore
        )
        return list(result.scalars().all())


@site.register_admin
class MCQQPollAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="定时公告",
        icon="fa fa-clock-o",
    )  # type: ignore
    model = MCQQPoll


class MCQQWaypoint(BaseIDModel, table=True):
    """MC 路径点列表"""

    __tablename__ = "MCQQWaypoint"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    server_name: str = Field(default="", title="ServerName")
    point_name: str = Field(default="", title="路径点名称")
    player_name: str = Field(default="", title="创建者")
    x: float = Field(default=0.0, title="X坐标")
    y: float = Field(default=0.0, title="Y坐标")
    z: float = Field(default=0.0, title="Z坐标")
    dimension: str = Field(default="minecraft:overworld", title="维度")
    is_global: bool = Field(default=False, title="全局路径点")

    @classmethod
    @with_session
    async def get_point(
        cls: Type[T_MCQQWaypoint],
        session: AsyncSession,
        server_name: str,
        point_name: str,
        player_name: Optional[str] = None,
    ) -> Optional["MCQQWaypoint"]:
        """按服务器名称和地标名获取路径点。
        若指定了 player_name，优先匹配该玩家的私有路径点；若无私有路径点则匹配全局路径点。
        """
        if player_name:
            result = await session.execute(
                select(cls).where(
                    cls.server_name == server_name,  # type: ignore
                    cls.point_name == point_name,  # type: ignore
                    cls.player_name == player_name,  # type: ignore
                    cls.is_global == False,  # type: ignore
                )
            )
            point = result.scalar_one_or_none()
            if point is not None:
                return point

        result = await session.execute(
            select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.point_name == point_name,  # type: ignore
                cls.is_global == True,  # type: ignore
            )
        )
        return result.scalars().first()

    @classmethod
    @with_session
    async def get_list(
        cls: Type[T_MCQQWaypoint],
        session: AsyncSession,
        server_name: str,
        player_name: Optional[str] = None,
    ) -> List["MCQQWaypoint"]:
        """获取指定服务器的路径点列表（包括全部全局路径点与该玩家个人的私有路径点）"""
        if player_name:
            result = await session.execute(
                select(cls).where(
                    cls.server_name == server_name,  # type: ignore
                    or_(cls.is_global == True, cls.player_name == player_name),  # type: ignore
                )
            )
        else:
            result = await session.execute(
                select(cls).where(
                    cls.server_name == server_name,  # type: ignore
                    cls.is_global == True,  # type: ignore
                )
            )
        return list(result.scalars().all())

    @classmethod
    @with_session
    async def add_or_update(
        cls: Type[T_MCQQWaypoint],
        session: AsyncSession,
        server_name: str,
        point_name: str,
        player_name: str,
        x: float,
        y: float,
        z: float,
        dimension: str = "minecraft:overworld",
        is_global: bool = False,
    ) -> "MCQQWaypoint":
        """新增或更新路径点"""
        if is_global:
            stmt = select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.point_name == point_name,  # type: ignore
                cls.is_global == True,  # type: ignore
            )
        else:
            stmt = select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.point_name == point_name,  # type: ignore
                cls.player_name == player_name,  # type: ignore
                cls.is_global == False,  # type: ignore
            )
        result = await session.execute(stmt)
        point = result.scalar_one_or_none()
        if point:
            point.x = x
            point.y = y
            point.z = z
            point.dimension = dimension
            point.player_name = player_name
            await session.commit()
            return point
        else:
            new_point = cls(
                server_name=server_name,
                point_name=point_name,
                player_name=player_name,
                x=x,
                y=y,
                z=z,
                dimension=dimension,
                is_global=is_global,
            )
            session.add(new_point)
            await session.commit()
            await session.refresh(new_point)
            return new_point

    @classmethod
    @with_session
    async def delete_point(
        cls: Type[T_MCQQWaypoint],
        session: AsyncSession,
        server_name: str,
        point_name: str,
        player_name: Optional[str] = None,
        is_global: bool = False,
    ) -> bool:
        """删除指定路径点"""
        if is_global:
            stmt = select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.point_name == point_name,  # type: ignore
                cls.is_global == True,  # type: ignore
            )
        else:
            if not player_name:
                return False
            stmt = select(cls).where(
                cls.server_name == server_name,  # type: ignore
                cls.point_name == point_name,  # type: ignore
                cls.player_name == player_name,  # type: ignore
                cls.is_global == False,  # type: ignore
            )
        result = await session.execute(stmt)
        point = result.scalar_one_or_none()
        if point:
            await session.delete(point)
            await session.commit()
            return True
        return False


@site.register_admin
class MCQQWaypointAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="mc路径点列表",
        icon="fa fa-map-marker",
    )  # type: ignore
    model = MCQQWaypoint



