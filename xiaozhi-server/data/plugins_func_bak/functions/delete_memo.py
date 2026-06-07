from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

delete_memo_function_desc = {
    "type": "function",
    "function": {
        "name": "delete_memo",
        "description": "删除一条备忘录。当用户说删掉那条备忘、不用记了时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "memo_id": {"type": "integer", "description": "备忘录编号"},
            },
            "required": ["memo_id"],
        },
    },
}

@register_function("delete_memo", delete_memo_function_desc, ToolType.SYSTEM_CTL)
def delete_memo(conn: "ConnectionHandler", memo_id: int):
    try:
        from plugins_func.functions import memo_db
        mac = getattr(conn, "device_id", "") or ""
        agent_id = memo_db.agent_id_by_mac(mac)
        if not agent_id:
            return ActionResponse(action=Action.REQLLM, result="找不到智能体配置", response="")
        ok = memo_db.delete_memo(agent_id, memo_id)
        if ok:
            return ActionResponse(action=Action.REQLLM, result=f"备忘录 #{memo_id} 已删除", response="")
        return ActionResponse(action=Action.REQLLM, result=f"没找到编号 {memo_id} 的备忘录", response="")
    except Exception as e:
        logger.bind(tag=TAG).error(f"删除备忘录失败: {e}")
        return ActionResponse(action=Action.REQLLM, result=f"删除失败: {e}", response="")
