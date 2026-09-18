import json
import asyncio
from aiohttp import web

from core.api.base_handler import BaseHandler
from core.providers.tools.device_mcp import call_mcp_tool
from core.runtime_debug_text import (
    RUNTIME_DEBUG_AUTH_SECRET,
    RuntimeDebugTextSessionManager,
)


class RuntimeDebugHandler(BaseHandler):
    def __init__(self, config: dict, server):
        super().__init__(config)
        self.server = server
        self.session_manager = RuntimeDebugTextSessionManager(config, server)

    def _authorized(self, request) -> bool:
        provided = (
            request.headers.get("x-debug-token")
            or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        )
        return bool(provided) and provided == RUNTIME_DEBUG_AUTH_SECRET

    def _json_response(self, body: dict, status: int = 200):
        response = web.json_response(body, status=status)
        self._add_cors_headers(response)
        return response

    async def handle_send(self, request):
        if not self._authorized(request):
            return self._json_response({"error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return self._json_response({"error": "invalid json"}, status=400)

        session_key = str(payload.get("session_key") or "").strip()
        device_id = str(payload.get("device_id") or "").strip()
        text = str(payload.get("text") or "").strip()
        timeout_seconds = float(payload.get("timeout_seconds") or 90)
        if not session_key:
            return self._json_response({"error": "session_key required"}, status=400)
        if not text:
            return self._json_response({"error": "text required"}, status=400)

        try:
            session = await self.session_manager.get_session(session_key, device_id=device_id)
            result = await session.send_turn(text, timeout_seconds=timeout_seconds)
            return self._json_response({"ok": True, **result})
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def handle_reset(self, request):
        if not self._authorized(request):
            return self._json_response({"error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except json.JSONDecodeError:
            payload = {}

        session_key = str(payload.get("session_key") or "").strip()
        device_id = str(payload.get("device_id") or "").strip()
        if not session_key:
            return self._json_response({"error": "session_key required"}, status=400)

        try:
            await self.session_manager.reset_session(session_key, device_id=device_id)
            return self._json_response({"ok": True})
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def handle_live_devices(self, request):
        if not self._authorized(request):
            return self._json_response({"error": "unauthorized"}, status=401)
        registry = getattr(self.server, "live_connection_registry", None) if self.server is not None else None
        if registry is None:
            return self._json_response({"ok": True, "devices": [], "count": 0})
        try:
            devices = registry.snapshot()
            return self._json_response({"ok": True, "count": len(devices), "devices": devices})
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)

    async def handle_device_status(self, request):
        if not self._authorized(request):
            return self._json_response({"error": "unauthorized"}, status=401)

        payload = {}
        if request.method == "POST":
            try:
                payload = await request.json()
            except json.JSONDecodeError:
                payload = {}

        device_id = str(
            payload.get("device_id")
            or request.query.get("device_id")
            or ""
        ).strip()
        timeout_seconds = float(
            payload.get("timeout_seconds")
            or request.query.get("timeout_seconds")
            or 5
        )
        if not device_id:
            return self._json_response({"error": "device_id required"}, status=400)

        registry = getattr(self.server, "live_connection_registry", None) if self.server is not None else None
        if registry is None:
            return self._json_response({
                "ok": False,
                "online": False,
                "message": "live registry unavailable",
            }, status=503)

        conn = registry.get_by_device_id(device_id)
        if conn is None:
            return self._json_response({
                "ok": True,
                "online": False,
                "message": "device not currently online",
            })

        mcp_client = getattr(conn, "mcp_client", None)
        if mcp_client is None:
            return self._json_response({
                "ok": True,
                "online": True,
                "status": {},
                "message": "device mcp client unavailable",
            })

        try:
            raw_status = await call_mcp_tool(
                conn,
                mcp_client,
                "self_get_device_status",
                {},
                timeout=int(max(1, min(timeout_seconds, 15))),
            )
            status = raw_status
            if isinstance(raw_status, str):
                try:
                    status = json.loads(raw_status)
                except json.JSONDecodeError:
                    status = {"raw": raw_status}
            return self._json_response({
                "ok": True,
                "online": True,
                "status": status if isinstance(status, dict) else {"raw": status},
            })
        except Exception as e:
            return self._json_response({
                "ok": False,
                "online": True,
                "error": str(e),
            }, status=500)

    async def handle_device_factory_reset(self, request):
        if not self._authorized(request):
            return self._json_response({"error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except json.JSONDecodeError:
            payload = {}

        device_id = str(payload.get("device_id") or "").strip()
        if not device_id:
            return self._json_response({"error": "device_id required"}, status=400)

        registry = getattr(self.server, "live_connection_registry", None) if self.server is not None else None
        if registry is None:
            return self._json_response({
                "ok": False,
                "pushed": False,
                "acknowledged": False,
                "message": "live registry unavailable",
            }, status=503)

        conn = registry.get_by_device_id(device_id)
        if conn is None:
            return self._json_response({
                "ok": True,
                "pushed": False,
                "acknowledged": False,
                "message": "device not currently online",
            })

        try:
            payload = {
                "type": "system",
                "command": "factory_reset",
                "device_id": device_id,
                "stage": "prepare_reset",
                "message": "factory reset requested by backend",
            }
            await conn.websocket.send(json.dumps(payload, ensure_ascii=False))
            await asyncio.sleep(0.5)
            await conn.close()
            return self._json_response({
                "ok": True,
                "pushed": True,
                "acknowledged": False,
                "message": "factory reset command sent and session closed; device ack is not implemented",
            })
        except Exception as e:
            return self._json_response({
                "ok": False,
                "pushed": False,
                "acknowledged": False,
                "error": str(e),
            }, status=500)

    async def handle_first_adoption_greeting(self, request):
        if not self._authorized(request):
            return self._json_response({"error": "unauthorized"}, status=401)

        try:
            payload = await request.json()
        except json.JSONDecodeError:
            payload = {}

        device_id = str(payload.get("device_id") or "").strip()
        text = str(payload.get("text") or "").strip()
        user_name = str(payload.get("user_name") or "").strip()
        robot_name = str(payload.get("robot_name") or "").strip()
        if not device_id:
            return self._json_response({"error": "device_id required"}, status=400)
        if not text or not user_name or not robot_name:
            return self._json_response({
                "ok": True,
                "pushed": False,
                "message": "text/user_name/robot_name incomplete; greeting skipped",
            })

        registry = getattr(self.server, "live_connection_registry", None) if self.server is not None else None
        if registry is None:
            return self._json_response({
                "ok": False,
                "pushed": False,
                "message": "live registry unavailable",
            }, status=503)

        conn = registry.get_by_device_id(device_id)
        if conn is None:
            return self._json_response({
                "ok": True,
                "pushed": False,
                "message": "device not currently online",
            })

        try:
            command = {
                "type": "system",
                "command": "first_adoption_greeting",
                "device_id": device_id,
                "text": text,
                "user_name": user_name,
                "robot_name": robot_name,
            }
            await conn.websocket.send(json.dumps(command, ensure_ascii=False))
            return self._json_response({
                "ok": True,
                "pushed": True,
                "message": "first adoption greeting command sent",
            })
        except Exception as e:
            return self._json_response({
                "ok": False,
                "pushed": False,
                "error": str(e),
            }, status=500)
