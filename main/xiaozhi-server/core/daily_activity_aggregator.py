from __future__ import annotations

import json
import os
from datetime import datetime, time as dt_time
from typing import Any, Dict, Optional

import pymysql


DB_HOST = os.getenv("MYSQL_HOST", "xiaozhi-esp32-server-db")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASS = os.getenv("MYSQL_PASSWORD", "123456")
DB_NAME = os.getenv("MYSQL_DATABASE", "xiaozhi_esp32_server")
DAILY_SUMMARY_UPDATE_HOUR = int(os.getenv("DAILY_ACTIVITY_SUMMARY_UPDATE_HOUR", "20"))

SUPPORTED_ACTIVITIES = {
    "chat",
    "learning",
    "story",
    "game",
    "creative",
    "bedtime",
    "emotional_support",
    "music",
    "other",
}

SCENE_TO_ACTIVITY = {
    "curiosity": "learning",
    "learning_support": "learning",
    "play_interaction": "game",
    "emotion_support": "emotional_support",
    "relationship_building": "chat",
    "system_repair": "other",
    "safety_risk": "emotional_support",
}

SUBSCENE_TO_ACTIVITY = {
    "story_game": "story",
    "language_game": "game",
    "role_play": "game",
    "movement_game": "game",
    "sadness": "emotional_support",
    "fear": "emotional_support",
    "anger": "emotional_support",
    "shame": "emotional_support",
    "school_stress": "emotional_support",
}


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
            CREATE TABLE IF NOT EXISTS child_daily_activity_summary (
                id BIGINT NOT NULL AUTO_INCREMENT,
                device_id VARCHAR(128) NOT NULL,
                summary_date DATE NOT NULL,
                total_duration INT NOT NULL DEFAULT 0,
                total_duration_seconds INT NOT NULL DEFAULT 0,
                session_count INT NOT NULL DEFAULT 0,
                activity_distribution_json TEXT NOT NULL,
                scene_distribution_json TEXT NOT NULL,
                primary_activity VARCHAR(64) NOT NULL DEFAULT 'other',
                primary_scene VARCHAR(64) NOT NULL DEFAULT 'relationship_building',
                active_periods_json TEXT NOT NULL,
                highlight_metadata_json TEXT NOT NULL,
                session_state_json MEDIUMTEXT NOT NULL,
                finalized TINYINT NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uk_child_daily_activity_device_date (device_id, summary_date),
                KEY idx_child_daily_activity_date (summary_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )


def _json_loads(value: Any, default: Any):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(str(value))
        return parsed if parsed is not None else default
    except Exception:
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _safe_key(value: Any, default: str = "other") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default
    normalized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text).strip("_")
    return normalized or default


def classify_activity(scene_name: str, subscene: str = "", protocol_mode: str = "") -> str:
    subscene_key = _safe_key(subscene, "")
    if subscene_key in SUBSCENE_TO_ACTIVITY:
        return SUBSCENE_TO_ACTIVITY[subscene_key]
    scene_key = _safe_key(scene_name, "")
    activity = SCENE_TO_ACTIVITY.get(scene_key, "other")
    mode = _safe_key(protocol_mode, "")
    if "story" in mode:
        activity = "story"
    elif "game" in mode or "play" in mode:
        activity = "game"
    return activity if activity in SUPPORTED_ACTIVITIES else "other"


def _period_for(now: datetime) -> str:
    current = now.time()
    if dt_time(5, 0) <= current < dt_time(12, 0):
        return "morning"
    if dt_time(12, 0) <= current < dt_time(18, 0):
        return "afternoon"
    return "evening"


def _is_daily_summary_update_time(now: datetime) -> bool:
    return now.hour >= DAILY_SUMMARY_UPDATE_HOUR


def _max_key(distribution: Dict[str, int], fallback: str) -> str:
    if not distribution:
        return fallback
    return max(distribution.items(), key=lambda item: (int(item[1] or 0), item[0]))[0]


def _build_highlight_metadata(
    primary_activity: str,
    primary_scene: str,
) -> Dict[str, Any]:
    metadata = {
        "primary_activity": primary_activity,
        "primary_scene": primary_scene,
        "interaction_style": "exploratory" if primary_activity == "learning" else "companionship",
    }
    if primary_activity == "emotional_support":
        metadata["interaction_style"] = "supportive"
    elif primary_activity == "bedtime":
        metadata["interaction_style"] = "calming"
    elif primary_activity in {"game", "story", "creative", "music"}:
        metadata["interaction_style"] = "playful"
    return metadata


def record_interaction_event(
    *,
    device_id: str,
    session_id: str,
    scene_name: str,
    subscene: str = "",
    protocol_mode: str = "",
    emotion_state: str = "neutral",
    occurred_at: Optional[datetime] = None,
) -> None:
    normalized_device_id = str(device_id or "").strip().lower()
    normalized_session_id = str(session_id or "").strip()
    if not normalized_device_id or not normalized_session_id:
        return

    now = occurred_at or datetime.now()
    summary_date = now.date()
    scene_key = _safe_key(scene_name, "relationship_building")
    activity_key = classify_activity(scene_key, subscene, protocol_mode)
    active_period = _period_for(now)
    finalized = 1 if _is_daily_summary_update_time(now) else 0

    ensure_table()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE child_daily_activity_summary
            SET finalized=1
            WHERE device_id=%s AND summary_date < %s AND finalized=0
            """,
            (normalized_device_id, summary_date),
        )
        cur.execute(
            """
            SELECT * FROM child_daily_activity_summary
            WHERE device_id=%s AND summary_date=%s
            LIMIT 1
            """,
            (normalized_device_id, summary_date),
        )
        row = cur.fetchone()

        if row:
            activity_distribution = _json_loads(row["activity_distribution_json"], {})
            scene_distribution = _json_loads(row["scene_distribution_json"], {})
            active_periods = _json_loads(row["active_periods_json"], {
                "morning": False,
                "afternoon": False,
                "evening": False,
            })
            session_state = _json_loads(row["session_state_json"], {"sessions": {}})
            total_seconds = int(row.get("total_duration_seconds") or 0)
        else:
            activity_distribution = {}
            scene_distribution = {}
            active_periods = {"morning": False, "afternoon": False, "evening": False}
            session_state = {"sessions": {}}
            total_seconds = 0

        sessions = session_state.setdefault("sessions", {})
        session_meta = sessions.get(normalized_session_id) or {}
        is_new_session = normalized_session_id not in sessions
        previous_seen_at = session_meta.get("last_seen_at")
        if previous_seen_at:
            try:
                previous_dt = datetime.fromisoformat(previous_seen_at)
                delta_seconds = max(0, int((now - previous_dt).total_seconds()))
                total_seconds += min(delta_seconds, 600)
            except Exception:
                pass

        session_meta.update({
            "first_seen_at": session_meta.get("first_seen_at") or now.isoformat(timespec="seconds"),
            "last_seen_at": now.isoformat(timespec="seconds"),
            "last_scene": scene_key,
            "last_activity": activity_key,
        })
        sessions[normalized_session_id] = session_meta

        activity_distribution[activity_key] = int(activity_distribution.get(activity_key) or 0) + 1
        scene_distribution[scene_key] = int(scene_distribution.get(scene_key) or 0) + 1
        active_periods[active_period] = True

        primary_activity = _max_key(activity_distribution, activity_key)
        primary_scene = _max_key(scene_distribution, scene_key)
        highlight_metadata = _build_highlight_metadata(
            primary_activity,
            primary_scene,
        )
        session_count = len(sessions)
        total_minutes = int(round(total_seconds / 60))

        if row:
            cur.execute(
                """
                UPDATE child_daily_activity_summary
                SET total_duration=%s,
                    total_duration_seconds=%s,
                    session_count=%s,
                    activity_distribution_json=%s,
                    scene_distribution_json=%s,
                    primary_activity=%s,
                    primary_scene=%s,
                    active_periods_json=%s,
                    highlight_metadata_json=%s,
                    session_state_json=%s,
                    finalized=%s
                WHERE id=%s
                """,
                (
                    total_minutes,
                    total_seconds,
                    session_count,
                    _json_dumps(activity_distribution),
                    _json_dumps(scene_distribution),
                    primary_activity,
                    primary_scene,
                    _json_dumps(active_periods),
                    _json_dumps(highlight_metadata),
                    _json_dumps(session_state),
                    finalized,
                    row["id"],
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO child_daily_activity_summary (
                    device_id, summary_date, total_duration, total_duration_seconds,
                    session_count, activity_distribution_json, scene_distribution_json,
                    primary_activity, primary_scene, active_periods_json,
                    highlight_metadata_json, session_state_json, finalized
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    normalized_device_id,
                    summary_date,
                    total_minutes,
                    total_seconds,
                    session_count if is_new_session else len(sessions),
                    _json_dumps(activity_distribution),
                    _json_dumps(scene_distribution),
                    primary_activity,
                    primary_scene,
                    _json_dumps(active_periods),
                    _json_dumps(highlight_metadata),
                    _json_dumps(session_state),
                    finalized,
                ),
            )
