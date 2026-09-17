import time
import threading
import requests

from core.providers.tts.base import TTSProviderBase
from core.utils import textUtils
from core.utils.tts import convert_percentage_to_range
from config.logger import setup_logging


TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    VOICE_ALIASES = {
        "zh": "zf_xiaoxiao",
        "zh-cn": "zf_xiaoxiao",
        "mandarin_female": "zf_xiaoxiao",
        "mandarin_male": "zm_yunyang",
        "cute_female": "zf_xiaoyi",
        "strong_male": "zm_yunjian",
        "young_male": "zm_yunxi",
        "boy_male": "zm_yunxia",
        "liaoning_female": "zf_xiaobei",
        "shaanxi_female": "zf_xiaoni",
        "zh-CN-XiaoxiaoNeural": "zf_xiaoxiao",
        "zh-CN-YunyangNeural": "zm_yunyang",
        "zh-CN-XiaoyiNeural": "zf_xiaoyi",
        "zh-CN-YunjianNeural": "zm_yunjian",
        "zh-CN-YunxiNeural": "zm_yunxi",
        "zh-CN-YunxiaNeural": "zm_yunxia",
        "zh-CN-liaoning-XiaobeiNeural": "zf_xiaobei",
        "zh-CN-shaanxi-XiaoniNeural": "zf_xiaoni",
        "zh-HK-HiuGaaiNeural": "zf_xiaoxiao",
        "zh-HK-HiuMaanNeural": "zf_xiaoxiao",
        "zh-HK-WanLungNeural": "zm_yunyang",
        "TTS_EdgeTTS0001": "zf_xiaoxiao",
        "TTS_EdgeTTS0002": "zm_yunyang",
        "TTS_EdgeTTS0003": "zf_xiaoyi",
        "TTS_EdgeTTS0004": "zm_yunjian",
        "TTS_EdgeTTS0005": "zm_yunxi",
        "TTS_EdgeTTS0006": "zm_yunxia",
        "TTS_EdgeTTS0007": "zf_xiaobei",
        "TTS_EdgeTTS0008": "zf_xiaoni",
        "TTS_EdgeTTS0009": "zf_xiaoxiao",
        "TTS_EdgeTTS0010": "zf_xiaoxiao",
        "TTS_EdgeTTS0011": "zm_yunyang",
    }
    VALID_VOICE_PREFIXES = (
        "af_",
        "am_",
        "bf_",
        "bm_",
        "ef_",
        "em_",
        "ff_",
        "hf_",
        "hm_",
        "if_",
        "im_",
        "jf_",
        "jm_",
        "pf_",
        "pm_",
        "zf_",
        "zm_",
    )

    TTS_PARAM_CONFIG = [
        ("ttsRate", "speed", 0.25, 4, 1, lambda v: round(float(v), 2)),
    ]

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.api_url = config.get("api_url", "http://127.0.0.1:8880/v1/audio/speech")
        self.model = config.get("model", "kokoro")
        configured_voice = config.get("private_voice") or config.get("voice", "zf_xiaoxiao")
        self.voice = self._normalize_voice(configured_voice)
        self.audio_file_type = config.get("response_format", config.get("format", "wav"))
        self.stream_format = config.get("stream_format", "audio")
        self.api_key = config.get("api_key", "")
        self.speed = float(config.get("speed", 1.0))
        self.request_timeout = float(config.get("request_timeout", 20))
        self.connect_timeout = float(config.get("connect_timeout", 3))
        self.read_timeout = float(config.get("read_timeout", 20))
        self.max_retry_attempts = int(config.get("max_retry_attempts", 2))
        self.first_audio_timeout_ms = int(config.get("first_audio_timeout_ms", 5000))
        self.first_segment_min_chars = int(config.get("first_segment_min_chars", 6))
        self.min_segment_chars = int(config.get("min_segment_chars", 14))
        self.first_segment_max_chars = int(config.get("first_segment_max_chars", 8))
        self.max_segment_chars = int(config.get("max_segment_chars", 48))
        self.segment_punctuations = tuple(
            config.get(
                "segment_punctuations",
                "，,、。！？!?；;：:\n",
            )
        )
        self._http_session = requests.Session()
        self._http_session_lock = threading.Lock()
        self._kokoro_segment_history = []

        self._apply_percentage_params(config)

        if self.api_key:
            if "Bearer " in self.api_key:
                self.authorization = self.api_key
            else:
                self.authorization = f"Bearer {self.api_key}"
        else:
            self.authorization = ""

    def _normalize_voice(self, voice):
        raw_voice = str(voice or "").strip()
        if not raw_voice:
            return "zf_xiaoxiao"
        mapped_voice = self.VOICE_ALIASES.get(raw_voice) or self.VOICE_ALIASES.get(
            raw_voice.lower()
        )
        if mapped_voice:
            return mapped_voice
        if raw_voice.startswith(self.VALID_VOICE_PREFIXES):
            return raw_voice
        logger.bind(tag=TAG).warning(
            f"Kokoro voice '{raw_voice}' is not supported, fallback to zf_xiaoxiao"
        )
        return "zf_xiaoxiao"

    def _build_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.authorization:
            headers["Authorization"] = self.authorization
        return headers

    def _set_response_socket_timeout(self, response, timeout):
        try:
            sock = response.raw._fp.fp.raw._sock
            sock.settimeout(timeout)
        except Exception:
            logger.bind(tag=TAG).debug("Kokoro response socket timeout update skipped")

    def _normalize_segment_text(self, text):
        return textUtils.get_string_no_punctuation_or_emoji(text or "").strip()

    def _split_kokoro_segments(self, text):
        pending = str(text or "")
        segments = []
        while pending:
            if len(pending) <= self.max_segment_chars:
                normalized = self._normalize_segment_text(pending)
                if normalized:
                    segments.append(normalized)
                break

            split_pos = -1
            search_window = pending[: self.max_segment_chars + 1]
            for punct in self.segment_punctuations:
                pos = search_window.rfind(punct)
                if pos > 0 and pos + 1 >= self.min_segment_chars:
                    split_pos = max(split_pos, pos)

            if split_pos <= 0:
                split_pos = self.max_segment_chars

            raw_segment = pending[: split_pos + 1]
            normalized = self._normalize_segment_text(raw_segment)
            if normalized:
                segments.append(normalized)
            pending = pending[split_pos + 1 :]
        return segments

    def _get_segment_text(self):
        full_text = "".join(self.tts_text_buff)
        current_text = full_text[self.processed_chars :]
        if not current_text:
            return None

        split_pos = -1
        min_chars = self.first_segment_min_chars if self.is_first_sentence else self.min_segment_chars
        first_segment_soft_min = max(2, min(self.first_segment_min_chars, 4))
        for punct in self.segment_punctuations:
            pos = current_text.find(punct)
            if (
                pos != -1
                and (
                    pos + 1 >= min_chars
                    or self.tts_stop_request
                    or (self.is_first_sentence and pos + 1 >= first_segment_soft_min)
                )
                and (split_pos == -1 or pos < split_pos)
            ):
                split_pos = pos

        if (
            self.is_first_sentence
            and len(current_text) >= self.first_segment_max_chars
            and (split_pos == -1 or split_pos + 1 > self.first_segment_max_chars)
        ):
            raw_segment = current_text[: self.first_segment_max_chars]
        elif split_pos != -1:
            raw_segment = current_text[: split_pos + 1]
        elif self.is_first_sentence and len(current_text) >= self.first_segment_max_chars:
            raw_segment = current_text[: self.first_segment_max_chars]
        elif len(current_text) >= self.max_segment_chars:
            raw_segment = current_text[: self.max_segment_chars]
        elif self.tts_stop_request:
            raw_segment = current_text
        else:
            return None

        self.processed_chars += len(raw_segment)
        was_first_segment = self.is_first_sentence
        self.is_first_sentence = False
        normalized = self._normalize_segment_text(raw_segment)
        if normalized:
            if was_first_segment:
                self._kokoro_segment_history = []
            if self.conn is not None and hasattr(self.conn, "mark_latency_stage"):
                self.conn.mark_latency_stage(
                    "tts_segment_ready",
                    segment_index=len(self._kokoro_segment_history),
                    chars=len(normalized),
                    first_segment=was_first_segment,
                    text=normalized,
                )
            self._kokoro_segment_history.append(normalized)
        return normalized

    def _process_remaining_text_stream(self, opus_handler=None):
        full_text = "".join(self.tts_text_buff)
        remaining_text = full_text[self.processed_chars :]
        if not remaining_text:
            return False

        handled = False
        for segment_text in self._split_kokoro_segments(remaining_text):
            self.to_tts_stream(segment_text, opus_handler=opus_handler)
            handled = True
        self.processed_chars = len(full_text)
        return handled

    async def text_to_speak(self, text, output_file):
        voice = self._normalize_voice(self.voice)
        if voice != self.voice:
            logger.bind(tag=TAG).info(f"Kokoro voice normalized: {self.voice} -> {voice}")
            self.voice = voice
        request_json = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": self.audio_file_type,
            "speed": self.speed,
            "stream_format": self.stream_format,
        }
        first_audio_timeout = max(0.1, self.first_audio_timeout_ms / 1000.0)
        timeout = (self.connect_timeout, min(self.read_timeout, first_audio_timeout))
        request_started_at = time.perf_counter()
        if self.conn is not None and hasattr(self.conn, "mark_latency_stage"):
            self.conn.mark_latency_stage(
                "tts_request_start",
                provider="KokoroHttp",
                voice=voice,
                model=self.model,
                first_audio_timeout_ms=self.first_audio_timeout_ms,
                read_timeout_ms=int(self.read_timeout * 1000),
                text_chars=len(text or ""),
            )

        try:
            with self._http_session_lock:
                response = self._http_session.post(
                    self.api_url,
                    json=request_json,
                    headers=self._build_headers(),
                    timeout=timeout,
                    stream=True,
                )
            response.raise_for_status()

            audio_bytes = bytearray()
            first_chunk_seen = False
            first_chunk_at = None

            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if not first_chunk_seen:
                    first_chunk_seen = True
                    first_chunk_at = time.perf_counter()
                    self._set_response_socket_timeout(response, self.read_timeout)
                    if self.conn is not None and hasattr(self.conn, "mark_latency_stage"):
                        self.conn.mark_latency_stage(
                            "tts_first_audio_ready",
                            provider="KokoroHttp",
                            first_audio_latency_ms=int(
                                (first_chunk_at - request_started_at) * 1000
                            ),
                        )
                audio_bytes.extend(chunk)

            if not first_chunk_seen:
                raise Exception("Kokoro TTS请求失败: No audio was received")

            if self.conn is not None and hasattr(self.conn, "mark_latency_stage"):
                self.conn.mark_latency_stage(
                    "tts_request_end",
                    provider="KokoroHttp",
                    duration_ms=int((time.perf_counter() - request_started_at) * 1000),
                )

            data = bytes(audio_bytes)
            if not data:
                raise Exception("Kokoro TTS请求失败: No audio was received")

            if output_file:
                with open(output_file, "wb") as audio_file:
                    audio_file.write(data)
            else:
                return data
        except Exception as e:
            error_msg = f"Kokoro TTS请求失败: {e}"
            if self.conn is not None and hasattr(self.conn, "mark_latency_stage"):
                self.conn.mark_latency_stage(
                    "tts_request_failed",
                    provider="KokoroHttp",
                    error=str(e),
                    failure_stage="waiting_first_audio",
                    elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
                )
            raise Exception(error_msg)

    async def close(self):
        await super().close()
        try:
            self._http_session.close()
        except Exception:
            logger.bind(tag=TAG).debug("Kokoro HTTP session close skipped")
