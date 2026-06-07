from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

VOICE_MAP = {
    "普通话女声": {"voice": "zh-CN-XiaoxiaoNeural", "desc": "晓晓"},
    "普通话男声": {"voice": "zh-CN-YunyangNeural", "desc": "云扬"},
    "可爱女声": {"voice": "zh-CN-XiaoyiNeural", "desc": "晓伊"},
    "阳刚男声": {"voice": "zh-CN-YunjianNeural", "desc": "云健"},
    "年轻男声": {"voice": "zh-CN-YunxiNeural", "desc": "云希"},
    "少年男声": {"voice": "zh-CN-YunxiaNeural", "desc": "云夏"},
    "东北话": {"voice": "zh-CN-liaoning-XiaobeiNeural", "desc": "辽宁小北"},
    "陕西话": {"voice": "zh-CN-shaanxi-XiaoniNeural", "desc": "陕西小妮"},
    "粤语女声": {"voice": "zh-HK-HiuGaaiNeural", "desc": "港女HiuGaai"},
    "粤语甜美": {"voice": "zh-HK-HiuMaanNeural", "desc": "港女HiuMaan"},
    "粤语男声": {"voice": "zh-HK-WanLungNeural", "desc": "港男WanLung"},
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
        "description": f"切换语音音色或方言。当用户想换声音、换方言、换口音时调用。可选: {available_voices}",
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
    new_voice = voice_info["voice"]
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

