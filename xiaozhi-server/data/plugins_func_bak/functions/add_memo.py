from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

add_memo_function_desc = {
    "type": "function",
    "function": {
        "name": "add_memo",
        "description": "帮用户记住一件事（备忘录）。当用户说帮我记住、记一下、备忘时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "备忘标题，简短概括"},
                "content": {"type": "string", "description": "备忘详细内容，可为空"},
            },
            "required": ["title"],
        },
    },
}

@register_function("add_memo", add_memo_function_desc, ToolType.SYSTEM_CTL)
def add_memo(conn: "ConnectionHandler", title: str, content: str = ""):
    try:
        from plugins_func.functions import memo_db
        mac = getattr(conn, "device_id", "") or ""
        agent_id = memo_db.agent_id_by_mac(mac)
        if not agent_id:
            return ActionResponse(action=Action.REQLLM, result="找不到智能体配置", response="")
        memo_id = memo_db.add_memo(agent_id, title, content)
        logger.bind(tag=TAG).info(f"备忘录已创建: #{memo_id} {title}")
        return ActionResponse(action=Action.REQLLM, result=f"备忘录已创建，编号{memo_id}，标题：{title}", response="")
    except Exception as e:
        logger.bind(tag=TAG).error(f"创建备忘录失败: {e}")
        return ActionResponse(action=Action.REQLLM, result=f"创建备忘录失败: {e}", response="")
