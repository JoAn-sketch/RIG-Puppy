import uuid
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from core.handle.sendAudioHandle import send_tts_message
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO

TAG = __name__


class AdoptionGreetingMessageHandler(TextMessageHandler):
    """Play the one-time first adoption greeting without involving LLM or memory."""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.ADOPTION_GREETING

    async def handle(self, conn: "ConnectionHandler", msg_json: Dict[str, Any]) -> None:
        text = str(msg_json.get("text") or "").strip()
        user_name = str(msg_json.get("user_name") or "").strip()
        robot_name = str(msg_json.get("robot_name") or "").strip()
        if not text or not user_name or not robot_name:
            conn.logger.bind(tag=TAG).warning("首次领养欢迎语缺少 text/user_name/robot_name，跳过")
            return

        conn.logger.bind(tag=TAG).info(
            f"播放首次领养欢迎语: user_name={user_name}, robot_name={robot_name}"
        )
        conn._apply_robot_profile_voice()
        conn.client_abort = False
        conn.client_is_speaking = True
        conn.sentence_id = str(uuid.uuid4().hex)
        conn.tts.store_tts_text(conn.sentence_id, text)

        await send_tts_message(conn, "start")
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.FIRST,
                content_type=ContentType.ACTION,
            )
        )
        conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=text)
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.LAST,
                content_type=ContentType.ACTION,
            )
        )
