import asyncio
import copy
import concurrent.futures
import json
import os
import queue
import threading
import time
from typing import Any, Dict, Optional

from core.connection import ConnectionHandler
from core.conversation_session_state import ConversationSessionStateRegistry
from core.handle.textHandle import handleTextMessage
from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
from config.logger import setup_logging

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
        if self.closed:
            return
        if isinstance(payload, bytes):
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
    def __init__(self, session_key: str, config: dict, server, session_state_registry):
        self.session_key = session_key
        self.config = config
        self.server = server
        self.session_state_registry = session_state_registry
        self.device_id = RUNTIME_DEBUG_DEVICE_ID
        self.client_id = f"kb-admin-client-{session_key[:12]}"
        self.transport = DebugRuntimeTransport()
        self.conn: Optional[ConnectionHandler] = None
        self.lock = asyncio.Lock()
        self.last_activity = time.time()
        self.initialized = False

    async def _initialize(self):
        if (
            self.initialized
            and self.conn is not None
            and not self.transport.closed
            and not self.conn.stop_event.is_set()
            and self.conn.executor is not None
        ):
            return
        self.transport = DebugRuntimeTransport()

        conn = ConnectionHandler(
            copy.deepcopy(self.config),
            self.server._vad,
            self.server._asr,
            self.server._llm,
            self.server._memory,
            self.server._intent,
            self.server,
            session_state=self.session_state_registry.get_or_create(self.device_id),
        )
        conn.loop = asyncio.get_running_loop()
        conn.headers = {
            "device-id": self.device_id,
            "client-id": self.client_id,
        }
        conn.client_ip = "127.0.0.1"
        conn.device_id = self.device_id
        conn.debug_bypass_bind = False
        conn.websocket = self.transport
        conn.conn_from_mqtt_gateway = False
        conn.first_activity_time = time.time() * 1000
        conn.last_activity_time = time.time() * 1000
        conn.timeout_task = asyncio.create_task(conn._check_timeout())
        conn.welcome_msg = copy.deepcopy(conn.config["xiaozhi"])
        conn.welcome_msg["session_id"] = conn.session_id
        conn.sample_rate = conn.welcome_msg["audio_params"]["sample_rate"]
        await conn._initialize_private_config_async()
        conn.tts = DebugTextOnlyTTS(conn.config)
        conn._initialize_components()
        original_record_assistant_reply = conn._record_assistant_reply

        def _record_assistant_reply_debug(reply_text, next_action=None):
            original_record_assistant_reply(reply_text, next_action=next_action)
            try:
                self.transport.capture_reply(
                    reply_text,
                    conn._build_runtime_debug_payload(),
                    conn.loop,
                )
            except Exception:
                pass

        conn._record_assistant_reply = _record_assistant_reply_debug
        self.conn = conn
        self.initialized = True

    async def send_turn(self, text: str, timeout_seconds: float = 90):
        async with self.lock:
            await self._initialize()
            await self.transport.begin_turn()
            dialogue_len_before = len(getattr(self.conn.dialogue, "dialogue", []) or [])
            submitted_calls = []
            original_submit = self.conn.executor.submit

            def _submit_with_capture(fn, *args, **kwargs):
                future = original_submit(fn, *args, **kwargs)
                submitted_calls.append((fn, future))
                return future

            self.conn.executor.submit = _submit_with_capture
            payload = json.dumps(
                {
                    "type": "listen",
                    "state": "detect",
                    "mode": "auto",
                    "text": text,
                },
                ensure_ascii=False,
            )
            try:
                await handleTextMessage(self.conn, payload)
            finally:
                self.conn.executor.submit = original_submit

            chat_future = None
            for fn, future in submitted_calls:
                fn_name = getattr(fn, "__name__", "")
                if fn_name == "chat":
                    chat_future = future
                    break

            if chat_future is not None:
                await asyncio.wrap_future(chat_future, loop=self.conn.loop)
                result = self._build_result_from_conn(dialogue_len_before)
            else:
                result = await self.transport.wait_result(timeout_seconds)
            self.last_activity = time.time()
            return result

    def _build_result_from_conn(self, dialogue_len_before: int):
        messages = getattr(self.conn.dialogue, "dialogue", []) or []
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
        runtime_debug = self.conn._build_runtime_debug_payload()
        if not reply_text:
            rewrite = (runtime_debug or {}).get("response_rewrite") or {}
            reply_text = str(rewrite.get("rewritten_reply") or "").strip()
        if not reply_text:
            raise RuntimeError("empty runtime reply")
        return {
            "reply": reply_text,
            "runtime_debug": runtime_debug,
        }

    async def close(self):
        async with self.lock:
            if self.conn is not None:
                await self.conn.close()
                self.conn = None
            await self.transport.close()
            self.initialized = False


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

    async def get_session(self, session_key: str):
        async with self.lock:
            self._cleanup_stale_sessions_locked()
            session = self.sessions.get(session_key)
            if session is None:
                session = RuntimeDebugTextSession(
                    session_key,
                    self.config,
                    self.server,
                    self.session_state_registry,
                )
                self.sessions[session_key] = session
            session.last_activity = time.time()
            return session

    async def reset_session(self, session_key: str):
        async with self.lock:
            session = self.sessions.pop(session_key, None)
        if session is not None:
            await session.close()
        self.session_state_registry.reset(RUNTIME_DEBUG_DEVICE_ID)

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
