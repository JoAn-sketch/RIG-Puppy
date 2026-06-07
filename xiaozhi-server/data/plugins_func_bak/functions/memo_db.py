"""备忘录 DB helper"""
import os
from typing import Optional, Dict, Any, List
import pymysql

DB_HOST = os.getenv("MSG_DB_HOST", "xiaozhi-esp32-server-db")
DB_PORT = int(os.getenv("MSG_DB_PORT", "3306"))
DB_USER = os.getenv("MSG_DB_USER", "root")
DB_PASS = os.getenv("MSG_DB_PASS", "123456")
DB_NAME = os.getenv("MSG_DB_NAME", "xiaozhi_esp32_server")

def _conn():
    return pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True)

def agent_id_by_mac(mac: str) -> Optional[str]:
    if not mac:
        return None
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT agent_id FROM ai_device WHERE LOWER(mac_address)=LOWER(%s) LIMIT 1", (mac,))
        row = cur.fetchone()
        return row["agent_id"] if row else None

def add_memo(agent_id: str, title: str, content: str = "") -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO rl_memo (agent_id, title, content) VALUES (%s,%s,%s)", (agent_id, title, content))
        return cur.lastrowid

def list_memo(agent_id: str) -> List[Dict[str, Any]]:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT * FROM rl_memo WHERE agent_id=%s ORDER BY created_at DESC", (agent_id,))
        return list(cur.fetchall())

def delete_memo(agent_id: str, memo_id: int) -> bool:
    with _conn() as c, c.cursor() as cur:
        cur.execute("DELETE FROM rl_memo WHERE agent_id=%s AND id=%s", (agent_id, memo_id))
        return cur.rowcount > 0
