#!/usr/bin/env python3
"""
每晚 23:30 运行：事件收集 → 每日摘要 → 更新长期画像
"""
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta

import pymysql
import requests

DB_HOST = "172.18.0.3"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = "123456"
DB_NAME = "xiaozhi_esp32_server"
ZHIPU_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
MODEL = "glm-4-flash"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("portrait_daily")


def db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def llm(prompt, system="你是一个专业的老年陪伴数据分析助手。"):
    r = requests.post(
        f"{ZHIPU_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {ZHIPU_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def collect_events(conn, agent_id, target_date):
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    events = []

    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM rl_mood_daily WHERE agent_id=%s AND stat_date=%s",
            (agent_id, target_date)
        )
        mood = cur.fetchone()
        if mood:
            if mood.get("loneliness_hits", 0) >= 2:
                events.append({
                    "event_type": "mood_signal",
                    "event_time": end - timedelta(minutes=1),
                    "summary": f"今日孤独词命中{mood['loneliness_hits']}次，可能陪伴需求较高",
                    "risk_level": 1,
                    "detail": {"loneliness_hits": mood["loneliness_hits"],
                               "negative_hits": mood.get("negative_hits", 0),
                               "keywords": mood.get("matched_keywords")},
                })
            if mood.get("user_msg_count", 0) >= 5:
                events.append({
                    "event_type": "chat_companionship",
                    "event_time": mood.get("last_chat_at") or end,
                    "summary": f"今日主动对话{mood['user_msg_count']}次，互动活跃",
                    "risk_level": 0,
                    "detail": {"msg_count": mood["user_msg_count"],
                               "hours_active": mood.get("hours_active")},
                })

        cur.execute(
            "SELECT id, title, last_fired_at FROM rl_reminders "
            "WHERE agent_id=%s AND last_fired_at >= %s AND last_fired_at < %s",
            (agent_id, start, end)
        )
        for r in cur.fetchall():
            events.append({
                "event_type": "reminder_accepted",
                "event_time": r["last_fired_at"],
                "summary": f"提醒「{r['title']}」已触发",
                "risk_level": 0,
                "detail": {"reminder_id": r["id"], "title": r["title"]},
            })

        cur.execute(
            "SELECT template_key, rendered, created_at, status FROM rl_message_log "
            "WHERE agent_id=%s AND created_at >= %s AND created_at < %s",
            (agent_id, start, end)
        )
        for r in cur.fetchall():
            if r.get("template_key") == "fraud_alert" or "诈骗" in (r.get("rendered") or ""):
                events.append({
                    "event_type": "fraud_related",
                    "event_time": r["created_at"],
                    "summary": f"触发反诈提醒：{(r.get('rendered') or '')[:80]}",
                    "risk_level": 2,
                    "detail": {"template": r.get("template_key"), "status": r.get("status")},
                })

        health_kw = ["头晕", "头疼", "胸闷", "摔倒", "腿疼", "睡不好", "胃不舒服", "不舒服", "难受"]
        cur.execute(
            "SELECT content, created_at FROM ai_agent_chat_history "
            "WHERE agent_id=%s AND chat_type=1 AND created_at >= %s AND created_at < %s",
            (agent_id, start, end)
        )
        health_hits = []
        for r in cur.fetchall():
            content = r.get("content") or ""
            for kw in health_kw:
                if kw in content:
                    health_hits.append({"kw": kw, "at": str(r["created_at"]), "text": content[:100]})
                    break
        if health_hits:
            events.append({
                "event_type": "health_signal",
                "event_time": start,
                "summary": f"对话中出现健康相关词汇{len(health_hits)}次：{','.join(h['kw'] for h in health_hits[:3])}",
                "risk_level": 1,
                "detail": {"hits": health_hits[:5]},
            })

    return events


def save_events(conn, agent_id, events):
    with conn.cursor() as cur:
        for e in events:
            cur.execute(
                "INSERT INTO rl_care_events "
                "(agent_id, event_type, event_time, summary, risk_level, detail) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (agent_id, e["event_type"], e["event_time"],
                 e["summary"], e["risk_level"],
                 json.dumps(e.get("detail"), ensure_ascii=False) if e.get("detail") else None)
            )


DAILY_SUMMARY_PROMPT = """你是一个老年陪伴机器狗的照护数据分析助手。
下面是今天（{date}）的结构化事件日志，请生成一份每日照护摘要。

【今日事件日志】
{events_json}

【今日情绪统计】
{mood_json}

请严格按以下 JSON 格式输出，不要输出任何其他内容：
{{
  "overall_status": "normal或attention或alert",
  "medicine_status": {{"morning": "taken或missed或unknown", "noon": "taken或missed或unknown", "evening": "taken或missed或unknown", "note": "一句话说明"}},
  "reminder_status": {{"total": 0, "accepted": 0, "ignored": 0, "note": "一句话说明"}},
  "mood_companion": "今日情绪和陪伴需求的描述，2-3句",
  "fraud_risk": {{"count": 0, "max_level": 0, "note": "一句话说明，无风险则写无"}},
  "health_signals": "健康信号描述，无则写无",
  "interaction_prefs": "今日观察到的互动偏好，无新发现则写无",
  "tomorrow_strategy": "明天建议的陪伴策略，2-3条具体可执行建议",
  "family_note": "家属需要知道的事项，无则写无"
}}

注意：只写可观察事实和趋势，不做医学诊断，不写评价性结论，策略要具体可执行。"""


def generate_daily_summary(conn, agent_id, target_date, events):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM rl_mood_daily WHERE agent_id=%s AND stat_date=%s",
            (agent_id, target_date)
        )
        mood = cur.fetchone() or {}

    events_text = json.dumps(
        [{"type": e["event_type"], "time": str(e["event_time"]),
          "summary": e["summary"], "risk": e["risk_level"]} for e in events],
        ensure_ascii=False, indent=2
    )
    mood_text = json.dumps(
        {k: v for k, v in mood.items() if k not in ("id", "agent_id", "stat_date")},
        ensure_ascii=False, default=str
    )

    prompt = DAILY_SUMMARY_PROMPT.format(
        date=str(target_date), events_json=events_text or "[]", mood_json=mood_text or "{}"
    )

    raw = ""
    try:
        raw = llm(prompt)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        summary = json.loads(raw.strip())
    except Exception as e:
        log.error(f"摘要解析失败: {e}, raw={raw[:200]}")
        summary = {
            "overall_status": "normal",
            "medicine_status": {"morning": "unknown", "noon": "unknown", "evening": "unknown", "note": "数据不足"},
            "reminder_status": {"total": 0, "accepted": 0, "ignored": 0, "note": ""},
            "mood_companion": "今日数据不足，无法生成摘要",
            "fraud_risk": {"count": 0, "max_level": 0, "note": "无"},
            "health_signals": "无", "interaction_prefs": "无",
            "tomorrow_strategy": "保持常规陪伴策略", "family_note": "无",
        }

    def _str(v):
        """LLM 有时返回列表而非字符串，统一转成字符串"""
        if isinstance(v, list):
            return "\n".join(str(i) for i in v)
        if isinstance(v, str):
            return v
        return str(v) if v is not None else ""

    s_overall = _str(summary.get("overall_status", "normal"))
    s_med = json.dumps(summary.get("medicine_status"), ensure_ascii=False)
    s_rem = json.dumps(summary.get("reminder_status"), ensure_ascii=False)
    s_mood = _str(summary.get("mood_companion", ""))
    s_fraud = json.dumps(summary.get("fraud_risk"), ensure_ascii=False)
    s_health = _str(summary.get("health_signals", ""))
    s_prefs = _str(summary.get("interaction_prefs", ""))
    s_strat = _str(summary.get("tomorrow_strategy", ""))
    s_fam = _str(summary.get("family_note", ""))
    s_cnt = len(events)
    s_now = datetime.now()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM rl_daily_summary WHERE agent_id=%s AND summary_date=%s",
            (agent_id, target_date)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE rl_daily_summary SET overall_status=%s, medicine_status=%s, "
                "reminder_status=%s, mood_companion=%s, fraud_risk=%s, health_signals=%s, "
                "interaction_prefs=%s, tomorrow_strategy=%s, family_note=%s, "
                "raw_event_count=%s, llm_model=%s, generated_at=%s "
                "WHERE agent_id=%s AND summary_date=%s",
                (s_overall, s_med, s_rem, s_mood, s_fraud, s_health, s_prefs,
                 s_strat, s_fam, s_cnt, MODEL, s_now, agent_id, target_date)
            )
        else:
            cur.execute(
                "INSERT INTO rl_daily_summary "
                "(agent_id, summary_date, overall_status, medicine_status, reminder_status, "
                "mood_companion, fraud_risk, health_signals, interaction_prefs, "
                "tomorrow_strategy, family_note, raw_event_count, llm_model, generated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (agent_id, target_date, s_overall, s_med, s_rem, s_mood, s_fraud,
                 s_health, s_prefs, s_strat, s_fam, s_cnt, MODEL, s_now)
            )
    return summary


UPDATE_PROFILE_PROMPT = """你是一个老年陪伴机器狗的长期画像维护助手。

【当前长期陪伴画像】（已有 {data_days} 天数据）
{old_profile}

【最近3天每日摘要】
{recent_summaries}

【今日摘要】
{today_summary}

请更新长期陪伴画像。规则：
1. 只有连续多天出现的模式才能写入长期画像，单日偶发只写近期趋势
2. 不确定内容标记为"待观察"
3. 健康相关只写观察和建议，不做诊断
4. 每个字段用"事实+推断+策略"三层结构，例如：
   "近7天有4次晚间主动要求聊天（事实）→ 晚间陪伴需求可能较高（推断）→ 晚饭后主动说一句关心的话（策略）"

请严格按以下 JSON 格式输出：
{{
  "schedule_profile": "作息画像",
  "medicine_profile": "用药画像",
  "companion_prefs": "陪伴偏好画像",
  "mood_profile": "情绪陪伴画像",
  "fraud_profile": "反诈风险画像",
  "health_profile": "健康安全关注画像",
  "recent_trends": "近7天趋势摘要，2-3条最值得关注的变化",
  "tomorrow_strategy": "当前最有效的陪伴策略，3-5条具体可执行"
}}"""


def update_profile(conn, agent_id, today_summary):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM rl_companion_profile WHERE agent_id=%s", (agent_id,))
        old = cur.fetchone()
        cur.execute(
            "SELECT summary_date, overall_status, mood_companion, tomorrow_strategy, "
            "medicine_status, fraud_risk, health_signals FROM rl_daily_summary "
            "WHERE agent_id=%s ORDER BY summary_date DESC LIMIT 3",
            (agent_id,)
        )
        recent = cur.fetchall()

    data_days = (old or {}).get("data_days", 0) + 1

    def _str(v):
        if isinstance(v, list):
            return "\n".join(str(i) for i in v)
        return str(v) if v is not None else ""

    if data_days < 3:
        log.info(f"agent {agent_id} 数据仅 {data_days} 天，跳过长期画像，只记录趋势")
        t_trends = _str(today_summary.get("mood_companion", ""))
        t_strat = _str(today_summary.get("tomorrow_strategy", ""))
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rl_companion_profile "
                "(agent_id, recent_trends, tomorrow_strategy, data_days, last_updated) "
                "VALUES (%s,%s,%s,%s,CURDATE()) "
                "ON DUPLICATE KEY UPDATE recent_trends=%s, "
                "tomorrow_strategy=%s, data_days=%s, last_updated=CURDATE()",
                (agent_id, t_trends, t_strat, data_days,
                 t_trends, t_strat, data_days)
            )
        return

    old_profile_text = json.dumps(
        {k: v for k, v in (old or {}).items()
         if k not in ("id", "agent_id", "created_at", "updated_at", "profile_version")},
        ensure_ascii=False, default=str
    ) if old else "暂无历史画像，这是第一次生成"

    recent_text = json.dumps(
        [{k: str(v) if hasattr(v, "isoformat") else v for k, v in r.items()} for r in recent],
        ensure_ascii=False, default=str
    )

    raw = ""
    try:
        raw = llm(UPDATE_PROFILE_PROMPT.format(
            data_days=data_days,
            old_profile=old_profile_text,
            recent_summaries=recent_text,
            today_summary=json.dumps(today_summary, ensure_ascii=False),
        ))
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        new_profile = json.loads(raw.strip())
    except Exception as e:
        log.error(f"画像更新解析失败: {e}, raw={raw[:200]}")
        return

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM rl_companion_profile WHERE agent_id=%s", (agent_id,)
        )
        exists = cur.fetchone()
        p = new_profile
        if exists:
            cur.execute(
                "UPDATE rl_companion_profile SET "
                "schedule_profile=%s, medicine_profile=%s, companion_prefs=%s, mood_profile=%s, "
                "fraud_profile=%s, health_profile=%s, recent_trends=%s, tomorrow_strategy=%s, "
                "data_days=%s, last_updated=CURDATE(), profile_version=profile_version+1 "
                "WHERE agent_id=%s",
                (p.get("schedule_profile",""), p.get("medicine_profile",""),
                 p.get("companion_prefs",""), p.get("mood_profile",""),
                 p.get("fraud_profile",""), p.get("health_profile",""),
                 p.get("recent_trends",""), p.get("tomorrow_strategy",""),
                 data_days, agent_id)
            )
        else:
            cur.execute(
                "INSERT INTO rl_companion_profile "
                "(agent_id, schedule_profile, medicine_profile, companion_prefs, mood_profile, "
                "fraud_profile, health_profile, recent_trends, tomorrow_strategy, data_days, last_updated) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURDATE())",
                (agent_id,
                 p.get("schedule_profile",""), p.get("medicine_profile",""),
                 p.get("companion_prefs",""), p.get("mood_profile",""),
                 p.get("fraud_profile",""), p.get("health_profile",""),
                 p.get("recent_trends",""), p.get("tomorrow_strategy",""),
                 data_days)
            )
    log.info(f"agent {agent_id} 画像已更新，累计 {data_days} 天")


def run(target_date=None):
    if target_date is None:
        target_date = date.today()

    conn = db()
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT agent_id FROM ai_agent_chat_history")
        agent_ids = [r["agent_id"] for r in cur.fetchall()]

    log.info(f"共 {len(agent_ids)} 个 agent，日期 {target_date}")
    for agent_id in agent_ids:
        log.info(f"处理 agent: {agent_id}")
        try:
            events = collect_events(conn, agent_id, target_date)
            save_events(conn, agent_id, events)
            log.info(f"  收集事件 {len(events)} 条")
            summary = generate_daily_summary(conn, agent_id, target_date, events)
            log.info(f"  每日摘要完成，状态: {summary.get('overall_status')}")
            update_profile(conn, agent_id, summary)
        except Exception as e:
            log.error(f"  agent {agent_id} 处理失败: {e}", exc_info=True)

    conn.close()
    log.info("portrait_daily 完成")


if __name__ == "__main__":
    if not ZHIPU_KEY:
        sys.exit("env ZHIPU_API_KEY 未设")
    target = None
    if len(sys.argv) > 1:
        target = date.fromisoformat(sys.argv[1])
    run(target)
