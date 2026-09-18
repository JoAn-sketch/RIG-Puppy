from __future__ import annotations

import re
from dataclasses import dataclass


GREETING_MARKERS = (
    "你好",
    "您好",
    "早上好",
    "上午好",
    "中午好",
    "下午好",
    "晚上好",
    "早安",
    "晚安",
    "hi",
    "hello",
    "hey",
)

OPEN_SHARE_MARKERS = (
    "我回来",
    "我回来了",
    "我来了",
    "我来啦",
    "今天",
    "刚刚",
    "刚才",
    "刚刚我",
    "今天我",
    "我今天",
    "天气",
    "好热",
    "好冷",
    "好玩",
    "真开心",
    "很开心",
    "挺开心",
)

CRITICAL_MARKERS = (
    "我害怕",
    "我怕",
    "我很怕",
    "我受伤",
    "我摔倒",
    "我摔了",
    "我跌倒",
    "我肚子疼",
    "我头疼",
    "我牙疼",
    "我不舒服",
    "我生病",
    "我发烧",
    "我感冒",
    "肚子疼",
    "头疼",
    "牙疼",
    "不舒服",
    "生病",
    "发烧",
    "感冒",
    "流血",
    "受伤",
    "摔倒",
    "摔了",
    "好害怕",
    "很害怕",
    "好难过",
    "很难过",
    "淋雨",
    "淋到雨",
    "被雨淋",
    "淋湿",
    "湿透",
    "快感冒",
)

FOCUSED_COMMAND_MARKERS = (
    "开始计时",
    "开始倒计时",
    "设个计时器",
    "设个闹钟",
    "打开",
    "关闭",
    "开灯",
    "关灯",
    "播放",
    "暂停",
    "停止",
    "下一首",
    "上一首",
    "放音乐",
    "播音乐",
    "讲故事",
    "说故事",
    "唱歌",
)

QUESTION_MARKERS = (
    "为什么",
    "怎么",
    "是什么",
    "什么意思",
    "是不是",
    "能不能",
    "会不会",
    "告诉我",
    "讲个",
    "说个",
    "来一个",
)

LIGHT_SHARE_STARTERS = (
    "我",
    "今天",
    "刚刚",
    "刚才",
    "天气",
    "外面",
    "学校",
)


@dataclass(frozen=True)
class ConversationOpenness:
    level: int
    reason: str


def _normalize(text: str | None) -> str:
    value = str(text or "").strip().lower()
    return re.sub(r"\s+", "", value)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _is_short_greeting(text: str) -> bool:
    if not _contains_any(text, GREETING_MARKERS):
        return False
    stripped = text
    for marker in GREETING_MARKERS:
        stripped = stripped.replace(marker, "")
    stripped = re.sub(r"(呀|啊|呢|啦|哈|哇|哦|喽|呦|哟|嘛|～|~|!|！|,|，|。|\.|乐乐|可可)+", "", stripped)
    return len(stripped) <= 4


def _looks_like_question_or_request(text: str) -> bool:
    return text.endswith(("?", "？")) or _contains_any(text, QUESTION_MARKERS)


def evaluate_conversation_openness(text: str | None) -> ConversationOpenness:
    normalized = _normalize(text)
    if not normalized:
        return ConversationOpenness(level=3, reason="empty_default")

    if _contains_any(normalized, CRITICAL_MARKERS):
        return ConversationOpenness(level=1, reason="critical_need")

    if _contains_any(normalized, FOCUSED_COMMAND_MARKERS) and not _contains_any(normalized, GREETING_MARKERS):
        return ConversationOpenness(level=2, reason="focused_command")

    if _is_short_greeting(normalized):
        return ConversationOpenness(level=5, reason="social_greeting")

    if _looks_like_question_or_request(normalized):
        return ConversationOpenness(level=3, reason="question_or_request")

    if _contains_any(normalized, OPEN_SHARE_MARKERS):
        return ConversationOpenness(level=4, reason="light_sharing")

    if any(normalized.startswith(starter) for starter in LIGHT_SHARE_STARTERS):
        return ConversationOpenness(level=4, reason="open_sharing")

    return ConversationOpenness(level=3, reason="neutral_default")


def daily_greeting_mode(level: int | None) -> str:
    normalized = max(1, min(5, int(level or 3)))
    if normalized >= 4:
        return "immediate"
    if normalized == 3:
        return "deferred"
    return "skip"


def proactive_mode(level: int | None) -> str:
    normalized = max(1, min(5, int(level or 3)))
    return {
        5: "full",
        4: "moderate",
        3: "limited",
        2: "focused",
        1: "critical_only",
    }.get(normalized, "limited")
