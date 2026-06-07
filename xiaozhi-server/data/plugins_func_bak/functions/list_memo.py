from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

list_memo_function_desc = {
    "type": "function",
    "function": {
        "name": "list_memo",
        "description": "查看用户的备忘录列表。当用户说我记了什么、我的备忘录、帮我看看记了啥时调用。",
        "parameters": {"type": "object", "properties": {}},
    },
}

@register_function("list_memo", list_memo_function_desc, ToolType.SYSTEM_CTL)
def list_memo(conn: "ConnectionHandler"):
    try:
        from plugins_func.functions import memo_db
        mac = getattr(conn, "device_id", "") or ""
        agent_id = memo_db.agent_id_by_mac(mac)
        if not agent_id:
            return ActionResponse(action=Action.REQLLM, result="找不到智能体配置", response="")
        memos = memo_db.list_memo(agent_id)
        if not memos:
            return ActionResponse(action=Action.REQLLM, result="当前没有备忘录", response="")
        lines_out = []
        for m in memos:
            line = "#{} {}".format(m["id"], m["title"])
            if m.get("content"):
                line += ": {}".format(m["content"])
            lines_out.append(line)
        result = "备忘录列表：\n" + "\n".join(lines_out)
        return ActionResponse(action=Action.REQLLM, result=result, response="")
    except Exception as e:
        logger.bind(tag=TAG).error("查询备忘录失败: {}".format(e))
        return ActionResponse(action=Action.REQLLM, result="查询失败: {}".format(e), response="")

