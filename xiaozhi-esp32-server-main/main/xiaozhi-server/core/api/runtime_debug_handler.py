import json
from aiohttp import web

from core.api.base_handler import BaseHandler
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
        text = str(payload.get("text") or "").strip()
        timeout_seconds = float(payload.get("timeout_seconds") or 90)
        if not session_key:
            return self._json_response({"error": "session_key required"}, status=400)
        if not text:
            return self._json_response({"error": "text required"}, status=400)

        try:
            session = await self.session_manager.get_session(session_key)
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
        if not session_key:
            return self._json_response({"error": "session_key required"}, status=400)

        try:
            await self.session_manager.reset_session(session_key)
            return self._json_response({"ok": True})
        except Exception as e:
            return self._json_response({"error": str(e)}, status=500)
