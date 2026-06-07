import requests
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

GET_JOKE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_joke",
        "description": (
            "当用户要求'讲个笑话''说个段子''逗我笑一下'时调用。"
            "返回一个适合朗读的轻松段子。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lang": {
                    "type": "string",
                    "description": "回复语言code，默认 zh_CN",
                },
            },
            "required": ["lang"],
        },
    },
}

HITOKOTO_ENDPOINTS = [
    "https://international.v1.hitokoto.cn/?c=k",
    "https://v1.hitokoto.cn/?c=k",
]


def fetch_one_joke():
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in HITOKOTO_ENDPOINTS:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            r.raise_for_status()
            data = r.json()
            text = (data.get("hitokoto") or "").strip()
            if text:
                return text
        except Exception as e:
            logger.bind(tag=TAG).warning(f"hitokoto {url} 失败: {e}")
    return ""


@register_function(
    "get_joke",
    GET_JOKE_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
def get_joke(conn: "ConnectionHandler", lang: str = "zh_CN"):
    try:
        joke = fetch_one_joke()
        if not joke:
            return ActionResponse(
                Action.REQLLM, "抱歉，笑话库暂时连不上，待会儿再试。", None
            )

        report = (
            f"根据下列素材，用{lang}回应用户'讲笑话'的请求：\n\n"
            f"素材: {joke}\n\n"
            "(请把这条素材改写成一句口语化、有节奏感的小段子讲给用户听，"
            "可以加点语气词让它更像真人在讲，不要解释、不要追问。)"
        )
        return ActionResponse(Action.REQLLM, report, None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"获取笑话失败: {e}")
        return ActionResponse(
            Action.REQLLM, "抱歉，获取笑话时出错了，待会儿再试。", None
        )
