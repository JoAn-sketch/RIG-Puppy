"""消息中心：联系人/模板/日志的 DB 助手。

直接复用 xiaozhi-esp32-server-db 容器里的 MySQL 实例。
"""

import os
import json
from typing import Optional, Dict, Any, List
import pymysql

DB_HOST = os.getenv("MSG_DB_HOST", "xiaozhi-esp32-server-db")
DB_PORT = int(os.getenv("MSG_DB_PORT", "3306"))
DB_USER = os.getenv("MSG_DB_USER", "root")
DB_PASS = os.getenv("MSG_DB_PASS", "123456")
DB_NAME = os.getenv("MSG_DB_NAME", "xiaozhi_esp32_server")


def _conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def find_contact(agent_id: str, nickname: str) -> Optional[Dict[str, Any]]:
    nickname = (nickname or "").strip()
    if not nickname:
        return None
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM rl_contacts WHERE agent_id=%s AND enabled=1 "
            "AND (nickname=%s OR relation=%s) ORDER BY id LIMIT 1",
            (agent_id, nickname, nickname),
        )
        return cur.fetchone()


def agent_id_by_mac(mac: str) -> Optional[str]:
    if not mac:
        return None
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT agent_id FROM ai_device WHERE LOWER(mac_address)=LOWER(%s) LIMIT 1",
            (mac,),
        )
        row = cur.fetchone()
        return row["agent_id"] if row else None


def list_contacts(agent_id: str) -> List[Dict[str, Any]]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT nickname, relation, channel_pref FROM rl_contacts "
            "WHERE agent_id=%s AND enabled=1 ORDER BY id",
            (agent_id,),
        )
        return list(cur.fetchall())


def find_template(template_key: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM rl_message_templates WHERE template_key=%s AND enabled=1",
            (template_key,),
        )
        return cur.fetchone()


def log_send(
    agent_id: str,
    contact_id: Optional[int],
    nickname: Optional[str],
    channel: str,
    template_key: Optional[str],
    rendered: str,
    status: str,
    err_msg: Optional[str] = None,
):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO rl_message_log "
            "(agent_id, contact_id, nickname, channel, template_key, rendered, status, err_msg) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (agent_id, contact_id, nickname, channel, template_key, rendered, status, err_msg),
        )


def render(content: str, variables: Dict[str, str]) -> str:
    out = content
    for k, v in (variables or {}).items():
        out = out.replace("${" + k + "}", str(v))
    return out
