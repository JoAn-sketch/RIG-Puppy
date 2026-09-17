#!/usr/bin/env python3
"""
每周日 20:00 给家属推送本周老人活动摘要。

数据源:
- rl_message_log: 本周发的消息条数 + 按 template_key 分类
- rl_reminders: 本周激活的提醒条数 (last_fired_at)
- ai_agent_chat_history: 本周对话条数 (粗略活跃度)
- ai_agent_plugin_mapping: 读 WxPusher app_token
- rl_contacts: 家属 wxpusher_uid

只推 wxpusher_uid 不为空的家属。
"""

import json
import logging
import sys
import time
from datetime import datetime, timedelta

import pymysql
import requests

DB_HOST = "172.18.0.3"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = "123456"
DB_NAME = "xiaozhi_esp32_server"
SEND_MSG_PLUGIN_ID = "SYSTEM_PLUGIN_SEND_MESSAGE"
WXPUSHER_ENDPOINT = "https://wxpusher.zjiecode.com/api/send/message"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("weekly_summary")


def db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4", autocommit=True,
    )


def get_wxpusher_token(conn, agent_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT param_info FROM ai_agent_plugin_mapping "
            "WHERE agent_id=%s AND plugin_id=%s",
            (agent_id, SEND_MSG_PLUGIN_ID),
        )
        row = cur.fetchone()
        if not row:
            return None
        info = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return (info or {}).get("wxpusher_app_token", "").strip() or None


def list_family(conn, agent_id):
    """返回 [(contact_id, nickname, relation, wxpusher_uid)]"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, nickname, relation, wxpusher_uid FROM rl_contacts "
            "WHERE agent_id=%s AND enabled=1 AND wxpusher_uid IS NOT NULL AND wxpusher_uid != ''",
            (agent_id,),
        )
        return list(cur.fetchall())


def list_agents(conn):
    """所有有家属配置的 agent_id"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT agent_id FROM rl_contacts "
            "WHERE enabled=1 AND wxpusher_uid IS NOT NULL AND wxpusher_uid != ''"
        )
        return [r[0] for r in cur.fetchall()]


def agent_name(conn, agent_id):
    with conn.cursor() as cur:
        cur.execute("SELECT agent_name FROM ai_agent WHERE id=%s", (agent_id,))
        row = cur.fetchone()
        return row[0] if row else agent_id


def collect(conn, agent_id, since, until):
    """采集 [since, until) 范围内的活动数据"""
    out = {
        "messages_sent": 0,
        "messages_by_template": {},
        "reminders_fired": 0,
        "chat_count": 0,
        "fraud_alerts": 0,
        "active_days": 0,
    }
    with conn.cursor() as cur:
        cur.execute(
            "SELECT template_key, COUNT(*) FROM rl_message_log "
            "WHERE agent_id=%s AND created_at >= %s AND created_at < %s "
            "AND status IN ('success','mocked') "
            "GROUP BY template_key",
            (agent_id, since, until),
        )
        for tk, cnt in cur.fetchall():
            out["messages_by_template"][tk or "unknown"] = cnt
            out["messages_sent"] += cnt

        out["fraud_alerts"] = out["messages_by_template"].get("custom", 0)

        cur.execute(
            "SELECT COUNT(*) FROM rl_reminders "
            "WHERE agent_id=%s AND last_fired_at >= %s AND last_fired_at < %s",
            (agent_id, since, until),
        )
        out["reminders_fired"] = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM ai_agent_chat_history "
            "WHERE agent_id=%s AND created_at >= %s AND created_at < %s",
            (agent_id, since, until),
        )
        out["chat_count"] = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(DISTINCT DATE(created_at)) FROM ai_agent_chat_history "
            "WHERE agent_id=%s AND created_at >= %s AND created_at < %s",
            (agent_id, since, until),
        )
        out["active_days"] = cur.fetchone()[0]
    return out


def render(name, data, since, until):
    """生成摘要文本"""
    period = f"{since.strftime('%m月%d日')} 至 {(until - timedelta(seconds=1)).strftime('%m月%d日')}"
    lines = [
        f"【{name} 本周陪伴摘要】",
        f"时段: {period}",
        "",
        f"• 对话活跃: {data['active_days']}/7 天有对话 (共 {data['chat_count']} 轮)",
        f"• 提醒触发: {data['reminders_fired']} 次 (吃药/作息等)",
        f"• 发出消息: {data['messages_sent']} 条",
    ]
    if data["fraud_alerts"] > 0:
        lines.append(f"• ⚠️ 反诈预警: {data['fraud_alerts']} 次,请关注")

    breakdown = []
    label_map = {
        "miss_you": "想念",
        "call_back": "请回电",
        "safe": "报平安",
        "health_concern": "健康关怀",
        "custom": "自定义/反诈",
    }
    for tk, cnt in data["messages_by_template"].items():
        breakdown.append(f"  - {label_map.get(tk, tk)}: {cnt}")
    if breakdown:
        lines.append("消息明细:")
        lines.extend(breakdown)

    if data["active_days"] == 0 and data["chat_count"] == 0:
        lines.append("")
        lines.append("⚠️ 本周老人没有与噜噜对话过,建议主动联系一下。")
    elif data["active_days"] <= 2:
        lines.append("")
        lines.append(f"本周对话天数偏少 ({data['active_days']}/7),可以问候一下。")

    lines.append("")
    lines.append("—— 噜噜每周自动汇报")
    return "\n".join(lines)


def push(token, uid, summary_title, content):
    payload = {
        "appToken": token,
        "content": content,
        "summary": summary_title[:20],
        "contentType": 1,
        "uids": [uid],
    }
    try:
        r = requests.post(WXPUSHER_ENDPOINT, json=payload, timeout=15)
        data = r.json()
    except Exception as e:
        return False, f"http: {e}"
    if data.get("code") == 1000:
        results = data.get("data") or []
        if results and results[0].get("code") == 1000:
            return True, ""
        return False, str(results)
    return False, f"{data.get('code')}: {data.get('msg')}"


def log_to_db(conn, agent_id, contact_id, nickname, content, status, err):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO rl_message_log "
            "(agent_id, contact_id, nickname, channel, template_key, rendered, status, err_msg) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (agent_id, contact_id, nickname, "wechat", "weekly_summary",
             content, status, err[:500] if err else None),
        )


def main():
    now = datetime.now()
    until = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    since = until - timedelta(days=7)
    log.info("Weekly summary range: %s -> %s", since, until)

    conn = db()
    try:
        agents = list_agents(conn)
        log.info("Agents to process: %s", agents)

        for agent_id in agents:
            token = get_wxpusher_token(conn, agent_id)
            if not token:
                log.warning("agent %s has no wxpusher_app_token, skip", agent_id)
                continue

            name = agent_name(conn, agent_id)
            family = list_family(conn, agent_id)
            data = collect(conn, agent_id, since, until)
            content = render(name, data, since, until)
            log.info("agent=%s name=%s data=%s", agent_id, name, data)
            log.info("content:\n%s", content)

            for contact_id, nickname, relation, uid in family:
                ok, err = push(token, uid, f"{name} 本周摘要", content)
                status = "success" if ok else "error"
                log_to_db(conn, agent_id, contact_id, nickname, content, status, err)
                log.info("  -> %s (%s): %s %s", nickname, relation, status, err)
                time.sleep(0.5)
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("weekly_summary failed: %s", e)
        sys.exit(1)
