from . import bind
from . import broadcast
from . import poll
from . import rcon
from . import server_add
from . import status
from . import tp
from . import whisper
from . import ws

from ..mcqq_core import forward as _forward  # noqa: F401  注册 QQ→MC 转发
from ..utils import waypoint as _waypoint  # noqa: F401  注册游戏内触发器
from ..utils import tpa as _tpa  # noqa: F401  注册游戏内 TPA
