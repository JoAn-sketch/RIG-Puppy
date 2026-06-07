"""
语音切换模式插件 - 根据用户指令切换 AI 陪伴模式
部署到: plugins_func/functions/switch_mode.py
"""
import os
import json
import pymysql
from plugins_func.register import register_function, Action, ActionResponse, ToolType
from config.logger import setup_logging

logger = setup_logging()
TAG = "switch_mode"

DB_HOST = os.getenv("MSG_DB_HOST", "xiaozhi-esp32-server-db")
DB_PORT = int(os.getenv("MSG_DB_PORT", "3306"))
DB_USER = os.getenv("MSG_DB_USER", "root")
DB_PASS = os.getenv("MSG_DB_PASS", "123456")
DB_NAME = os.getenv("MSG_DB_NAME", "xiaozhi_esp32_server")


def _db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


def _get_agent_id(conn):
    mac = getattr(conn, "device_id", "") or ""
    if not mac:
        return None
    with _db() as c, c.cursor() as cur:
        cur.execute(
            "SELECT agent_id FROM ai_device WHERE LOWER(mac_address)=LOWER(%s) LIMIT 1",
            (mac,),
        )
        row = cur.fetchone()
        return row["agent_id"] if row else None


@register_function('switch_mode', {
    "type": "function",
    "function": {
        "name": "switch_mode",
        "description": (
            "切换丁一锅的陪伴模式。当用户说\"切换为XX模式\"/\"换成XX模式\"/\"用XX模式\"时调用。"
            "可用模式: 活泼模式(lively) 倾听模式(listening)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode_name": {
                    "type": "string",
                    "description": "目标模式名称,如:活泼模式、倾听模式"
                }
            },
            "required": ["mode_name"]
        }
    }
}, type=ToolType.SYSTEM_CTL)
def switch_mode(conn, mode_name: str):
    """切换陪伴模式"""
    try:
        agent_id = _get_agent_id(conn)
        if not agent_id:
            logger.bind(tag=TAG).error(f"无法获取agent_id, device_id={getattr(conn, 'device_id', None)}")
            return ActionResponse(action=Action.RESPONSE, response="切换失败,设备未绑定智能体")

        with _db() as c, c.cursor() as cur:
            cur.execute(
                "SELECT id, mode_code, mode_name, system_prompt, context_modules, knowledge_ids "
                "FROM ai_agent_mode WHERE agent_id = %s",
                (agent_id,)
            )
            all_modes = cur.fetchall()

        if not all_modes:
            return ActionResponse(action=Action.RESPONSE, response="当前没有配置任何模式哦")

        # 模糊匹配模式名
        target = None
        mode_name_clean = mode_name.replace("模式", "").strip()
        for m in all_modes:
            if (mode_name_clean in m["mode_name"] or
                m["mode_name"] in mode_name or
                mode_name_clean == m["mode_code"]):
                target = m
                break

        if not target:
            names = "、".join([m["mode_name"] for m in all_modes])
            return ActionResponse(
                action=Action.RESPONSE,
                response=f"没有找到\"{mode_name}\"这个模式哦,我现在支持的模式有: {names}"
            )

        # 应用新模式的 prompt
        mode_prompt = target.get("system_prompt")
        context_modules = None
        raw = target.get("context_modules")
        if raw:
            if isinstance(raw, str):
                context_modules = json.loads(raw)
            elif isinstance(raw, dict):
                context_modules = raw

        # 更新知识库列表
        kid_raw = target.get("knowledge_ids")
        if kid_raw:
            if isinstance(kid_raw, str):
                conn._current_knowledge_ids = [str(k) for k in json.loads(kid_raw)]
            elif isinstance(kid_raw, list):
                conn._current_knowledge_ids = [str(k) for k in kid_raw]

        # 重新构建增强 prompt
        enhanced_prompt = conn.prompt_manager.build_enhanced_prompt(
            conn.config["prompt"], conn.device_id, conn.client_ip,
            mode_prompt=mode_prompt,
            context_modules=context_modules,
        )
        if enhanced_prompt:
            conn.change_system_prompt(enhanced_prompt)

        # 更新动作系统的模式标记
        conn._current_mode_code = target["mode_code"]

        logger.bind(tag=TAG).info(f"模式切换成功: {target['mode_name']} ({target['mode_code']})")

        return ActionResponse(
            action=Action.RESPONSE,
            response=f"好嘞,已经切换到{target['mode_name']}啦!"
        )

    except Exception as e:
        logger.bind(tag=TAG).error(f"切换模式失败: {e}")
        return ActionResponse(action=Action.RESPONSE, response="切换模式时出了点问题,稍后再试试")
