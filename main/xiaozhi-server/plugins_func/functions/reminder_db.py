"""提醒计划: DB 助手。复用 [[server-messaging-center]] 的连接方式。"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import pymysql

DB_HOST = os.getenv("MSG_DB_HOST", "xiaozhi-esp32-server-db")
DB_PORT = int(os.getenv("MSG_DB_PORT", "3306"))
DB_USER = os.getenv("MSG_DB_USER", "root")
DB_PASS = os.getenv("MSG_DB_PASS", "123456")
DB_NAME = os.getenv("MSG_DB_NAME", "xiaozhi_esp32_server")


def _conn():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


def agent_id_by_mac(mac: str) -> Optional[str]:
    if not mac:
        return None
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT agent_id FROM ai_device WHERE LOWER(mac_address)=LOWER(%s) LIMIT 1",
            (mac,),
        )
        row = cur.fetchone()
        return row["agent_id"] if row else None


def add_reminder(agent_id: str, type_: str, title: str, content: str,
                 fire_time: str, fire_date: Optional[str] = None) -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO rl_reminders "
            "(agent_id, type, title, content, fire_time, fire_date, enabled) "
            "VALUES (%s,%s,%s,%s,%s,%s,1)",
            (agent_id, type_, title, content, fire_time, fire_date),
        )
        return cur.lastrowid


def list_reminders(agent_id: str, only_enabled: bool = True) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM rl_reminders WHERE agent_id=%s"
    if only_enabled:
        sql += " AND enabled=1"
    sql += " ORDER BY type, fire_time"
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (agent_id,))
        return list(cur.fetchall())


def delete_reminder(agent_id: str, rid: int) -> bool:
    with _conn() as c, c.cursor() as cur:
        cur.execute("DELETE FROM rl_reminders WHERE agent_id=%s AND id=%s", (agent_id, rid))
        return cur.rowcount > 0


def mark_fired(rid: int):
    with _conn() as c, c.cursor() as cur:
        cur.execute("UPDATE rl_reminders SET last_fired_at=NOW() WHERE id=%s", (rid,))


def pending(agent_id: str, now: Optional[datetime] = None,
            grace_minutes: int = 720) -> List[Dict[str, Any]]:
    """返回该被播报的提醒。

    daily 类型:今天 fire_time 已到 + 当天还没播过。
    once 类型:fire_date <= 今天 + 还没播过(过期未播也要补播)。
    grace_minutes: daily 提醒错过多久就不再补播,默认 12 小时(避免半夜跳出来吓人)。
    """
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    hhmm_now = now.strftime("%H:%M")

    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT * FROM rl_reminders WHERE agent_id=%s AND enabled=1",
            (agent_id,),
        )
        rows = list(cur.fetchall())

    out = []
    for r in rows:
        last = r.get("last_fired_at")
        last_str = last.strftime("%Y-%m-%d") if last else ""

        if r["type"] == "daily":
            if r["fire_time"] > hhmm_now:
                continue
            if last_str == today:
                continue
            fire_dt = datetime.strptime(f"{today} {r['fire_time']}", "%Y-%m-%d %H:%M")
            if (now - fire_dt).total_seconds() > grace_minutes * 60:
                continue
            out.append(r)
        elif r["type"] == "once":
            if not r.get("fire_date"):
                continue
            if r["fire_date"] > today:
                continue
            if r["fire_date"] == today and r["fire_time"] > hhmm_now:
                continue
            if last:
                continue
            out.append(r)
    out.sort(key=lambda x: (x.get("fire_date") or "9999-99-99", x["fire_time"]))
    return out
