from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING
import pymysql
import json
import os

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

def _get_db():
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "xiaozhi-esp32-server-db"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", "123456"),
        database="xiaozhi_esp32_server",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

switch_mode_function_desc = {
    "type": "function",
    "function": {
        "name": "switch_mode",
        "description": "切换对话模式/角色风格。当用户说'切换到专业模式'、'换成倾听模式'、'活泼一点'、'理疗医生模式'、'陪我玩'等时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "mode_name": {
                    "type": "string",
                    "description": "要切换的模式名称或代码，如：活泼模式、专业模式、倾听模式、理疗医生模式、陪伴玩耍模式，或对应代码 lively/professional/listening/therapist/playmate"
                },
            },
            "required": ["mode_name"],
        },
    },
}


@register_function("switch_mode", switch_mode_function_desc, ToolType.CHANGE_SYS_PROMPT)
def switch_mode(conn: "ConnectionHandler", mode_name: str):
    """切换对话模式：基础 prompt 保留，模式 prompt 叠加，按 context_modules 选配渲染"""
    try:
        agent_id = conn.config.get("agent_id") or conn.config.get("id")
        if not agent_id:
            device_id = getattr(conn, "device_id", None)
            if not device_id:
                return ActionResponse(action=Action.RESPONSE, result="失败", response="无法获取智能体信息")

        db = _get_db()
        try:
            with db.cursor() as cursor:
                sql = """
                    SELECT id, mode_name, mode_code, system_prompt, context_modules
                    FROM ai_agent_mode
                    WHERE agent_id = %s
                    AND (mode_name LIKE %s OR mode_code = %s OR mode_name = %s)
                    LIMIT 1
                """
                cursor.execute(sql, (agent_id, f"%{mode_name}%", mode_name, mode_name))
                mode = cursor.fetchone()

                if not mode:
                    cursor.execute(
                        "SELECT mode_name, mode_code FROM ai_agent_mode WHERE agent_id = %s ORDER BY sort",
                        (agent_id,)
                    )
                    all_modes = cursor.fetchall()
                    names = "、".join([f"{m['mode_name']}({m['mode_code']})" for m in all_modes])
                    return ActionResponse(
                        action=Action.RESPONSE,
                        result="未找到",
                        response=f"没有找到「{mode_name}」这个模式，可用的模式有：{names}"
                    )

                mode_prompt = mode["system_prompt"]

                # 解析 context_modules JSON
                ctx_modules = None
                raw = mode.get("context_modules")
                if raw:
                    if isinstance(raw, str):
                        ctx_modules = json.loads(raw)
                    elif isinstance(raw, dict):
                        ctx_modules = raw

                # 解析 knowledge_ids
                kid_raw = mode.get("knowledge_ids")
                knowledge_ids = []
                if kid_raw:
                    if isinstance(kid_raw, str):
                        knowledge_ids = json.loads(kid_raw)
                    elif isinstance(kid_raw, list):
                        knowledge_ids = kid_raw
                # 存到 conn 上供知识库插件使用
                conn._current_knowledge_ids = [str(k) for k in knowledge_ids]

                # 基础 prompt 始终保留，模式 prompt 叠加渲染
                base_prompt = conn.config.get("prompt", "")
                enhanced = conn.prompt_manager.build_enhanced_prompt(
                    base_prompt, conn.device_id, conn.client_ip,
                    mode_prompt=mode_prompt,
                    context_modules=ctx_modules,
                )
                if enhanced:
                    conn.change_system_prompt(enhanced)
                else:
                    conn.change_system_prompt(base_prompt)

                logger.bind(tag=TAG).info(
                    f"切换模式: {mode['mode_name']} ({mode['mode_code']}), "
                    f"modules: {ctx_modules}"
                )
                return ActionResponse(
                    action=Action.RESPONSE,
                    result="成功",
                    response=f"好的，已切换到{mode['mode_name']}～"
                )
        finally:
            db.close()

    except Exception as e:
        logger.bind(tag=TAG).error(f"switch_mode 异常: {e}")
        return ActionResponse(action=Action.RESPONSE, result="失败", response="模式切换失败，请稍后再试")
