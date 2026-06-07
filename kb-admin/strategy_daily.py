#!/usr/bin/env python3
"""
strategy_daily.py — 每日陪伴策略生成
读取用户画像 + 情绪日志 + 提醒记录 → 调 LLM 生成 ~200 字行为策略 → 存入 rl_daily_strategy
cron: 0 0 * * * (每天 00:00)
"""
import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
import requests

ZHIPU_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
DB_CONTAINER = "xiaozhi-esp32-server-db"
DB_NAME = "xiaozhi_esp32_server"
DB_PASS = "123456"
AGENT_ID = "1822c2babf1b44cca6b25d0bdebc796f"


def mysql_query(sql):
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", f"-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "--batch", "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    lines = [l for l in r.stdout.split("\n") if l.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    return [dict(zip(headers, l.split("\t"))) for l in lines[1:]]


def mysql_exec(sql):
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", f"-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "-e", sql]
    subprocess.run(cmd, capture_output=True, text=True, timeout=20)


def get_config(key):
    rows = mysql_query(f"SELECT config_value FROM rl_system_config WHERE config_key='{key}'")
    return rows[0]["config_value"] if rows else None


def get_portrait():
    rows = mysql_query(f"""SELECT profile_json FROM rl_companion_profile
        WHERE agent_id='{AGENT_ID}' ORDER BY updated_at DESC LIMIT 1""")
    return rows[0]["profile_json"] if rows else "{}"


def get_recent_mood(days=3):
    rows = mysql_query(f"""SELECT mood_date, dominant_emotion, summary
        FROM rl_mood_daily WHERE agent_id='{AGENT_ID}'
        ORDER BY mood_date DESC LIMIT {days}""")
    return rows


def get_reminder_stats():
    rows = mysql_query(f"""SELECT title, remind_time, type, status FROM rl_reminders
        WHERE agent_id='{AGENT_ID}' AND status IN ('active','pending')
        ORDER BY remind_time LIMIT 10""")
    return rows


def get_recent_events(days=3):
    rows = mysql_query(f"""SELECT event_type, summary, ts
        FROM rl_care_events WHERE agent_id='{AGENT_ID}'
        AND ts >= DATE_SUB(NOW(), INTERVAL {days} DAY)
        ORDER BY ts DESC LIMIT 20""")
    return rows


def generate_strategy():
    portrait = get_portrait()
    moods = get_recent_mood()
    reminders = get_reminder_stats()
    events = get_recent_events()

    now = datetime.now()
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]

    prompt = f"""你是一个老年陪伴AI系统的策略引擎。根据以下数据，生成一段简短的"今日陪伴策略"。

要求：
1. 必须是行为指令，不是信息描述。告诉AI"做什么"而不是"老人是什么样的人"
2. 200字以内，分条列出，每条一句话
3. 涵盖：语气/动作频率/重点关注/主动话题/风险防范
4. 绝对不能包含"画像""数据""分析""系统发现"等词
5. 用"铲屎官"称呼老人

今天是 {now.strftime('%Y-%m-%d')} {weekday}

【用户画像】
{portrait[:1500]}

【近3天情绪】
{json.dumps(moods, ensure_ascii=False, indent=2)[:500] if moods else '无记录'}

【活跃提醒】
{json.dumps(reminders, ensure_ascii=False, indent=2)[:500] if reminders else '无提醒'}

【近期事件】
{json.dumps(events, ensure_ascii=False, indent=2)[:800] if events else '无事件'}

请直接输出策略文本，不要解释。"""

    headers = {"Authorization": f"Bearer {ZHIPU_KEY}", "Content-Type": "application/json"}
    r = requests.post(f"{ZHIPU_BASE}/chat/completions", headers=headers, json={
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500,
    }, timeout=30)
    result = r.json()
    strategy = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return strategy, portrait[:500]


def main():
    if not ZHIPU_KEY:
        sys.exit("env ZHIPU_API_KEY required")

    if get_config("strategy_auto_generate") != "1":
        print("strategy_auto_generate is off, skip")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    existing = mysql_query(f"SELECT id FROM rl_daily_strategy WHERE agent_id='{AGENT_ID}' AND strategy_date='{today}'")
    if existing:
        print(f"Strategy for {today} already exists, skip")
        return

    print(f"Generating strategy for {today}...")
    strategy, source = generate_strategy()

    if not strategy:
        print("LLM returned empty strategy")
        return

    safe_strategy = strategy.replace("'", "\\'").replace('"', '\\"')
    safe_source = source.replace("'", "\\'").replace('"', '\\"')

    sql = f"""INSERT INTO rl_daily_strategy (agent_id, strategy_date, strategy_text, source_portrait)
        VALUES ('{AGENT_ID}', '{today}', '{safe_strategy}', '{safe_source}')
        ON DUPLICATE KEY UPDATE strategy_text='{safe_strategy}', source_portrait='{safe_source}'"""
    mysql_exec(sql)
    print(f"Strategy saved ({len(strategy)} chars)")
    print(strategy)


if __name__ == "__main__":
    main()
