import asyncio
import json
import ssl
import uuid
from typing import TYPE_CHECKING, List, Optional, Tuple

import opuslib_next
import websockets

from config.logger import setup_logging
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType
from core.providers.asr.utils import lang_tag_filter

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.STREAM
        self.config = config
        self.text = ""
        self.decoder = opuslib_next.Decoder(16000, 1)
        self.asr_ws = None
        self._start_task = None
        self.forward_task = None
        self.is_processing = False
        self.server_ready = False
        self.session_task_id = None
        self._pending_final_text = ""
        self._pending_final_audio = None
        self._pending_final_at = 0.0
        self._pending_final_voice_packets = 0
        self._final_text_segments = []
        self._stop_sent = False
        self._stop_sent_at = 0.0
        self._no_result_reported = False
        self._stream_audio_sent_count = 0
        self._last_start_failed_at = 0.0
        self._start_failure_logged = False
        self._stream_audio_sent_count = 0

        self.host = config.get("host", "localhost")
        self.port = int(config.get("port", 10095))
        self.api_key = config.get("api_key", "none")
        self.is_ssl = str(config.get("is_ssl", False)).lower() in ("true", "1", "yes")
        self.mode = config.get("mode", "2pass")
        self.chunk_size = config.get("chunk_size", [5, 10, 5])
        self.chunk_interval = int(config.get("chunk_interval", 10))
        self.itn = bool(config.get("itn", True))
        self.final_grace_ms = int(config.get("final_sentence_grace_ms", 800))
        self.stop_no_result_timeout_ms = int(config.get("stop_no_result_timeout_ms", 1200))
        self.connect_timeout_ms = int(config.get("connect_timeout_ms", 1500))
        self.start_fail_cooldown_ms = int(config.get("start_fail_cooldown_ms", 2000))
        self.output_dir = config.get("output_dir", "tmp/")
        self.delete_audio_file = delete_audio_file

        scheme = "wss" if self.is_ssl else "ws"
        self.uri = f"{scheme}://{self.host}:{self.port}"
        self.ssl_context = ssl.SSLContext() if self.is_ssl else None
        if self.ssl_context:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

    def _merge_final_text(self, text: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return self._pending_final_text
        existing = "".join(self._final_text_segments).strip()
        if existing and normalized.startswith(existing):
            self._final_text_segments = [normalized]
        elif existing and normalized in existing:
            pass
        else:
            self._final_text_segments.append(normalized)
        return "".join(self._final_text_segments).strip()

    def _normalize_text(self, text):
        if isinstance(text, dict):
            text = text.get("content", "")
        filtered = lang_tag_filter(str(text or "").strip())
        if isinstance(filtered, dict):
            return str(filtered.get("content") or "").strip()
        return str(filtered or "").strip()

    def _set_pending_final(self, conn: "ConnectionHandler", text: str, audio_data):
        normalized = self._normalize_text(text)
        if not normalized:
            return
        self._pending_final_text = self._merge_final_text(normalized)
        self._pending_final_audio = list(audio_data or [])
        self._pending_final_at = asyncio.get_running_loop().time()
        stats = getattr(conn, "asr_turn_audio_stats", {}) or {}
        self._pending_final_voice_packets = int(stats.get("voice_packets") or 0)

    def _pending_final_ready(self, conn: "ConnectionHandler") -> bool:
        if not self._pending_final_text:
            return False
        if conn.client_voice_stop:
            return True
        if self.final_grace_ms <= 0 or not self._pending_final_at:
            return False
        elapsed_ms = (asyncio.get_running_loop().time() - self._pending_final_at) * 1000
        if elapsed_ms < self.final_grace_ms:
            return False
        stats = getattr(conn, "asr_turn_audio_stats", {}) or {}
        voice_packets = int(stats.get("voice_packets") or 0)
        if voice_packets > self._pending_final_voice_packets:
            self._pending_final_at = asyncio.get_running_loop().time()
            self._pending_final_voice_packets = voice_packets
            return False
        return True

    async def open_audio_channels(self, conn):
        await super().open_audio_channels(conn)

    def _start_cooldown_remaining_ms(self) -> int:
        if not self._last_start_failed_at or self.start_fail_cooldown_ms <= 0:
            return 0
        elapsed_ms = (asyncio.get_running_loop().time() - self._last_start_failed_at) * 1000
        return max(0, int(self.start_fail_cooldown_ms - elapsed_ms))

    def _can_attempt_start(self) -> bool:
        return self._start_cooldown_remaining_ms() <= 0

    def _record_start_failure(self):
        self._last_start_failed_at = asyncio.get_running_loop().time()
        self._start_failure_logged = False

    def _log_start_cooldown_once(self):
        if self._start_failure_logged:
            return
        logger.bind(tag=TAG).warning(
            "[FunASRStream] start suppressed during cooldown "
            f"remaining_ms={self._start_cooldown_remaining_ms()}"
        )
        self._start_failure_logged = True

    async def _consume_start_task_if_done(self):
        if not self._start_task or not self._start_task.done():
            return
        task = self._start_task
        self._start_task = None
        try:
            await task
        except Exception as e:
            logger.bind(tag=TAG).error(f"FunASR流式识别启动失败: {e}", exc_info=True)
            self._record_start_failure()
            await self._cleanup(send_stop=False)

    async def _wait_for_start_task(self, conn: "ConnectionHandler") -> bool:
        if not self._start_task:
            return True
        task = self._start_task
        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=max(self.connect_timeout_ms / 1000.0 + 0.5, 0.5),
            )
            return True
        except Exception as e:
            logger.bind(tag=TAG).error(f"FunASR流式识别启动失败: {e}", exc_info=True)
            self._record_start_failure()
            self._start_task = None
            await self._handle_no_result_after_stop(
                conn,
                "funasr_stream_start_failed_before_stop",
            )
            await self._cleanup(send_stop=False)
            return False
        finally:
            if self._start_task and self._start_task.done():
                self._start_task = None

    async def _flush_unsent_audio(self, conn: "ConnectionHandler"):
        if not self.asr_ws or not self.server_ready:
            return
        audio_data = list(conn.asr_audio or [])
        start_index = max(0, min(self._stream_audio_sent_count, len(audio_data)))
        if start_index >= len(audio_data):
            return
        pending_audio = audio_data[start_index:]
        logger.bind(tag=TAG).info(
            f"[FunASRStream] flushing cached audio before stop packets={len(pending_audio)} "
            f"from_index={start_index} total={len(audio_data)}"
        )
        for cached_frame in pending_audio:
            try:
                pcm_frame = self.decoder.decode(cached_frame, 960)
                self.track_upstream_audio(conn, pcm_frame, cached=True)
                await self.asr_ws.send(pcm_frame)
                self._stream_audio_sent_count += 1
            except Exception as e:
                self.track_upstream_error(conn)
                logger.bind(tag=TAG).warning(f"FunASR stop前缓存音频发送失败: {e}")
                break

    async def receive_audio(self, conn, audio, audio_have_voice):
        await super().receive_audio(conn, audio, audio_have_voice)
        await self._consume_start_task_if_done()

        # For wake-word-free auto mode, the device owns the capture boundary
        # via listen/start and listen/stop. Do not rely solely on server-side
        # VAD to start the FunASR stream; server VAD can miss quiet speech and
        # leave the device waiting forever after listen/stop.
        should_start_stream = (
            audio_have_voice or str(getattr(conn, "client_listen_mode", "")) != "manual"
        )
        if (
            should_start_stream
            and not self.is_processing
            and not self.asr_ws
            and not self._start_task
        ):
            if not self._can_attempt_start():
                self._log_start_cooldown_once()
                return
            self._start_task = asyncio.create_task(self._start_recognition(conn))
            return

        if self.asr_ws and self.is_processing and self.server_ready:
            try:
                pcm_frame = self.decoder.decode(audio, 960)
                self.track_upstream_audio(conn, pcm_frame)
                await self.asr_ws.send(pcm_frame)
                self._stream_audio_sent_count = max(
                    self._stream_audio_sent_count,
                    len(conn.asr_audio or []),
                )
            except Exception as e:
                self.track_upstream_error(conn)
                logger.bind(tag=TAG).warning(f"FunASR音频发送失败: {e}")
                await self._cleanup(send_stop=False)

        if self.asr_ws and conn.client_voice_stop and not self._stop_sent:
            await self._send_stop_request(conn)

    async def _send_stop(self):
        if not self.asr_ws or self._stop_sent:
            return
        self._stop_sent = True
        self._stop_sent_at = asyncio.get_running_loop().time()
        self.is_processing = False
        await self.asr_ws.send(json.dumps({"is_speaking": False}, ensure_ascii=False))
        logger.bind(tag=TAG).debug("[FunASRStream] sent stop")

    async def _send_stop_request(self, conn: Optional["ConnectionHandler"] = None):
        if self._stop_sent:
            return

        if conn is not None and not await self._wait_for_start_task(conn):
            return

        if not self.asr_ws:
            if conn is not None and conn.asr_audio:
                logger.bind(tag=TAG).warning(
                    "[FunASRStream] listen/stop received before stream started; "
                    f"forcing recognition with cached_packets={len(conn.asr_audio)}"
                )
                try:
                    await self._start_recognition(conn, cached_audio=list(conn.asr_audio))
                except Exception as e:
                    logger.bind(tag=TAG).error(
                        f"FunASR强制启动识别失败: {e}", exc_info=True
                    )
                    self._record_start_failure()
                    await self._handle_no_result_after_stop(
                        conn,
                        "funasr_stream_force_start_failed",
                    )
                    await self._cleanup(send_stop=False)
                    return
            else:
                logger.bind(tag=TAG).warning(
                    "[FunASRStream] listen/stop ignored: stream not started and no audio"
                )
                if conn is not None:
                    await self._handle_no_result_after_stop(
                        conn,
                        "funasr_stream_stop_without_audio",
                    )
                return

        try:
            if conn is not None:
                await self._flush_unsent_audio(conn)
            await self._send_stop()
        except websockets.ConnectionClosed as e:
            logger.bind(tag=TAG).warning(
                f"[FunASRStream] stop skipped because service connection is closed: {e}"
            )
            await self._cleanup(send_stop=False)
        except Exception as e:
            logger.bind(tag=TAG).warning(f"[FunASRStream] stop send failed: {e}")
            await self._cleanup(send_stop=False)

    async def _start_recognition(self, conn: "ConnectionHandler", cached_audio=None):
        self.session_task_id = uuid.uuid4().hex
        self.is_processing = True
        self.server_ready = False
        self._stop_sent = False
        self._stop_sent_at = 0.0
        self._no_result_reported = False

        auth_header = {}
        if self.api_key and self.api_key != "none":
            auth_header["Authorization"] = f"Bearer; {self.api_key}"

        logger.bind(tag=TAG).info(
            f"[FunASRStream] connecting uri={self.uri} mode={self.mode} task={self.session_task_id}"
        )
        self.asr_ws = await websockets.connect(
            self.uri,
            additional_headers=auth_header,
            subprotocols=["binary"],
            max_size=1000000000,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=5,
            open_timeout=max(self.connect_timeout_ms / 1000.0, 0.1),
            ssl=self.ssl_context,
        )
        self._last_start_failed_at = 0.0
        self._start_failure_logged = False

        self.forward_task = asyncio.create_task(self._forward_results(conn))
        config_message = {
            "mode": self.mode,
            "chunk_size": self.chunk_size,
            "chunk_interval": self.chunk_interval,
            "wav_name": self.session_task_id,
            "is_speaking": True,
            "itn": self.itn,
        }
        await self.asr_ws.send(json.dumps(config_message, ensure_ascii=False))
        self.server_ready = True

        replay_audio = cached_audio if cached_audio is not None else list(conn.asr_audio or [])
        if replay_audio:
            for cached_frame in replay_audio:
                try:
                    pcm_frame = self.decoder.decode(cached_frame, 960)
                    self.track_upstream_audio(conn, pcm_frame, cached=True)
                    await self.asr_ws.send(pcm_frame)
                except Exception as e:
                    self.track_upstream_error(conn)
                    logger.bind(tag=TAG).warning(f"FunASR缓存音频发送失败: {e}")
                    break
            self._stream_audio_sent_count = max(
                self._stream_audio_sent_count,
                len(replay_audio),
            )

    async def _finalize_pending(self, conn: "ConnectionHandler", audio_data, reason: str):
        if not self._pending_final_text:
            return
        self.text = self._pending_final_text
        conn.asr_final_reason = reason
        await self.handle_voice_stop(
            conn,
            self._pending_final_audio or audio_data or conn.asr_audio,
        )

    def _stop_no_result_timed_out(self) -> bool:
        if not self._stop_sent or self._pending_final_text:
            return False
        if self.stop_no_result_timeout_ms <= 0 or not self._stop_sent_at:
            return False
        elapsed_ms = (asyncio.get_running_loop().time() - self._stop_sent_at) * 1000
        return elapsed_ms >= self.stop_no_result_timeout_ms

    async def _handle_no_result_after_stop(
        self,
        conn: "ConnectionHandler",
        reason: str = "funasr_stream_no_result_after_stop",
    ):
        if self._no_result_reported:
            return
        self._no_result_reported = True
        audio_snapshot = list(conn.asr_audio or [])
        self.log_asr_turn_summary(conn, audio_snapshot, "", reason)
        if hasattr(conn, "mark_latency_stage"):
            conn.mark_latency_stage("asr_final", text="", reason=reason)
        logger.bind(tag=TAG).warning(
            f"[FunASRStream] no ASR result after stop; reason={reason} "
            f"buffer_packets={len(audio_snapshot)}"
        )
        try:
            from core.handle.sendAudioHandle import send_tts_message

            await send_tts_message(conn, "stop", None)
        except Exception as e:
            logger.bind(tag=TAG).warning(
                f"[FunASRStream] failed to notify client stop after empty ASR: {e}"
            )

    async def _forward_results(self, conn: "ConnectionHandler"):
        try:
            while not conn.stop_event.is_set():
                audio_data = list(conn.asr_audio or [])
                try:
                    recv_timeout = 0.2 if self._pending_final_text else 1.0
                    response = await asyncio.wait_for(self.asr_ws.recv(), timeout=recv_timeout)
                    if isinstance(response, bytes):
                        continue
                    result = json.loads(response)
                    text = self._normalize_text(result.get("text", ""))
                    mode = str(result.get("mode") or "").strip()
                    is_final = bool(result.get("is_final", False))

                    if text:
                        logger.bind(tag=TAG).info(
                            f"[FunASRStream] result mode={mode or '-'} final={is_final} text={text}"
                        )

                    # 2pass-offline is the corrected final result from FunASR
                    # runtime. It is already the boundary of this utterance;
                    # waiting for another local timeout here can let the next
                    # turn overwrite the pending text.
                    if text and mode in ("2pass-offline", "offline"):
                        self._pending_final_text = text
                        self._pending_final_audio = audio_data
                        await self._finalize_pending(
                            conn,
                            audio_data,
                            "funasr_stream_2pass_offline",
                        )
                        break
                    elif text and is_final:
                        self._pending_final_text = text
                        self._pending_final_audio = audio_data
                        self._pending_final_at = asyncio.get_running_loop().time()
                    elif text and mode in ("online", "2pass-online"):
                        self._set_pending_final(conn, text, audio_data)

                    if conn.client_voice_stop and not self._stop_sent:
                        await self._send_stop()

                    if self._pending_final_ready(conn):
                        reason = (
                            "funasr_stream_voice_stop"
                            if conn.client_voice_stop
                            else "funasr_stream_final_grace_timeout"
                        )
                        await self._finalize_pending(conn, audio_data, reason)
                        break

                except asyncio.TimeoutError:
                    if conn.client_voice_stop and not self._stop_sent:
                        await self._send_stop()
                    if self._stop_no_result_timed_out():
                        await self._handle_no_result_after_stop(conn)
                        break
                    if self._pending_final_ready(conn):
                        await self._finalize_pending(
                            conn,
                            conn.asr_audio,
                            "funasr_stream_recv_timeout",
                        )
                        break
                    continue
                except websockets.ConnectionClosed:
                    logger.bind(tag=TAG).info("[FunASRStream] service connection closed")
                    if conn.client_voice_stop and not self._pending_final_text:
                        await self._handle_no_result_after_stop(
                            conn,
                            "funasr_stream_closed_without_result",
                        )
                    break
                except Exception as e:
                    logger.bind(tag=TAG).error(f"FunASR结果处理失败: {e}", exc_info=True)
                    break
        finally:
            await self._cleanup(send_stop=False)
            conn.reset_audio_states()

    async def _cleanup(self, send_stop: bool = True):
        self.is_processing = False
        self.server_ready = False
        current_task = asyncio.current_task()
        if self._start_task and self._start_task is not current_task and not self._start_task.done():
            self._start_task.cancel()
            try:
                await self._start_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        if send_stop and self.asr_ws and not self._stop_sent:
            try:
                await self._send_stop()
                await asyncio.sleep(0.1)
            except Exception:
                pass
        if self.asr_ws:
            try:
                await asyncio.wait_for(self.asr_ws.close(), timeout=2.0)
            except Exception as e:
                logger.bind(tag=TAG).debug(f"FunASR WebSocket关闭失败: {e}")
            finally:
                self.asr_ws = None
        self.forward_task = None
        self._start_task = None
        self.session_task_id = None
        self._pending_final_text = ""
        self._pending_final_audio = None
        self._pending_final_at = 0.0
        self._pending_final_voice_packets = 0
        self._final_text_segments = []
        self._stop_sent = False
        self._stop_sent_at = 0.0
        self._no_result_reported = False
        self._stream_audio_sent_count = 0

    async def speech_to_text(
        self,
        opus_data: List[bytes],
        session_id: str,
        audio_format="opus",
        artifacts=None,
    ) -> Tuple[Optional[str], Optional[str]]:
        result = self.text
        self.text = ""
        return result, None

    def stop_ws_connection(self):
        pass

    async def close(self):
        await self._cleanup()
        if getattr(self, "decoder", None) is not None:
            try:
                del self.decoder
            except Exception:
                pass
            self.decoder = None
