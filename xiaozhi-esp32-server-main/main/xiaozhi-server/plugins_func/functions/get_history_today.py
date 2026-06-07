import re
import random
import requests
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

GET_HISTORY_TODAY_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_history_today",
        "description": (
            "当用户询问'历史上的今天''今天历史上发生了什么''这天有什么大事'时调用。"
            "返回历史上同一天发生的若干件大事，从中挑出 3 件讲给用户听。"
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


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return text.strip()


def fetch_history_today(month: int, day: int):
    url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{month:02d}.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    key_outer = f"{month:02d}"
    key_inner = f"{month:02d}{day:02d}"
    events = data.get(key_outer, {}).get(key_inner, [])
    return [
        {
            "year": e.get("year", ""),
            "title": _strip_html(e.get("title", "")),
        }
        for e in events
        if e.get("title")
    ]


@register_function(
    "get_history_today",
    GET_HISTORY_TODAY_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
def get_history_today(conn: "ConnectionHandler", lang: str = "zh_CN"):
    try:
        now = datetime.now()
        events = fetch_history_today(now.month, now.day)
        if not events:
            return ActionResponse(
                Action.REQLLM, "抱歉，今天没有查到历史事件，请稍后再试。", None
            )

        picks = random.sample(events, k=min(3, len(events)))
        lines = [f"{e['year']}年: {e['title']}" for e in picks]
        report = (
            f"根据下列数据，用{lang}回应用户'历史上的今天'查询，今天是 {now.month} 月 {now.day} 日：\n\n"
            + "\n".join(lines)
            + "\n\n(请把这 3 件事用自然口语连起来讲给用户听，每件事一句话简单交代清楚，"
            "整体控制在 4-6 句话，不要罗列年份编号、不要让用户追问。)"
        )
        return ActionResponse(Action.REQLLM, report, None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"历史上的今天获取失败: {e}")
        return ActionResponse(
            Action.REQLLM, "抱歉，查询历史事件时出错了，请稍后再试。", None
        )
