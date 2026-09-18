import asyncio
import uuid
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from core.handle.sendAudioHandle import sendAudioMessage, send_tts_message
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.providers.tts.dto.dto import SentenceType

TAG = __name__


async def _play_tts_cue(conn: "ConnectionHandler", cue: str, text: str) -> None:
    conn._suppress_auto_boot_greeting = True
    if not text:
        conn.logger.bind(tag=TAG).warning(f"voice cue skipped: empty text, cue={cue}")
        return

    start_time = asyncio.get_running_loop().time()
    while asyncio.get_running_loop().time() - start_time < 5:
        if getattr(conn, "tts", None):
            break
        await asyncio.sleep(0.1)

    if not getattr(conn, "tts", None):
        conn.logger.bind(tag=TAG).warning(f"voice cue skipped: tts unavailable, cue={cue}")
        await send_tts_message(conn, "stop", None)
        conn.client_is_speaking = False
        return

    conn._apply_robot_profile_voice()
    conn.client_abort = False
    conn.client_is_speaking = True
    conn.sentence_id = str(uuid.uuid4().hex)
    conn.logger.bind(tag=TAG).info(f"playing voice cue: cue={cue}, text={text}")
    await send_tts_message(conn, "start")

    audio_datas = await asyncio.to_thread(conn.tts.to_tts, text)
    if not audio_datas:
        conn.logger.bind(tag=TAG).warning(f"voice cue skipped: tts returned no audio, cue={cue}")
        await send_tts_message(conn, "stop", None)
        conn.client_is_speaking = False
        return

    await sendAudioMessage(
        conn,
        SentenceType.FIRST,
        audio_datas,
        text,
        sentence_id=conn.sentence_id,
    )
    await sendAudioMessage(
        conn,
        SentenceType.LAST,
        [],
        None,
        sentence_id=conn.sentence_id,
    )


class SystemCueTextMessageHandler(TextMessageHandler):
    """Generate short system cues through server-side TTS."""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.SYSTEM_CUE

    async def handle(self, conn: "ConnectionHandler", msg_json: Dict[str, Any]) -> None:
        cue = str(msg_json.get("cue") or "system_cue").strip()
        text = str(msg_json.get("text") or "").strip()
        await _play_tts_cue(conn, cue, text)
