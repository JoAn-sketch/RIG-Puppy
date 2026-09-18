from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

VOICE_MAP = {
    "普通话女声": {"voice": "zf_xiaoxiao", "legacy_voice": "zh-CN-XiaoxiaoNeural", "desc": "Kokoro 原生默认女声"},
    "普通话男声": {"voice": "zm_yunyang", "legacy_voice": "zh-CN-YunyangNeural", "desc": "Kokoro 原生男声"},
    "可爱女声": {"voice": "zf_xiaoyi", "legacy_voice": "zh-CN-XiaoyiNeural", "desc": "Kokoro 原生轻快女声"},
    "阳刚男声": {"voice": "zm_yunjian", "legacy_voice": "zh-CN-YunjianNeural", "desc": "Kokoro 原生稳重男声"},
    "年轻男声": {"voice": "zm_yunxi", "legacy_voice": "zh-CN-YunxiNeural", "desc": "Kokoro 原生年轻男声"},
    "少年男声": {"voice": "zm_yunxia", "legacy_voice": "zh-CN-YunxiaNeural", "desc": "Kokoro 原生少年男声"},
    "东北话": {"voice": "zf_xiaobei", "legacy_voice": "zh-CN-liaoning-XiaobeiNeural", "desc": "Kokoro 原生东北音色"},
    "陕西话": {"voice": "zf_xiaoni", "legacy_voice": "zh-CN-shaanxi-XiaoniNeural", "desc": "Kokoro 原生陕西音色"},
    "粤语女声": {"voice": "zf_xiaoxiao", "legacy_voice": "zh-HK-HiuGaaiNeural", "desc": "Kokoro 原生女声"},
    "粤语甜美": {"voice": "zf_xiaoxiao", "legacy_voice": "zh-HK-HiuMaanNeural", "desc": "Kokoro 原生甜美女声"},
    "粤语男声": {"voice": "zm_yunyang", "legacy_voice": "zh-HK-WanLungNeural", "desc": "Kokoro 原生男声"},
}

VOICE_ALIASES = {
    "粤语": "粤语女声",
    "广东话": "粤语女声",
    "东北": "东北话",
    "辽宁话": "东北话",
    "陕西": "陕西话",
    "西安话": "陕西话",
    "默认": "普通话女声",
    "正常": "普通话女声",
    "普通话": "普通话女声",
    "女声": "普通话女声",
    "男声": "普通话男声",
}

available_voices = ", ".join(list(VOICE_MAP.keys()) + list(VOICE_ALIASES.keys()))

switch_voice_function_desc = {
    "type": "function",
    "function": {
        "name": "switch_voice",
        "description": f"切换语音音色或方言。Kokoro 模式下使用原生音色；可选: {available_voices}",
        "parameters": {
            "type": "object",
            "properties": {
                "voice_name": {
                    "type": "string",
                    "description": "要切换的音色名称，如：粤语、东北话、普通话女声、陕西话等"
                },
            },
            "required": ["voice_name"],
        },
    },
}


@register_function("switch_voice", switch_voice_function_desc, ToolType.NONE)
def switch_voice(conn: "ConnectionHandler", voice_name: str):
    """切换TTS音色/方言"""
    resolved = VOICE_ALIASES.get(voice_name, voice_name)

    if resolved not in VOICE_MAP:
        available = ", ".join(VOICE_MAP.keys())
        return ActionResponse(
            action=Action.RESPONSE,
            result="切换失败",
            response=f"没有这个音色哦，我支持：{available}"
        )

    voice_info = VOICE_MAP[resolved]
    use_kokoro_voice = hasattr(conn.tts, "_normalize_voice")
    new_voice = voice_info["voice"] if use_kokoro_voice else voice_info["legacy_voice"]
    desc = voice_info["desc"]

    if conn.tts and hasattr(conn.tts, "voice"):
        conn.tts.voice = new_voice
        logger.bind(tag=TAG).info(f"TTS音色已切换: {resolved} -> {new_voice} ({desc})")
        return ActionResponse(
            action=Action.RESPONSE,
            result="切换成功",
            response=f"好的，我已经切换到{resolved}了，你听听看"
        )
    else:
        logger.bind(tag=TAG).error("TTS实例不存在或不支持voice属性")
        return ActionResponse(
            action=Action.RESPONSE,
            result="切换失败",
            response="抱歉，当前语音引擎不支持切换音色"
        )
