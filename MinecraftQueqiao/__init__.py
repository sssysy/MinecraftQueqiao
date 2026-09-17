from gsuid_core.sv import Plugins

Plugins(
    name="MinecraftQueqiao",
    force_prefix=["mc"],
    allow_empty_prefix=False,
)

# 确保指令包被加载注册（与 player_info 等子包同级）
from . import mc_login  # noqa: E402,F401

