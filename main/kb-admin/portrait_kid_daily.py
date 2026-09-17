#!/usr/bin/env python3
"""
portrait_kid_daily.py — 儿童画像每日聚合
读取 rl_kid_session_log → 聚合学习统计 → 调 LLM 生成人性化画像文本 → 存入 rl_kid_profile
cron: 30 23 * * * (每天 23:30,在成人画像 portrait_daily.py 之后跑)

用法: python3 /home/ubuntu/kb-admin/portrait_kid_daily.py [--device MAC]
"""
import os
import sys
import json
import subprocess
from datetime import datetime, date, timedelta
import requests

ZHIPU_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
DB_CONTAINER = "xiaozhi-esp32-server-db"
DB_NAME = "xiaozhi_esp32_server"
DB_PASS = "123456"


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


def get_active_devices():
    return mysql_query(
        "SELECT DISTINCT device_mac FROM rl_kid_session_log "
        "WHERE session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
    )


def get_session_stats(device_mac: str):
    """近 30 天各题型的正确率统计"""
    rows = mysql_query(
        f"SELECT content_type, COUNT(*) as total, SUM(is_correct) as correct "
        f"FROM rl_kid_session_log "
        f"WHERE device_mac='{device_mac}' AND session_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) "
        f"GROUP BY content_type"
    )
    return rows


def get_streak_history(device_mac: str):
    """计算历史最长连对"""
    rows = mysql_query(
        f"SELECT is_correct FROM rl_kid_session_log "
        f"WHERE device_mac='{device_mac}' ORDER BY created_at"
    )
    best = streak = 0
    for r in rows:
        if r['is_correct'] == '1':
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def get_active_days(device_mac: str):
    rows = mysql_query(
        f"SELECT COUNT(DISTINCT session_date) as days FROM rl_kid_session_log "
        f"WHERE device_mac='{device_mac}'"
    )
    return int(rows[0]['days']) if rows else 0


def get_existing_profile(device_mac: str):
    rows = mysql_query(
        f"SELECT profile_json FROM rl_kid_profile WHERE device_mac='{device_mac}'"
    )
    return json.loads(rows[0]['profile_json']) if rows and rows[0].get('profile_json') else {}


def call_llm(prompt: str) -> str:
    if not ZHIPU_KEY:
        return ""
    try:
        resp = requests.post(
            f"{ZHIPU_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {ZHIPU_KEY}"},
            json={
                "model": "glm-4-flash",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=30,
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"LLM 调用失败: {e}")
        return ""


def generate_kid_profile(device_mac: str):
    stats = get_session_stats(device_mac)
    if not stats:
        print(f"  {device_mac}: 无游戏记录,跳过")
        return

    total_q = sum(int(s['total']) for s in stats)
    total_c = sum(int(s['correct']) for s in stats)
    accuracy = round(total_c / total_q * 100, 1) if total_q else 0

    fav_type = max(stats, key=lambda s: int(s['total']))['content_type'] if stats else None
    weak_type = min(
        [s for s in stats if int(s['total']) >= 3],
        key=lambda s: int(s['correct']) / int(s['total']),
        default=None
    )
    weak_type = weak_type['content_type'] if weak_type else None

    best_streak = get_streak_history(device_mac)
    active_days = get_active_days(device_mac)
    old_profile = get_existing_profile(device_mac)

    type_names = {
        'riddle': '脑筋急转弯', 'math': '数学', 'pinyin': '拼音',
        'idiom': '成语', 'english': '英语', 'safety': '安全', 'whyq': '十万个为什么'
    }

    stats_text = "\n".join(
        f"  {type_names.get(s['content_type'], s['content_type'])}: "
        f"答了{s['total']}道,答对{s['correct']}道"
        for s in stats
    )

    prompt = f"""你是一只陪伴小朋友学习的 AI 机器狗,请根据以下学习数据,生成一段简洁的儿童成长画像(100字以内,白话文,不要出现"数据/画像/系统"等词)。

学习统计(近30天):
{stats_text}
总题数: {total_q}题,正确率: {accuracy}%
历史最长连对: {best_streak}题
活跃天数: {active_days}天
最爱题型: {type_names.get(fav_type, fav_type)}
{'薄弱题型: ' + type_names.get(weak_type, weak_type) if weak_type else '暂无明显薄弱项'}

历史画像(上次): {json.dumps(old_profile.get('summary', ''), ensure_ascii=False)}

请生成:画像摘要(一段话),以及一句今天可以针对这个小朋友说的鼓励话(不超过20字)。
格式:
摘要: xxx
鼓励: xxx"""

    llm_out = call_llm(prompt)
    summary = ""
    encourage = ""
    for line in llm_out.splitlines():
        if line.startswith("摘要:"):
            summary = line[3:].strip()
        elif line.startswith("鼓励:"):
            encourage = line[3:].strip()

    profile_json = json.dumps({
        "summary": summary,
        "encourage": encourage,
        "stats": {s['content_type']: {
            "total": int(s['total']), "correct": int(s['correct'])
        } for s in stats},
        "accuracy": accuracy,
        "best_streak": best_streak,
        "active_days": active_days,
        "fav_type": fav_type,
        "weak_type": weak_type,
        "updated_at": datetime.now().isoformat(),
    }, ensure_ascii=False)

    safe_json = profile_json.replace("'", "\\'").replace("\\", "\\\\")
    today = date.today().isoformat()
    mysql_exec(
        f"INSERT INTO rl_kid_profile "
        f"(device_mac, total_questions, total_correct, best_streak, fav_type, weak_type, "
        f"last_active_date, active_days, profile_json) "
        f"VALUES ('{device_mac}', {total_q}, {total_c}, {best_streak}, "
        f"'{fav_type or ''}', '{weak_type or ''}', '{today}', {active_days}, '{safe_json}') "
        f"ON DUPLICATE KEY UPDATE "
        f"total_questions={total_q}, total_correct={total_c}, best_streak={best_streak}, "
        f"fav_type='{fav_type or ''}', weak_type='{weak_type or ''}', "
        f"last_active_date='{today}', active_days={active_days}, profile_json='{safe_json}', "
        f"updated_at=NOW()"
    )
    print(f"  {device_mac}: ok — {total_q}题/{accuracy}% — {summary[:40]}")


def main():
    target_mac = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--device":
        target_mac = sys.argv[2]

    if target_mac:
        devices = [{"device_mac": target_mac}]
    else:
        devices = get_active_devices()

    print(f"[portrait_kid_daily] {datetime.now()} — {len(devices)} 台设备")
    for d in devices:
        try:
            generate_kid_profile(d["device_mac"])
        except Exception as e:
            print(f"  {d['device_mac']} 失败: {e}")

    print("done.")


if __name__ == "__main__":
    main()
