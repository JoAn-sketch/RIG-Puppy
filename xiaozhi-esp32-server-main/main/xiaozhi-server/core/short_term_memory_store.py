from __future__ import annotations

import json
import os
from typing import Optional

import pymysql

from core.short_term_memory import ShortTermMemoryManager


DB_HOST = os.getenv("MYSQL_HOST", "xiaozhi-esp32-server-db")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASS = os.getenv("MYSQL_PASSWORD", "123456")
DB_NAME = os.getenv("MYSQL_DATABASE", "xiaozhi_esp32_server")


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


def ensure_table() -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_short_term_memory (
                device_id VARCHAR(128) NOT NULL,
                memory_json LONGTEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (device_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )


def load_memory(device_id: str) -> Optional[ShortTermMemoryManager]:
    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id:
        return None
    ensure_table()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT memory_json FROM ai_short_term_memory WHERE device_id=%s LIMIT 1",
            (normalized_device_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row["memory_json"] or "{}")
        return ShortTermMemoryManager.from_dict(payload)
    except Exception:
        return None


def save_memory(device_id: str, memory: ShortTermMemoryManager) -> None:
    normalized_device_id = str(device_id or "").strip()
    if not normalized_device_id or memory is None:
        return
    ensure_table()
    payload = json.dumps(memory.to_dict(), ensure_ascii=False)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai_short_term_memory (device_id, memory_json)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE memory_json=VALUES(memory_json)
            """,
            (normalized_device_id, payload),
        )
