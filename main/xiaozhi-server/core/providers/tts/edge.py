import os
import uuid
import edge_tts
from datetime import datetime
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    VOICE_ALIASES = {
        "zf_xiaoxiao": "zh-CN-XiaoxiaoNeural",
        "zm_yunyang": "zh-CN-YunyangNeural",
        "zf_xiaoyi": "zh-CN-XiaoyiNeural",
        "zm_yunjian": "zh-CN-YunjianNeural",
        "zm_yunxi": "zh-CN-YunxiNeural",
        "zm_yunxia": "zh-CN-YunxiaNeural",
        "zf_xiaobei": "zh-CN-liaoning-XiaobeiNeural",
        "zf_xiaoni": "zh-CN-shaanxi-XiaoniNeural",
        "mandarin_female": "zh-CN-XiaoxiaoNeural",
        "mandarin_male": "zh-CN-YunyangNeural",
        "cute_female": "zh-CN-XiaoyiNeural",
        "strong_male": "zh-CN-YunjianNeural",
        "young_male": "zh-CN-YunxiNeural",
        "boy_male": "zh-CN-YunxiaNeural",
        "liaoning_female": "zh-CN-liaoning-XiaobeiNeural",
        "shaanxi_female": "zh-CN-shaanxi-XiaoniNeural",
    }

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        if config.get("private_voice"):
            configured_voice = config.get("private_voice")
        else:
            configured_voice = config.get("voice")
        self.voice = self._normalize_voice(configured_voice)
        self.audio_file_type = config.get("format", "mp3")

    def _normalize_voice(self, voice):
        raw_voice = str(voice or "").strip()
        return self.VOICE_ALIASES.get(raw_voice, raw_voice or "zh-CN-XiaoxiaoNeural")

    def generate_filename(self, extension=".mp3"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        try:
            communicate = edge_tts.Communicate(text, voice=self.voice)
            if output_file:
                # 确保目录存在并创建空文件
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, "wb") as f:
                    pass

                # 流式写入音频数据
                with open(output_file, "ab") as f:  # 改为追加模式避免覆盖
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":  # 只处理音频数据块
                            f.write(chunk["data"])
            else:
                # 返回音频二进制数据
                audio_bytes = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes += chunk["data"]
                return audio_bytes
        except Exception as e:
            error_msg = f"Edge TTS请求失败: {e}"
            raise Exception(error_msg)  # 抛出异常，让调用方捕获
