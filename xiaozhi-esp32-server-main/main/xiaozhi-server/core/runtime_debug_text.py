import asyncio
import copy
import json
import os
import queue
import threading
import time
from typing import Any, Dict, Optional

from config.logger import setup_logging
from config.config_loader import get_private_config_from_api
from core.connection import ConnectionHandler
from core.conversation_session_state import ConversationSessionStateRegistry
from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
from core.utils.modules_initialize import initialize_modules
from core.utils.util import check_asr_update, check_vad_update

TAG = __name__
logger = setup_logging()

RUNTIME_DEBUG_AUTH_SECRET = os.environ.get(
    "XIAOZHI_DEBUG_AUTH_SECRET",
    "04219c19-8d5b-410c-84af-511faf293509",
)
RUNTIME_DEBUG_DEVICE_ID = os.environ.get(
    "XIAOZHI_DEBUG_DEVICE_ID",
    "E8:3D:C1:F5:49:B8",
)


class NoLiveRuntimeConnectionError(RuntimeError):
    pass


class DebugRuntimeTransport:
    def __init__(self):
        self.closed = False
        self.state = type("DebugState", (), {"name": "OPEN"})()
        self._turn_lock = asyncio.Lock()
        self._result_future: Optional[asyncio.Future] = None
        self._pending_chunks = []
        self._latest_runtime_debug: Dict[str, Any] = {}
        self._latest_llm_text = ""
        self._latest_reply_text = ""
        self._turn_completed = False

    async def begin_turn(self):
        async with self._turn_lock:
            if self._result_future is not None and not self._result_future.done():
                raise RuntimeError("上一轮回复仍未完成，请稍后再试")
            loop = asyncio.get_running_loop()
            self._pending_chunks = []
            self._latest_runtime_debug = {}
            self._latest_llm_text = ""
            self._latest_reply_text = ""
            self._turn_completed = False
            self._result_future = loop.create_future()

    async def wait_result(self, timeout_seconds: float):
        if self._result_future is None:
            raise RuntimeError("当前没有进行中的调试轮次")
        result = await asyncio.wait_for(self._result_future, timeout=timeout_seconds)
        self._result_future = None
        return result

    async def send(self, payload):
        if self.closed or isinstance(payload, bytes):
            return
        try:
            message = json.loads(payload)
        except Exception:
            return

        message_type = message.get("type")
        if message_type == "runtime_debug":
            self._latest_runtime_debug = {
                "stage": message.get("stage"),
                "scene": message.get("scene"),
                "dialogue_state": message.get("dialogue_state"),
                "response_plan": message.get("response_plan"),
                "response_rewrite": message.get("response_rewrite"),
            }
            if message.get("stage") == "post_reply":
                self._turn_completed = True
                self._maybe_finish_result()
            return
        if message_type == "llm":
            llm_text = str(message.get("text") or "").strip()
            if llm_text:
                self._latest_llm_text = llm_text
            return
        if message_type != "tts":
            return

        state = message.get("state")
        if state == "sentence_start":
            chunk_text = str(message.get("text") or "").strip()
            if chunk_text:
                self._pending_chunks.append(chunk_text)
            return
        if state != "stop":
            return
        self._turn_completed = True
        self._maybe_finish_result()

    def _resolve_reply_text(self):
        if self._latest_reply_text:
            return self._latest_reply_text
        runtime_debug = dict(self._latest_runtime_debug or {})
        rewrite = runtime_debug.get("response_rewrite") or {}
        rewritten_reply = str(rewrite.get("rewritten_reply") or "").strip()
        if rewritten_reply:
            return rewritten_reply
        reply_text = "\n".join(part for part in self._pending_chunks if part).strip()
        if reply_text:
            return reply_text
        return self._latest_llm_text.strip()

    def _maybe_finish_result(self):
        if self._result_future is None or self._result_future.done():
            return
        if not self._turn_completed:
            return
        reply_text = self._resolve_reply_text()
        if not reply_text:
            return
        self._result_future.set_result(
            {
                "reply": reply_text,
                "runtime_debug": dict(self._latest_runtime_debug or {}),
            }
        )

    def capture_reply(self, reply_text, runtime_debug, loop):
        self._latest_reply_text = str(reply_text or "").strip()
        self._latest_runtime_debug = dict(runtime_debug or {})
        self._turn_completed = True
        if loop is not None:
            loop.call_soon_threadsafe(self._maybe_finish_result)

    async def close(self):
        self.closed = True
        self.state.name = "CLOSED"
        if self._result_future is not None and not self._result_future.done():
            self._result_future.set_exception(RuntimeError("调试会话已关闭"))


class DebugTextOnlyTTS:
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.tts_text_queue = queue.Queue()
        self.tts_audio_queue = queue.Queue()
        self._sentence_text_map: Dict[str, str] = {}
        self._text_thread = None

    async def open_audio_channels(self, conn):
        self.conn = conn
        if self._text_thread is None or not self._text_thread.is_alive():
            self._text_thread = threading.Thread(
                target=self._tts_text_priority_thread,
                daemon=True,
            )
            self._text_thread.start()

    def store_tts_text(self, sentence_id, text):
        if sentence_id and text:
            self._sentence_text_map[sentence_id] = text
            if len(self._sentence_text_map) > 8:
                oldest = next(iter(self._sentence_text_map))
                del self._sentence_text_map[oldest]

    def get_tts_text(self, sentence_id):
        return self._sentence_text_map.get(sentence_id)

    def clear_tts_text(self, sentence_id):
        self._sentence_text_map.pop(sentence_id, None)

    def tts_one_sentence(
        self,
        conn,
        content_type,
        content_detail=None,
        content_file=None,
        sentence_id=None,
    ):
        if not sentence_id:
            if conn.sentence_id:
                sentence_id = conn.sentence_id
            else:
                sentence_id = str(time.time_ns())
                conn.sentence_id = sentence_id
        self.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=content_type,
                content_detail=content_detail,
                content_file=content_file,
            )
        )

    def _send_json(self, payload: Dict[str, Any]):
        if self.conn is None or self.conn.loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.conn.websocket.send(json.dumps(payload, ensure_ascii=False)),
                self.conn.loop,
            )
        except Exception as e:
            logger.bind(tag=TAG).warning(f"调试TTS消息发送失败: {e}")

    def _tts_text_priority_thread(self):
        while self.conn is not None and not self.conn.stop_event.is_set():
            try:
                message = self.tts_text_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            except Exception:
                continue

            if message.sentence_id != self.conn.sentence_id:
                continue

            if message.content_type == ContentType.TEXT:
                text = str(message.content_detail or "").strip()
                if text:
                    self._send_json(
                        {
                            "type": "tts",
                            "state": "sentence_start",
                            "session_id": self.conn.session_id,
                            "text": text,
                        }
                    )

            if message.sentence_type == SentenceType.LAST:
                self._send_json(
                    {
                        "type": "tts",
                        "state": "stop",
                        "session_id": self.conn.session_id,
                    }
                )

    async def close(self):
        return


class RuntimeDebugTextSession:
    def __init__(
        self,
        session_key: str,
        config: dict,
        server,
        session_state_registry,
        device_id: Optional[str] = None,
    ):
        self.session_key = session_key
        self.config = config
        self.server = server
        self.session_state_registry = session_state_registry
        self.device_id = self._normalize_device_id(device_id or RUNTIME_DEBUG_DEVICE_ID)
        self.client_id = f"kb-admin-client-{session_key[:12]}"
        self.transport = DebugRuntimeTransport()
        self.lock = asyncio.Lock()
        self.last_activity = time.time()
        self.text_only_conn: Optional[ConnectionHandler] = None

    def _normalize_device_id(self, device_id: Optional[str]) -> str:
        normalized = str(device_id or "").strip().lower()
        return normalized or str(RUNTIME_DEBUG_DEVICE_ID).strip().lower()

    def _resolve_live_connection(self):
        registry = getattr(self.server, "live_connection_registry", None) if self.server is not None else None
        if registry is None:
            return None
        return registry.get_by_device_id(self.device_id)

    async def _ensure_text_only_connection(self) -> ConnectionHandler:
        if self.text_only_conn is not None:
            return self.text_only_conn

        conn_config = copy.deepcopy(self.config)
        private_config = {}
        try:
            private_config = await get_private_config_from_api(
                conn_config,
                self.device_id,
                self.client_id,
            ) or {}
        except Exception as e:
            logger.bind(tag=TAG).warning(f"text-only fallback private config unavailable: {e}")

        init_llm = init_tts = init_memory = init_intent = False
        init_vad = check_vad_update(conn_config, private_config)
        init_asr = check_asr_update(conn_config, private_config)
        if init_vad:
            conn_config["VAD"] = private_config["VAD"]
            conn_config["selected_module"]["VAD"] = private_config["selected_module"]["VAD"]
        if init_asr:
            conn_config["ASR"] = private_config["ASR"]
            conn_config["selected_module"]["ASR"] = private_config["selected_module"]["ASR"]
        if private_config.get("TTS") is not None:
            init_tts = True
            conn_config["TTS"] = private_config["TTS"]
            conn_config["selected_module"]["TTS"] = private_config["selected_module"]["TTS"]
        if private_config.get("LLM") is not None:
            init_llm = True
            conn_config["LLM"] = private_config["LLM"]
            conn_config["selected_module"]["LLM"] = private_config["selected_module"]["LLM"]
        if private_config.get("Memory") is not None:
            init_memory = True
            conn_config["Memory"] = private_config["Memory"]
            conn_config["selected_module"]["Memory"] = private_config["selected_module"]["Memory"]
        if private_config.get("Intent") is not None:
            init_intent = True
            conn_config["Intent"] = private_config["Intent"]
            conn_config["selected_module"]["Intent"] = private_config["selected_module"]["Intent"]
        if private_config.get("prompt") is not None:
            conn_config["prompt"] = private_config["prompt"]
        if private_config.get("summaryMemory") is not None:
            conn_config["summaryMemory"] = private_config["summaryMemory"]
        if private_config.get("device_max_output_size") is not None:
            conn_config["device_max_output_size"] = private_config["device_max_output_size"]
        if private_config.get("chat_history_conf") is not None:
            conn_config["chat_history_conf"] = private_config["chat_history_conf"]

        modules = initialize_modules(
            logger,
            conn_config,
            init_vad,
            init_asr,
            init_llm,
            init_tts,
            init_memory,
            init_intent,
        )
        conn = ConnectionHandler(
            conn_config,
            modules.get("vad"),
            modules.get("asr"),
            modules.get("llm"),
            modules.get("memory"),
            modules.get("intent"),
            self.server,
            session_state=self.session_state_registry.get_or_create(self.device_id),
        )
        conn.loop = asyncio.get_running_loop()
        conn.headers = {
            "device-id": self.device_id,
            "client-id": self.client_id,
            "x-debug-bypass-bind": "1",
        }
        conn.device_id = self.device_id
        conn.client_ip = "127.0.0.1"
        conn.debug_bypass_bind = True
        conn.need_bind = False
        conn.bind_completed_event.set()
        conn._initialize_memory()
        conn._initialize_intent()
        conn.tts = modules.get("tts") or DebugTextOnlyTTS(conn.config)
        if not isinstance(conn.tts, DebugTextOnlyTTS):
            conn.tts = DebugTextOnlyTTS(conn.config)
        await conn.tts.open_audio_channels(conn)
        self.text_only_conn = conn
        return conn

    def _build_result_from_conn(self, conn: ConnectionHandler, dialogue_len_before: int):
        messages = getattr(conn.dialogue, "dialogue", []) or []
        new_messages = messages[dialogue_len_before:]
        assistant_texts = [
            str(message.content or "").strip()
            for message in new_messages
            if getattr(message, "role", None) == "assistant" and str(message.content or "").strip()
        ]
        if not assistant_texts:
            assistant_texts = [
                str(message.content or "").strip()
                for message in reversed(messages)
                if getattr(message, "role", None) == "assistant" and str(message.content or "").strip()
            ][:1]
        reply_text = "\n".join(text for text in assistant_texts if text).strip()
        runtime_debug = conn._build_runtime_debug_payload()
        if not reply_text:
            rewrite = (runtime_debug or {}).get("response_rewrite") or {}
            reply_text = str(rewrite.get("rewritten_reply") or "").strip()
        if not reply_text:
            raise RuntimeError("empty runtime reply")
        return {
            "reply": reply_text,
            "runtime_debug": runtime_debug,
        }

    async def _run_turn_on_conn(self, conn: ConnectionHandler, text: str, timeout_seconds: float):
        await self.transport.begin_turn()
        dialogue_len_before = len(getattr(conn.dialogue, "dialogue", []) or [])
        previous_hook = getattr(conn, "_runtime_result_hook", None)
        previous_websocket = conn.websocket
        previous_tts = conn.tts
        conn._runtime_result_hook = self.transport.capture_reply
        conn.websocket = self.transport
        if previous_tts is not None and not isinstance(previous_tts, DebugTextOnlyTTS):
            debug_tts = DebugTextOnlyTTS(conn.config)
            await debug_tts.open_audio_channels(conn)
            conn.tts = debug_tts
        submitted_calls = []
        original_submit = conn.executor.submit

        def _submit_with_capture(fn, *args, **kwargs):
            future = original_submit(fn, *args, **kwargs)
            submitted_calls.append((fn, future))
            return future

        conn.executor.submit = _submit_with_capture
        try:
            await conn.run_text_turn(text)

            chat_future = None
            for fn, future in submitted_calls:
                if getattr(fn, "__name__", "") == "chat":
                    chat_future = future
                    break

            if chat_future is not None:
                await asyncio.wait_for(asyncio.wrap_future(chat_future, loop=conn.loop), timeout=timeout_seconds)
                return self._build_result_from_conn(conn, dialogue_len_before)
            return await self.transport.wait_result(timeout_seconds)
        finally:
            conn.executor.submit = original_submit
            conn._runtime_result_hook = previous_hook
            conn.websocket = previous_websocket
            if conn.tts is not previous_tts:
                try:
                    await conn.tts.close()
                except Exception:
                    pass
                conn.tts = previous_tts

    async def send_turn(self, text: str, timeout_seconds: float = 90):
        async with self.lock:
            live_conn = self._resolve_live_connection()
            mode = "live"
            if live_conn is None:
                mode = "text_only_fallback"
                conn = await self._ensure_text_only_connection()
            else:
                conn = live_conn
            async with conn.turn_lock:
                result = await self._run_turn_on_conn(conn, text, timeout_seconds)
            self.last_activity = time.time()
            result["mode"] = mode
            result["device_id"] = self.device_id
            return result

    async def close(self):
        async with self.lock:
            await self.transport.close()
            if self.text_only_conn is not None:
                try:
                    await self.text_only_conn.tts.close()
                except Exception:
                    pass
                self.text_only_conn.executor.shutdown(wait=False)
                self.text_only_conn.stop_event.set()
                self.text_only_conn = None


class RuntimeDebugTextSessionManager:
    def __init__(self, config: dict, server):
        self.config = config
        self.server = server
        self.sessions: Dict[str, RuntimeDebugTextSession] = {}
        self.lock = asyncio.Lock()
        if (
            self.server is not None
            and getattr(self.server, "session_state_registry", None) is not None
        ):
            self.session_state_registry = self.server.session_state_registry
        else:
            self.session_state_registry = ConversationSessionStateRegistry()

    def _session_registry_key(self, session_key: str, device_id: str) -> str:
        normalized_device_id = str(device_id or RUNTIME_DEBUG_DEVICE_ID).strip().lower() or str(RUNTIME_DEBUG_DEVICE_ID).strip().lower()
        return f"{normalized_device_id}::{session_key}"

    async def get_session(self, session_key: str, device_id: Optional[str] = None):
        registry_key = self._session_registry_key(session_key, device_id or RUNTIME_DEBUG_DEVICE_ID)
        normalized_device_id = str(device_id or RUNTIME_DEBUG_DEVICE_ID).strip().lower() or str(RUNTIME_DEBUG_DEVICE_ID).strip().lower()
        async with self.lock:
            self._cleanup_stale_sessions_locked()
            session = self.sessions.get(registry_key)
            if session is None:
                session = RuntimeDebugTextSession(
                    session_key,
                    self.config,
                    self.server,
                    self.session_state_registry,
                    device_id=normalized_device_id,
                )
                self.sessions[registry_key] = session
            else:
                session.device_id = normalized_device_id
            session.last_activity = time.time()
            return session

    async def reset_session(self, session_key: str, device_id: Optional[str] = None):
        normalized_device_id = str(device_id or RUNTIME_DEBUG_DEVICE_ID).strip().lower() or str(RUNTIME_DEBUG_DEVICE_ID).strip().lower()
        registry_key = self._session_registry_key(session_key, normalized_device_id)
        async with self.lock:
            session = self.sessions.pop(registry_key, None)
        if session is not None:
            await session.close()

        live_registry = getattr(self.server, "live_connection_registry", None) if self.server is not None else None
        live_conn = live_registry.get_by_device_id(normalized_device_id) if live_registry is not None else None
        if live_conn is not None:
            async with live_conn.turn_lock:
                live_conn.reset_runtime_session()
        else:
            cleared = self.session_state_registry.clear_in_place(normalized_device_id)
            if not cleared:
                self.session_state_registry.reset(normalized_device_id)

    def _cleanup_stale_sessions_locked(self):
        now = time.time()
        stale_keys = [
            key
            for key, session in self.sessions.items()
            if now - session.last_activity > 1800
        ]
        for key in stale_keys:
            session = self.sessions.pop(key, None)
            if session is not None:
                asyncio.create_task(session.close())
