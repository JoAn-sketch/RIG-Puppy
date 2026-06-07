"""
kids_game.py — 儿童互动游戏插件
LLM 调用入口:
  - kids_ask_question(age_band, content_type)
  - kids_check_answer(question_id, user_answer)
deploy: plugins_func/functions/kids_game.py
"""
import subprocess
import time
from plugins_func.register import register_function, Action, ActionResponse, ToolType
from config.logger import setup_logging

logger = setup_logging()
TAG = "kids_game"

DB_CONTAINER = "xiaozhi-esp32-server-db"
DB_NAME = "xiaozhi_esp32_server"
DB_PASS = "123456"


def _mysql_query(sql):
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", "-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "--batch", "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    lines = [l for l in r.stdout.split("\n") if l.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:]]


def _mysql_exec(sql):
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", "-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "-e", sql]
    subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def _log_session(device_mac, qid, content_type, age_band, is_correct):
    try:
        from datetime import date
        today = date.today().isoformat()
        _mysql_exec(
            f"INSERT INTO rl_kid_session_log "
            f"(device_mac, question_id, content_type, age_band, is_correct, session_date) "
            f"VALUES ('{device_mac}', {qid}, '{content_type}', '{age_band}', "
            f"{1 if is_correct else 0}, '{today}')"
        )
    except Exception as e:
        logger.bind(tag=TAG).debug(f"session log 写入失败: {e}")


def _get_question(age_band, content_type=None):
    type_filter = f"AND content_type='{content_type}'" if content_type else ""
    sql = (
        f"SELECT id, content_type, question, answer, reward_group, comfort_group "
        f"FROM rl_kid_content "
        f"WHERE enabled=1 AND age_band='{age_band}' {type_filter} "
        f"ORDER BY RAND() LIMIT 1"
    )
    rows = _mysql_query(sql)
    return rows[0] if rows else None


def _get_question_by_id(qid):
    rows = _mysql_query(
        f"SELECT id, content_type, question, answer, reward_group, comfort_group "
        f"FROM rl_kid_content WHERE id={qid} AND enabled=1"
    )
    return rows[0] if rows else None


def _check_answer(correct, user_ans):
    c = correct.strip().lower().replace(" ", "")
    u = user_ans.strip().lower().replace(" ", "")
    return c in u or u in c


def _trigger_action(conn, group_code, timing="before"):
    try:
        import asyncio, threading, json
        from core.providers.tools.device_mcp.mcp_handler import call_mcp_tool
        payload = json.dumps({"group_code": group_code, "timing": timing})
        loop = getattr(conn, "loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                call_mcp_tool(conn, conn.mcp_client, "self_play_action_group", payload), loop
            )
        else:
            threading.Thread(
                target=lambda: asyncio.run(
                    call_mcp_tool(conn, conn.mcp_client, "self_play_action_group", payload)
                ), daemon=True
            ).start()
    except Exception as e:
        logger.bind(tag=TAG).debug(f"trigger_action 失败: {e}")


def _get_kid_state(conn):
    if not hasattr(conn, "_kid_game_state"):
        conn._kid_game_state = {"current_qid": None, "correct_streak": 0, "last_q_time": 0}
    return conn._kid_game_state


KIDS_ASK_QUESTION_DESC = {
    "type": "function",
    "function": {
        "name": "kids_ask_question",
        "description": (
            "给小朋友出一道互动题目(谜语/数学/拼音/成语/英语/安全/为什么等)."
            "小朋友说出题/考考我/来一个/再来一道时调用."
            "返回题目文字,直接念给小朋友听."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "age_band": {
                    "type": "string",
                    "enum": ["3-5", "6-8", "9-12"],
                    "description": "年龄段,根据 kid_age_band 上下文选择,默认 6-8"
                },
                "content_type": {
                    "type": "string",
                    "enum": ["riddle", "math", "pinyin", "idiom", "english", "safety", "whyq", ""],
                    "description": "题型;没指定时传空字符串随机选"
                }
            },
            "required": ["age_band", "content_type"]
        }
    }
}


@register_function("kids_ask_question", KIDS_ASK_QUESTION_DESC, type=ToolType.SYSTEM_CTL)
def kids_ask_question(conn, age_band="6-8", content_type=""):
    age_band = age_band if age_band in ("3-5", "6-8", "9-12") else "6-8"
    ct = content_type if content_type else None
    q = _get_question(age_band, ct)
    if not q:
        q = _get_question("6-8", None)
    if not q:
        return ActionResponse(
            action=Action.RESPONSE, result="",
            response="哎呀题库暂时空了,等我想想新题目再来~"
        )

    state = _get_kid_state(conn)
    state["current_qid"] = int(q["id"])
    state["last_q_time"] = time.time()

    type_label = {
        "riddle": "脑筋急转弯", "math": "算术题", "pinyin": "拼音题",
        "idiom": "成语题", "english": "英语题", "safety": "安全题", "whyq": "为什么"
    }.get(q["content_type"], "题目")

    text = "来了来了!" + type_label + ":" + q["question"]
    return ActionResponse(action=Action.RESPONSE, result=str(q["id"]), response=text)


KIDS_CHECK_ANSWER_DESC = {
    "type": "function",
    "function": {
        "name": "kids_check_answer",
        "description": (
            "判断小朋友的回答是否正确,并触发对应的奖励或安抚动作."
            "小朋友说出答案后调用.question_id 是上一次 kids_ask_question 返回的 result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question_id": {
                    "type": "integer",
                    "description": "题目 id,来自上次 kids_ask_question 的 result"
                },
                "user_answer": {
                    "type": "string",
                    "description": "小朋友说的答案,原文传入"
                }
            },
            "required": ["question_id", "user_answer"]
        }
    }
}


@register_function("kids_check_answer", KIDS_CHECK_ANSWER_DESC, type=ToolType.SYSTEM_CTL)
def kids_check_answer(conn, question_id=0, user_answer=""):
    state = _get_kid_state(conn)
    qid = question_id or state.get("current_qid") or 0
    if not qid:
        return ActionResponse(
            action=Action.RESPONSE, result="no_question",
            response="我们还没出题呢,要来一道吗?"
        )
    q = _get_question_by_id(int(qid))
    if not q:
        return ActionResponse(
            action=Action.RESPONSE, result="not_found",
            response="这道题我找不到了,再来一道吧~"
        )
    correct = _check_answer(q["answer"], user_answer)
    state["current_qid"] = None
    device_mac = getattr(conn, "device_id", "") or ""
    _log_session(device_mac, int(qid), q["content_type"], q["age_band"], correct)

    if correct:
        state["correct_streak"] = state.get("correct_streak", 0) + 1
        streak = state["correct_streak"]
        if streak > 0 and streak % 3 == 0:
            _trigger_action(conn, "cute", "after")
            praise = "哇!连续答对" + str(streak) + "题!小主人太厉害了!"
        else:
            _trigger_action(conn, q.get("reward_group", "happy"), "before")
            praises = ["答对啦!你真聪明~", "对对对!小主人脑子转得真快!", "哇塞全对!汪!", "答对了!太棒了!"]
            praise = praises[streak % len(praises)]
        return ActionResponse(action=Action.RESPONSE, result="correct", response=praise)
    else:
        state["correct_streak"] = 0
        _trigger_action(conn, q.get("comfort_group", "comfort"), "after")
        hint = q["answer"]
        msg = "没关系没关系~答案是" + hint + ",记住了吗?下次一定行!"
        return ActionResponse(action=Action.RESPONSE, result="wrong", response=msg)
