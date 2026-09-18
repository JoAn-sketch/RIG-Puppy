"""reminder: 提醒计划工具集 (4 个工具)。

- add_reminder      创建提醒(每日 daily / 一次性 once)
- list_reminders    列出全部
- delete_reminder   按 id 或标题模糊删
- get_pending_reminders 取"现在该播的"——LLM 在每次会话开场调用一次

LLM 调用示例:
  add_reminder(type="daily", title="吃降压药", content="餐后温水送服一片", fire_time="08:00")
  add_reminder(type="once", title="去医院复诊", content="带病历本", fire_date="2026-05-25", fire_time="09:30")
  get_pending_reminders()
"""

from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions import reminder_db
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()


ADD_REMINDER_DESC = {
    "type": "function",
    "function": {
        "name": "add_reminder",
        "description": (
            "创建一个提醒计划。"
            "适用场景:用户说'每天早上 8 点提醒我吃药''下周一上午 10 点带我去医院''每天晚上 9 点提醒我量血压'等。"
            "type=daily 是每天重复;type=once 是一次性,必须提供具体日期 fire_date。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "daily=每天重复, once=一次性;按用户语义判断",
                    "enum": ["daily", "once"],
                },
                "title": {
                    "type": "string",
                    "description": "简短标题,例如:吃降压药、量血压、去医院复诊",
                },
                "content": {
                    "type": "string",
                    "description": "详细内容(可空),例如:餐后温水送服一片、记得带病历本",
                },
                "fire_time": {
                    "type": "string",
                    "description": "24 小时制 HH:MM,如 08:00、21:30",
                },
                "fire_date": {
                    "type": "string",
                    "description": "type=once 必填,YYYY-MM-DD 格式;type=daily 不要传",
                },
            },
            "required": ["type", "title", "fire_time"],
        },
    },
}


LIST_REMINDERS_DESC = {
    "type": "function",
    "function": {
        "name": "list_reminders",
        "description": "列出当前所有的提醒计划。用户问'我有哪些提醒''我设了什么提醒'时调用。",
        "parameters": {"type": "object", "properties": {}},
    },
}


DELETE_REMINDER_DESC = {
    "type": "function",
    "function": {
        "name": "delete_reminder",
        "description": "删除一个提醒。用户说'取消吃药提醒''把那个复诊的提醒删了'时调用,按标题模糊匹配。",
        "parameters": {
            "type": "object",
            "properties": {
                "title_keyword": {
                    "type": "string",
                    "description": "提醒标题关键词,如'吃药''复诊'",
                },
                "id": {"type": "integer", "description": "或者直接指定 id"},
            },
        },
    },
}


GET_PENDING_DESC = {
    "type": "function",
    "function": {
        "name": "get_pending_reminders",
        "description": (
            "查询当前应该立刻播报给用户的提醒(到点了/已过点未播报/今日一次性的)。"
            "**重要:每次和用户开始新对话(用户说的第一句话)时,先调用此工具一次**;"
            "如果有结果,先把这些提醒亲切地告诉用户,再处理用户原本的话题。"
            "如果返回空列表则正常对话即可,不要刻意提及。"
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def _agent(conn) -> str:
    mac = getattr(conn, "device_id", "") or ""
    return reminder_db.agent_id_by_mac(mac) or ""


@register_function("add_reminder", ADD_REMINDER_DESC, ToolType.SYSTEM_CTL)
def add_reminder(conn: "ConnectionHandler", type: str = "daily",
                 title: str = "", content: str = "",
                 fire_time: str = "", fire_date: str = ""):
    agent_id = _agent(conn)
    if not agent_id:
        return ActionResponse(Action.REQLLM, "找不到当前设备绑定的智能体。", None)

    type_ = (type or "daily").lower()
    if type_ not in ("daily", "once"):
        return ActionResponse(Action.REQLLM, f"类型 {type} 无效,只能是 daily/once。", None)
    if not title.strip() or not fire_time.strip():
        return ActionResponse(Action.REQLLM, "标题和时间都必填。", None)
    if type_ == "once" and not fire_date.strip():
        return ActionResponse(Action.REQLLM, "一次性提醒必须告诉我具体哪一天(YYYY-MM-DD)。", None)

    try:
        rid = reminder_db.add_reminder(
            agent_id, type_, title.strip(), content.strip(),
            fire_time.strip(), fire_date.strip() or None,
        )
    except Exception as e:
        logger.bind(tag=TAG).error(f"add_reminder 失败: {e}")
        return ActionResponse(Action.REQLLM, f"创建提醒失败: {e}", None)

    when = "每天" if type_ == "daily" else fire_date
    summary = (
        f"已为用户创建提醒(id={rid}):{when} {fire_time} {title}"
        + (f" — {content}" if content else "")
        + "。请用一句俏皮话告诉用户已经记下了。"
    )
    return ActionResponse(Action.REQLLM, summary, None)


@register_function("list_reminders", LIST_REMINDERS_DESC, ToolType.SYSTEM_CTL)
def list_reminders(conn: "ConnectionHandler"):
    agent_id = _agent(conn)
    if not agent_id:
        return ActionResponse(Action.REQLLM, "找不到当前设备。", None)
    rows = reminder_db.list_reminders(agent_id)
    if not rows:
        return ActionResponse(Action.REQLLM, "用户当前没有任何提醒计划。请告诉用户。", None)
    lines = []
    for r in rows:
        when = "每天" if r["type"] == "daily" else r.get("fire_date") or "(无日期)"
        body = r.get("content") or ""
        lines.append(f"#{r['id']} {when} {r['fire_time']} {r['title']}{(' — ' + body) if body else ''}")
    txt = "当前提醒计划:\n" + "\n".join(lines) + "\n请用猫咪口吻念给用户听。"
    return ActionResponse(Action.REQLLM, txt, None)


@register_function("delete_reminder", DELETE_REMINDER_DESC, ToolType.SYSTEM_CTL)
def delete_reminder(conn: "ConnectionHandler", title_keyword: str = "", id: int = 0):
    agent_id = _agent(conn)
    if not agent_id:
        return ActionResponse(Action.REQLLM, "找不到当前设备。", None)
    rows = reminder_db.list_reminders(agent_id, only_enabled=False)

    target = None
    if id:
        for r in rows:
            if r["id"] == int(id):
                target = r; break
    if not target and title_keyword:
        kw = title_keyword.strip()
        cands = [r for r in rows if kw in (r["title"] or "")]
        if len(cands) == 1:
            target = cands[0]
        elif len(cands) > 1:
            names = "、".join(f"#{r['id']} {r['title']}" for r in cands)
            return ActionResponse(
                Action.REQLLM,
                f"找到多个匹配的提醒:{names}。请告诉用户具体要删哪一个(说 id)。",
                None,
            )
    if not target:
        return ActionResponse(Action.REQLLM, "没找到这个提醒。请告诉用户没找到。", None)

    reminder_db.delete_reminder(agent_id, target["id"])
    return ActionResponse(
        Action.REQLLM,
        f"已删除提醒「{target['title']}」(id={target['id']})。请俏皮地告诉用户。",
        None,
    )


@register_function("get_pending_reminders", GET_PENDING_DESC, ToolType.SYSTEM_CTL)
def get_pending_reminders(conn: "ConnectionHandler"):
    agent_id = _agent(conn)
    if not agent_id:
        return ActionResponse(Action.REQLLM, "[]", None)
    rows = reminder_db.pending(agent_id)
    if not rows:
        return ActionResponse(Action.REQLLM,
                              "目前没有需要立刻提醒的事。请按用户原话题正常回答即可,不要刻意提到提醒。",
                              None)
    lines = []
    for r in rows:
        when = "今天" if r["type"] == "daily" else r.get("fire_date") or ""
        body = r.get("content") or ""
        lines.append(f"{when} {r['fire_time']} 该 {r['title']}{('(' + body + ')') if body else ''}")
        try:
            reminder_db.mark_fired(r["id"])
        except Exception:
            pass
    txt = (
        "【需要立即播报的提醒】\n" + "\n".join(lines)
        + "\n请你优先用温柔的猫咪口吻,把这些提醒当面告诉用户(挨个念,不要漏),"
        + "提醒完再回答用户原本的话题。"
    )
    return ActionResponse(Action.REQLLM, txt, None)
