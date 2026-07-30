from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.connection import ConnectionHandler


class LiveConnectionRegistry:
    """Track current live runtime connections by device/client identity."""

    def __init__(self):
        self._device_connections: dict[str, tuple["ConnectionHandler", float]] = {}
        self._client_connections: dict[str, tuple["ConnectionHandler", float]] = {}
        self._lock = threading.Lock()

    def register(self, conn: "ConnectionHandler") -> None:
        now = time.time()
        device_id = self._normalize_device_id(getattr(conn, "device_id", ""))
        client_id = str(
            getattr(conn, "headers", {}).get("client-id", "") if getattr(conn, "headers", None) else ""
        ).strip()
        with self._lock:
            if device_id:
                self._device_connections[device_id] = (conn, now)
            if client_id:
                self._client_connections[client_id] = (conn, now)

    def unregister(self, conn: "ConnectionHandler") -> None:
        with self._lock:
            self._remove_if_same_locked(self._device_connections, getattr(conn, "device_id", None), conn)
            client_id = ""
            headers = getattr(conn, "headers", None) or {}
            if isinstance(headers, dict):
                client_id = str(headers.get("client-id", "") or "").strip()
            self._remove_if_same_locked(self._client_connections, client_id, conn)

    def get_by_device_id(self, device_id: str) -> Optional["ConnectionHandler"]:
        normalized = self._normalize_device_id(device_id)
        if not normalized:
            return None
        with self._lock:
            conn, seen_at = self._device_connections.get(normalized, (None, 0.0))
            if not self._is_alive(conn):
                self._device_connections.pop(normalized, None)
                return None
            self._device_connections[normalized] = (conn, max(seen_at, time.time()))
            return conn

    def cleanup_stale(self, ttl_seconds: int = 1800) -> None:
        cutoff = time.time() - ttl_seconds
        with self._lock:
            stale_device_keys = [
                key for key, (conn, seen_at) in self._device_connections.items()
                if seen_at < cutoff or not self._is_alive(conn)
            ]
            stale_client_keys = [
                key for key, (conn, seen_at) in self._client_connections.items()
                if seen_at < cutoff or not self._is_alive(conn)
            ]
            for key in stale_device_keys:
                self._device_connections.pop(key, None)
            for key in stale_client_keys:
                self._client_connections.pop(key, None)

    def snapshot(self) -> list[dict]:
        now = time.time()
        result = []
        with self._lock:
            stale_device_keys = []
            for key, (conn, seen_at) in self._device_connections.items():
                if not self._is_alive(conn):
                    stale_device_keys.append(key)
                    continue
                headers = getattr(conn, "headers", None) or {}
                if not isinstance(headers, dict):
                    headers = {}
                result.append(
                    {
                        "device_id": str(getattr(conn, "device_id", "") or ""),
                        "client_id": str(headers.get("client-id", "") or ""),
                        "client_ip": str(getattr(conn, "client_ip", "") or ""),
                        "connected_at": float(getattr(conn, "first_activity_time", 0.0) or 0.0) / 1000.0,
                        "last_activity_at": float(getattr(conn, "last_activity_time", 0.0) or 0.0) / 1000.0,
                        "last_seen_at": float(seen_at or 0.0),
                        "connection_alive": True,
                        "conn_from_mqtt_gateway": bool(getattr(conn, "conn_from_mqtt_gateway", False)),
                        "session_id": str(getattr(conn, "session_id", "") or ""),
                    }
                )
            for key in stale_device_keys:
                self._device_connections.pop(key, None)
        result.sort(key=lambda item: item.get("last_activity_at") or item.get("last_seen_at") or 0.0, reverse=True)
        for item in result:
            last_ts = item.get("last_activity_at") or item.get("last_seen_at") or 0.0
            item["idle_seconds"] = max(0, int(now - last_ts)) if last_ts else None
        return result

    def _remove_if_same_locked(self, mapping, key, conn: "ConnectionHandler") -> None:
        normalized = self._normalize_device_id(key)
        if not normalized:
            return
        current_conn, _ = mapping.get(normalized, (None, 0.0))
        if current_conn is conn:
            mapping.pop(normalized, None)

    def _normalize_device_id(self, device_id) -> str:
        return str(device_id or "").strip().lower()

    def _is_alive(self, conn: Optional["ConnectionHandler"]) -> bool:
        if conn is None:
            return False
        stop_event = getattr(conn, "stop_event", None)
        if stop_event is not None and stop_event.is_set():
            return False
        executor = getattr(conn, "executor", None)
        if executor is None:
            return False
        return True
