#!/usr/bin/env python3
"""
每日凌晨跑：扫昨天 ai_agent_chat_history，统计情绪信号写入 rl_mood_daily。

信号维度：
- user_msg_count / assistant_msg_count：对话量
- user_total_chars / avg_user_chars：用户发言长度（越短可能越消极）
- negative_hits：消极/丧气关键词命中次数
- silence_word_hits：沉默/不想说话类
- loneliness_hits：孤独/想念类
- hours_active：活跃小时数（去重）
- matched_keywords：命中的具体词（JSON 数组，方便后续分析）
"""

import json
import logging
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta

import pymysql

DB_HOST = "172.18.0.3"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = "123456"
DB_NAME = "xiaozhi_esp32_server"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("mood_collect")

# 关键词库 —— 老年人常见消极表达
NEGATIVE_WORDS = [
    "不想活", "活着没意思", "死了算了", "没意思", "烦死了",
    "不想动", "累死了", "好累", "没劲", "没力气",
    "不舒服", "难受", "疼", "头晕", "胸闷",
    "不想吃", "吃不下", "没胃口",
    "睡不着", "失眠", "整夜", "半夜醒",
    "不想说", "别烦我", "不想聊", "闭嘴", "别说了",
]

SILENCE_WORDS = [
    "不想说话", "不想聊", "别说了", "安静", "别烦",
    "不想理", "懒得说", "算了",
]

LONELINESS_WORDS = [
    "孤独", "一个人", "没人", "想他", "想她", "想儿子", "想女儿",
    "想家人", "没人管", "没人来", "好久没", "都不来看",
    "想念", "寂寞", "冷清",
]


def db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4", autocommit=True,
    )


def list_agents(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT agent_id FROM ai_agent_chat_history")
        return [r[0] for r in cur.fetchall()]


def count_keywords(text, word_list):
    hits = []
    for w in word_list:
        if w in text:
            hits.append(w)
    return hits


def collect_day(conn, agent_id, target_date):
    """收集某天的对话数据并聚合"""
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT chat_type, content, created_at FROM ai_agent_chat_history "
            "WHERE agent_id=%s AND created_at >= %s AND created_at < %s "
            "ORDER BY created_at",
            (agent_id, start, end),
        )
        rows = cur.fetchall()

    if not rows:
        return None

    user_msgs = []
    asst_count = 0
    hours_set = set()
    first_at = None
    last_at = None

    for chat_type, content, created_at in rows:
        if chat_type == 1:  # user
            user_msgs.append(content or "")
        elif chat_type == 2:  # assistant
            asst_count += 1

        if created_at:
            hours_set.add(created_at.hour)
            if first_at is None:
                first_at = created_at
            last_at = created_at

    user_msg_count = len(user_msgs)
    user_total_chars = sum(len(m) for m in user_msgs)
    avg_user_chars = user_total_chars / user_msg_count if user_msg_count > 0 else 0

    # 关键词扫描（合并所有用户消息为一个文本块）
    all_user_text = " ".join(user_msgs)
    neg_hits = count_keywords(all_user_text, NEGATIVE_WORDS)
    sil_hits = count_keywords(all_user_text, SILENCE_WORDS)
    lone_hits = count_keywords(all_user_text, LONELINESS_WORDS)

    all_matched = list(set(neg_hits + sil_hits + lone_hits))

    return {
        "agent_id": agent_id,
        "stat_date": target_date,
        "user_msg_count": user_msg_count,
        "assistant_msg_count": asst_count,
        "user_total_chars": user_total_chars,
        "avg_user_chars": round(avg_user_chars, 1),
        "negative_hits": len(neg_hits),
        "silence_word_hits": len(sil_hits),
        "loneliness_hits": len(lone_hits),
        "hours_active": len(hours_set),
        "first_chat_at": first_at,
        "last_chat_at": last_at,
        "matched_keywords": json.dumps(all_matched, ensure_ascii=False) if all_matched else None,
    }


def upsert(conn, data):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO rl_mood_daily "
            "(agent_id, stat_date, user_msg_count, assistant_msg_count, "
            "user_total_chars, avg_user_chars, negative_hits, silence_word_hits, "
            "loneliness_hits, hours_active, first_chat_at, last_chat_at, matched_keywords) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            "user_msg_count=VALUES(user_msg_count), assistant_msg_count=VALUES(assistant_msg_count), "
            "user_total_chars=VALUES(user_total_chars), avg_user_chars=VALUES(avg_user_chars), "
            "negative_hits=VALUES(negative_hits), silence_word_hits=VALUES(silence_word_hits), "
            "loneliness_hits=VALUES(loneliness_hits), hours_active=VALUES(hours_active), "
            "first_chat_at=VALUES(first_chat_at), last_chat_at=VALUES(last_chat_at), "
            "matched_keywords=VALUES(matched_keywords)",
            (
                data["agent_id"], data["stat_date"],
                data["user_msg_count"], data["assistant_msg_count"],
                data["user_total_chars"], data["avg_user_chars"],
                data["negative_hits"], data["silence_word_hits"],
                data["loneliness_hits"], data["hours_active"],
                data["first_chat_at"], data["last_chat_at"],
                data["matched_keywords"],
            ),
        )


def main():
    # 默认跑昨天；传参数可以跑指定日期或回填
    if len(sys.argv) > 1:
        target = date.fromisoformat(sys.argv[1])
    else:
        target = date.today() - timedelta(days=1)

    log.info("Collecting mood data for: %s", target)

    conn = db()
    try:
        agents = list_agents(conn)
        log.info("Agents: %s", agents)

        for agent_id in agents:
            data = collect_day(conn, agent_id, target)
            if data is None:
                log.info("  agent=%s: no data for %s", agent_id, target)
                continue
            upsert(conn, data)
            log.info(
                "  agent=%s: msgs=%d, neg=%d, sil=%d, lone=%d, hours=%d, keywords=%s",
                agent_id, data["user_msg_count"],
                data["negative_hits"], data["silence_word_hits"],
                data["loneliness_hits"], data["hours_active"],
                data["matched_keywords"],
            )
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("mood_collect failed: %s", e)
        sys.exit(1)
