from sqlalchemy import text

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV
from gsuid_core.utils.database.base_models import engine

sv_mcqq_drop_table = SV("鹊桥清理旧表指令", pm=2)


@sv_mcqq_drop_table.on_fullmatch(("删除旧表", "清除旧表", "清理旧表"))
async def drop_mcqq_old_tables(bot: Bot, ev: Event) -> None:
    try:
        tables_to_drop = ["MCQQServer", "MCQQBind", "mcqqserver", "mcqqbind"]
        async with engine.begin() as conn:
            for table_name in tables_to_drop:
                await conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))

        logger.success("[MCQueQiao] 已成功删除 MCQueQiao 旧数据表")
        await bot.send(
            "✅ 已成功清理 MCQueQiao 旧数据表！\n"
            "⚠️ 请立即重启早柚核心 (GsCore) 以便重新初始化数据库表结构并生效。"
        )
    except Exception as e:
        logger.error(f"[MCQueQiao] 删除旧表失败: {e}")
        await bot.send(f"❌ 清理旧表失败: {e}")
