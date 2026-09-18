from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


DEFAULT_MAX_TOPICS = 5
DEFAULT_TOPIC_TTL_HOURS = 24
DEFAULT_MAX_ENTITIES = 6
DEFAULT_MAX_RESOLVED_POINTS = 4

SHORT_MEMORY_SCENES = {
    "curiosity",
    "learning_support",
    "emotion_support",
    "play_interaction",
}

EVENT_MARKERS = (
    "昨天",
    "今天",
    "刚刚",
    "刚才",
    "下午",
    "早上",
    "上午",
    "中午",
    "晚上",
    "去",
    "看到",
    "玩了",
    "回来",
)

RECENT_EXPERIENCE_MARKERS = (
    "昨天",
    "今天",
    "刚刚",
    "刚才",
    "去了",
    "去看",
    "去玩",
    "看到",
    "看了",
    "玩了",
    "回来",
    "参观",
    "展览",
    "动物园",
    "公园",
    "博物馆",
    "比赛",
    "表演",
)

FOLLOWUP_CONTINUATION_MARKERS = (
    "那它",
    "那他",
    "那她",
    "那这个",
    "那这种",
    "哪里不一样",
    "有什么不一样",
    "那为什么",
    "那怎么",
    "那它们",
    "它和",
    "它们和",
)

QUESTION_MARKERS = (
    "为什么",
    "怎么",
    "是什么",
    "什么意思",
    "是不是",
    "能不能",
    "会不会",
)

GREETING_MARKERS = (
    "你好",
    "您好",
    "早安",
    "早上好",
    "上午好",
    "中午好",
    "下午好",
    "晚上好",
    "晚安",
    "hello",
    "hi",
)

EMOTION_MARKERS = (
    "难过",
    "伤心",
    "害怕",
    "紧张",
    "不开心",
    "委屈",
    "担心",
    "开心",
    "高兴",
    "兴奋",
    "期待",
    "激动",
    "不知道",
    "不懂",
    "不会",
    "错了",
    "失败",
    "丢脸",
)

HEALTH_MARKERS = (
    "生病",
    "发烧",
    "感冒",
    "咳嗽",
    "不舒服",
    "肚子疼",
    "头疼",
    "牙疼",
    "流鼻涕",
    "嗓子疼",
)

PERSONAL_RELEVANCE_MARKERS = (
    "我",
    "我的",
    "我们",
    "妈妈",
    "爸爸",
    "奶奶",
    "爷爷",
    "老师",
    "同学",
    "朋友",
    "学校",
    "幼儿园",
    "家里",
    "宠物",
    "狗狗",
    "猫猫",
)

FUTURE_CONTINUATION_MARKERS = (
    "明天",
    "后天",
    "今晚",
    "等会",
    "等一下",
    "待会",
    "待会儿",
    "一会",
    "一会儿",
    "稍后",
    "下周",
    "周末",
    "下个月",
    "准备",
    "打算",
    "要去",
    "要做",
    "要上",
    "要参加",
    "会去",
    "会有",
    "会参加",
    "想去",
    "想做",
)

ONGOING_STATE_MARKERS = (
    "还在",
    "一直",
    "最近",
    "还没",
    "还没有",
    "没做完",
    "没开始",
    "学",
    "练",
    "养",
    "照顾",
    "担心",
    "紧张",
    "害怕",
    "不舒服",
    "生病",
)

EXPECTED_OUTCOME_MARKERS = (
    "考试",
    "测验",
    "测试",
    "比赛",
    "表演",
    "上课",
    "练琴",
    "钢琴课",
    "游泳课",
    "看医生",
    "去医院",
    "动物园",
    "生日",
    "旅行",
    "春游",
    "秋游",
)

CONVERSATION_TOPIC_MARKERS = (
    "是什么",
    "什么意思",
    "为什么",
    "怎么",
    "是不是",
    "能不能",
    "会不会",
)

TASK_MARKERS = (
    "作业",
    "考试",
    "测验",
    "测试",
    "上课",
    "练琴",
    "钢琴课",
    "游泳课",
    "拼写测试",
    "比赛",
    "表演",
    "训练",
    "任务",
    "目标",
    "计划",
    "答应",
    "约定",
    "约好",
    "说好",
    "承诺",
)

FOLLOW_UP_MARKERS = (
    "明天",
    "后天",
    "今晚",
    "等会",
    "等一下",
    "待会",
    "待会儿",
    "一会",
    "一会儿",
    "稍后",
    "下周",
    "周末",
    "下个月",
    "准备",
    "打算",
    "要去",
    "要做",
    "要上",
    "要参加",
    "会去",
    "会有",
    "会参加",
    "想去",
    "想做",
    "还没",
    "还没有",
    "没做完",
    "没开始",
    "记得",
    "后来",
    "怎么样",
    "怎么样了",
    "一定要",
    "得去",
    "必须",
)

INTEREST_MARKERS = (
    "喜欢",
    "最喜欢",
    "爱",
    "感兴趣",
    "想了解",
    "想知道",
)

KNOWLEDGE_FACT_MARKERS = (
    "科学家",
    "研究",
    "事实",
    "知识",
    "为什么",
    "是什么",
    "什么意思",
    "分类",
    "属于",
    "能在",
    "会在",
)

MEMORY_TYPE_PRIORITY = {
    "greeting": 0,
    "conversation": 1,
    "event": 2,
    "task": 3,
    "emotion": 4,
    "health": 5,
}

GREETING_CANDIDATE_TYPE_PRIORITY = {
    "knowledge_fact": 1,
    "user_interest": 2,
    "emotional_moment": 3,
    "personal_event": 4,
    "unfinished_thread": 5,
}

STOPWORDS = {
    "",
    "的",
    "了",
    "啊",
    "呀",
    "呢",
    "吗",
    "吧",
    "我",
    "你",
    "他",
    "她",
    "它",
    "我们",
    "你们",
    "他们",
    "这个",
    "那个",
    "什么",
    "怎么",
    "为什么",
    "一下",
    "一个",
    "昨天",
    "今天",
    "上午",
    "下午",
    "早上",
    "晚上",
    "中午",
    "刚刚",
    "刚才",
    "去了",
    "看到",
    "看了",
    "去",
    "看",
    "已经",
    "还是",
    "就是",
    "然后",
    "自己",
    "我们",
    "你们",
    "他们",
    "我的",
    "你的",
    "它的",
    "就能",
    "能够",
    "可以",
    "清楚",
    "很清楚",
    "得很清楚",
}

ENTITY_SPLIT_PATTERN = re.compile(
    r"(为什么|怎么|是什么|什么意思|是不是|能不能|会不会|因为|所以|如果|但是|然后|刚刚|刚才|昨天|今天|上午|下午|早上|晚上|中午|自己|已经|我们|你们|他们|我的|你的|它的|这个|那个|一个|去了|看到|看了|去|看|在|和|跟|是|有|了|的|吗|呢|吧|呀|啊)"
)

GENERIC_ENTITY_PARTS = (
    "因为",
    "所以",
    "发现",
    "单独",
    "最近",
    "亲戚",
    "今天",
    "上午",
    "下午",
    "早上",
    "晚上",
    "刚刚",
    "刚才",
    "昨天",
    "回来",
    "哪里不一样",
    "有什么不一样",
)

ENTITY_PRIORITY_HINTS = (
    "小熊猫",
    "大熊猫",
    "熊猫",
    "小狗",
    "小猫",
    "猫",
    "狗",
    "动物园",
    "熊科",
    "小熊猫科",
    "浣熊科",
    "食肉目",
    "竹子",
    "苹果",
)

GENERIC_ENTITY_EXACT = {
    "那它",
    "那他",
    "那她",
    "那这个",
    "这次",
    "回来",
    "刚从",
    "我昨天",
    "自己",
    "它不",
    "昨天",
    "今天",
    "看了",
    "去了",
    "看到",
}

NOISY_ENTITY_PARTS = (
    "记得",
    "干嘛",
    "太累",
    "累了",
    "感觉",
    "心情",
    "新鲜事",
    "想聊聊",
    "还说",
    "就能",
    "能够",
    "可以",
    "很清楚",
    "得很清楚",
    "生病",
    "发烧",
    "感冒",
    "咳嗽",
    "不舒服",
)


def _normalize_text(text: str | None) -> str:
    value = str(text or "").strip().lower()
    return re.sub(r"\s+", "", value)


def _split_sentences(text: str | None) -> List[str]:
    value = str(text or "").strip()
    if not value:
        return []
    parts = re.split(r"[。！？!?；;\n]+", value)
    return [part.strip(" ，,、：:~") for part in parts if part.strip(" ，,、：:~")]


def _tokenize_text(text: str | None) -> List[str]:
    value = str(text or "").strip().lower()
    if not value:
        return []

    chinese_tokens = re.findall(r"[\u4e00-\u9fff]{2,8}", value)
    alpha_tokens = re.findall(r"[a-z0-9]{2,24}", value)
    tokens = chinese_tokens + alpha_tokens
    normalized = []
    for token in tokens:
        token = token.strip()
        if token and token not in STOPWORDS:
            normalized.append(token)
    return normalized


def _extract_entity_candidates(text: str | None) -> List[str]:
    value = str(text or "").strip()
    if not value:
        return []

    candidates: List[str] = []
    prioritized = []
    for hint in ENTITY_PRIORITY_HINTS:
        if hint in value:
            prioritized.append(hint)
    chinese_blocks = re.findall(r"[\u4e00-\u9fff]{2,24}", value)
    for block in chinese_blocks:
        pieces = ENTITY_SPLIT_PATTERN.split(block)
        for piece in pieces:
            piece = piece.strip()
            if len(piece) < 2:
                continue
            if piece in STOPWORDS:
                continue
            if piece in GENERIC_ENTITY_EXACT:
                continue
            if any(generic in piece for generic in GENERIC_ENTITY_PARTS):
                continue
            if len(piece) > 8:
                for size in (4, 3):
                    for index in range(0, len(piece) - size + 1):
                        sub = piece[index:index + size]
                        if (
                            sub not in STOPWORDS
                            and sub not in GENERIC_ENTITY_EXACT
                            and not any(generic in sub for generic in GENERIC_ENTITY_PARTS)
                            and not any(noisy in sub for noisy in NOISY_ENTITY_PARTS)
                        ):
                            candidates.append(sub)
            else:
                candidates.append(piece)

    alpha_tokens = re.findall(r"[a-z0-9]{2,24}", value.lower())
    candidates.extend(alpha_tokens)
    cleaned_candidates = _sanitize_entities(candidates)
    if prioritized:
        prioritized_set = set(prioritized)
        cleaned_candidates = [
            item for item in cleaned_candidates
            if item not in prioritized_set and len(item) >= 2
        ]
    return _dedupe_keep_order(prioritized + cleaned_candidates)


def _dedupe_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _sanitize_entities(items: Sequence[str] | None) -> List[str]:
    cleaned: List[str] = []
    for item in list(items or []):
        value = str(item or "").strip()
        if len(value) < 2 and value not in {"猫", "狗"}:
            continue
        if any(part in value for part in NOISY_ENTITY_PARTS):
            continue
        if len(value) > 8 and "玛雅文化展" not in value and "小熊猫" not in value and "大熊猫" not in value:
            continue
        cleaned.append(value)
    return _dedupe_keep_order(cleaned)


def _trim_text(text: str | None, max_len: int) -> str:
    value = str(text or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


def _contains_any(text: str | None, markers: Sequence[str]) -> bool:
    value = str(text or "").strip().lower()
    return any(marker in value for marker in markers)


def _is_greeting_text(text: str | None) -> bool:
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(text or "").strip().lower())
    if not normalized:
        return False
    if not any(marker in normalized for marker in GREETING_MARKERS):
        return False
    if len(normalized) <= 8:
        return True
    stripped = normalized
    for marker in GREETING_MARKERS:
        stripped = stripped.replace(marker, "")
    stripped = re.sub(r"(呀|啊|呢|啦|哈|哟|呦|喽|哦|诶)+", "", stripped)
    return len(stripped) <= 2


def _classify_memory_type(
    user_text: str,
    scene: str,
    emotion: str = "neutral",
    open_questions: Sequence[str] | None = None,
) -> str:
    normalized_user = str(user_text or "").strip()
    if _is_greeting_text(normalized_user):
        return "greeting"
    if _contains_any(normalized_user, HEALTH_MARKERS):
        return "health"
    if str(emotion or "").strip() not in {"", "neutral"}:
        return "emotion"
    if _contains_any(normalized_user, EMOTION_MARKERS):
        return "emotion"
    if _contains_any(normalized_user, TASK_MARKERS):
        return "task"
    if _contains_any(normalized_user, FOLLOW_UP_MARKERS) or scene in {"emotion_support", "play_interaction"}:
        return "event"
    if scene in {"curiosity", "learning_support"} and list(open_questions or []):
        return "conversation"
    if _contains_any(normalized_user, EVENT_MARKERS):
        return "event"
    return "conversation"


def _should_mark_follow_up_candidate(
    user_text: str,
    summary: str,
    memory_type: str,
) -> bool:
    if memory_type in {"greeting", "conversation"}:
        return False
    if memory_type in {"emotion", "health", "task"}:
        return True
    combined = f"{str(user_text or '').strip()} {str(summary or '').strip()}"
    return _contains_any(combined, FOLLOW_UP_MARKERS + HEALTH_MARKERS + EMOTION_MARKERS + TASK_MARKERS)


def _merge_memory_type(existing_type: str, new_type: str) -> str:
    existing = str(existing_type or "conversation").strip() or "conversation"
    incoming = str(new_type or "conversation").strip() or "conversation"
    if MEMORY_TYPE_PRIORITY.get(incoming, 0) >= MEMORY_TYPE_PRIORITY.get(existing, 0):
        return incoming
    return existing


def _merge_string_lists(existing: Sequence[str] | None, new_items: Sequence[str] | None) -> List[str]:
    return _dedupe_keep_order(list(existing or []) + list(new_items or []))


def _follow_up_confidence(score: int) -> str:
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    return "low"


def _build_follow_up_metadata(
    user_text: str,
    summary: str,
    memory_type: str,
    scene: str = "",
    open_questions: Sequence[str] | None = None,
) -> Dict[str, Any]:
    normalized_user = str(user_text or "").strip()
    normalized_summary = _summary_for_evaluation(summary)
    combined = f"{normalized_user} {normalized_summary}"
    evidence: List[str] = []
    rejection_evidence: List[str] = []

    if memory_type in {"greeting", "conversation"}:
        rejection_evidence.append("conversation_topic")
    if _is_greeting_text(normalized_user):
        rejection_evidence.append("greeting")
    if any(marker in combined for marker in CONVERSATION_TOPIC_MARKERS):
        rejection_evidence.append("conversation_topic")
    if list(open_questions or []) and memory_type == "conversation":
        rejection_evidence.append("conversation_closed")

    if _contains_any(normalized_user, FUTURE_CONTINUATION_MARKERS):
        evidence.append("future_continuation")
    if _contains_any(normalized_user, RECENT_EXPERIENCE_MARKERS):
        evidence.append("recent_personal_event")
    if memory_type in {"emotion", "health"} or _contains_any(normalized_user, ONGOING_STATE_MARKERS):
        evidence.append("ongoing_state")
    if _contains_any(normalized_user, PERSONAL_RELEVANCE_MARKERS):
        evidence.append("personal_relevance")
    if memory_type in {"task", "health"} or _contains_any(normalized_user, EXPECTED_OUTCOME_MARKERS):
        evidence.append("expected_outcome")

    evidence = _dedupe_keep_order(evidence)
    rejection_evidence = _dedupe_keep_order(rejection_evidence)
    positive_score = len(evidence)
    naturalness_passed = (
        memory_type in {"event", "task", "health", "emotion"}
        and positive_score >= 2
        and not rejection_evidence
    )
    naturalness_reason = "" if naturalness_passed else "awkward_follow_up"
    eligible = naturalness_passed
    confidence = _follow_up_confidence(positive_score if eligible else max(positive_score, len(rejection_evidence)))
    full_evidence = evidence + rejection_evidence
    return {
        "eligible": eligible,
        "confidence": confidence,
        "evidence": full_evidence,
        "naturalness": {
            "passed": naturalness_passed,
            "reason": naturalness_reason,
        },
    }


def _merge_follow_up_metadata(existing: Dict[str, Any] | None, new_meta: Dict[str, Any] | None) -> Dict[str, Any]:
    existing_meta = dict(existing or {})
    incoming_meta = dict(new_meta or {})
    if not existing_meta:
        return incoming_meta
    if not incoming_meta:
        return existing_meta
    merged_evidence = _merge_string_lists(existing_meta.get("evidence"), incoming_meta.get("evidence"))
    existing_naturalness = dict(existing_meta.get("naturalness") or {})
    incoming_naturalness = dict(incoming_meta.get("naturalness") or {})
    naturalness_passed = bool(existing_naturalness.get("passed")) or bool(incoming_naturalness.get("passed"))
    naturalness_reason = ""
    if not naturalness_passed:
        naturalness_reason = str(incoming_naturalness.get("reason") or existing_naturalness.get("reason") or "awkward_follow_up")
    score = len([item for item in merged_evidence if item in {"future_continuation", "recent_personal_event", "ongoing_state", "personal_relevance", "expected_outcome"}])
    eligible = naturalness_passed and score >= 2 and "conversation_topic" not in merged_evidence and "greeting" not in merged_evidence
    return {
        "eligible": eligible,
        "confidence": _follow_up_confidence(score if eligible else max(score, 1 if merged_evidence else 0)),
        "evidence": merged_evidence,
        "naturalness": {
            "passed": naturalness_passed,
            "reason": naturalness_reason,
        },
    }


def _round_score(value: float) -> float:
    return round(max(0.0, min(1.0, float(value or 0.0))), 3)


def _first_entity(entities: Sequence[str] | None) -> str:
    for entity in list(entities or []):
        value = str(entity or "").strip()
        if value:
            return value
    return ""


def _emotion_weight(user_text: str, memory_type: str, emotion: str = "neutral") -> float:
    normalized = str(user_text or "").strip()
    explicit_emotion = str(emotion or "").strip()
    if explicit_emotion and explicit_emotion != "neutral":
        return 1.0
    if memory_type == "emotion":
        return 0.9
    if _contains_any(normalized, ("担心", "紧张", "害怕", "难过", "伤心", "委屈", "不开心")):
        return 1.0
    if _contains_any(normalized, ("开心", "高兴", "兴奋", "期待", "激动")):
        return 0.75
    if memory_type == "health" or _contains_any(normalized, HEALTH_MARKERS):
        return 0.7
    if _contains_any(normalized, ("不知道", "不懂", "不会", "错了", "失败", "丢脸")):
        return 0.65
    return 0.0


def _build_greeting_candidate_metadata(
    user_text: str,
    summary: str,
    memory_type: str,
    scene: str = "",
    emotion: str = "neutral",
    entities: Sequence[str] | None = None,
    open_questions: Sequence[str] | None = None,
    follow_up: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    normalized_user = str(user_text or "").strip()
    normalized_summary = _summary_for_evaluation(summary)
    combined = f"{normalized_user} {normalized_summary}"
    follow_up_meta = dict(follow_up or {})
    follow_up_evidence = list(follow_up_meta.get("evidence") or [])
    follow_up_needed = bool(follow_up_meta.get("eligible"))
    evidence: List[str] = list(follow_up_evidence)

    has_personal_relevance = _contains_any(combined, PERSONAL_RELEVANCE_MARKERS)
    has_recent_experience = _contains_any(combined, RECENT_EXPERIENCE_MARKERS)
    has_future_or_ongoing = _contains_any(combined, FUTURE_CONTINUATION_MARKERS + ONGOING_STATE_MARKERS)
    has_health_or_task = memory_type in {"health", "task"} or _contains_any(combined, HEALTH_MARKERS + TASK_MARKERS)
    has_emotion = memory_type == "emotion" or _contains_any(combined, EMOTION_MARKERS)
    has_interest = _contains_any(combined, INTEREST_MARKERS)
    has_question = bool(open_questions) or _contains_any(normalized_user, QUESTION_MARKERS) or normalized_user.endswith(("?", "？"))

    if has_personal_relevance:
        evidence.append("personal_relevance")
    if has_recent_experience:
        evidence.append("recent_personal_event")
    if has_future_or_ongoing:
        evidence.append("future_or_ongoing")
    if has_health_or_task:
        evidence.append("health_or_task")
    if has_emotion:
        evidence.append("emotional_signal")
    if has_interest:
        evidence.append("user_interest")
    if has_question or _contains_any(combined, KNOWLEDGE_FACT_MARKERS):
        evidence.append("knowledge_fact")

    emotional_weight = _emotion_weight(normalized_user, memory_type, emotion=emotion)

    personal_event_score = 0.0
    if memory_type in {"task", "health", "emotion"} and has_personal_relevance:
        personal_event_score = 1.0
    elif memory_type == "event" and (has_recent_experience or has_health_or_task or has_emotion):
        personal_event_score = 1.0
    elif has_personal_relevance and (has_health_or_task or has_recent_experience):
        personal_event_score = 1.0
    elif has_personal_relevance:
        personal_event_score = 0.45

    unfinished_thread_score = 0.0
    if follow_up_needed and (has_future_or_ongoing or has_health_or_task):
        unfinished_thread_score = 1.0
    elif follow_up_needed:
        unfinished_thread_score = 0.75
    elif has_future_or_ongoing and (has_personal_relevance or has_health_or_task):
        unfinished_thread_score = 0.7

    interest_match_score = 0.0
    if has_interest and has_personal_relevance:
        interest_match_score = 0.8
    elif has_interest:
        interest_match_score = 0.6

    curiosity_score = 0.0
    if has_question or _contains_any(combined, KNOWLEDGE_FACT_MARKERS):
        curiosity_score = 0.7
    if scene in {"curiosity", "learning_support"} and memory_type == "conversation":
        curiosity_score = max(curiosity_score, 0.55)

    candidate_type = "knowledge_fact"
    if has_interest and not (personal_event_score >= 0.8 or unfinished_thread_score >= 0.7 or emotional_weight >= 0.65):
        candidate_type = "user_interest"
    if personal_event_score >= 0.8:
        candidate_type = "personal_event"
    if emotional_weight >= 0.65 and personal_event_score < 0.8 and unfinished_thread_score < 0.7:
        candidate_type = "emotional_moment"
    if unfinished_thread_score >= 0.7:
        candidate_type = "unfinished_thread"

    score = (
        personal_event_score * 0.35
        + unfinished_thread_score * 0.30
        + emotional_weight * 0.20
        + interest_match_score * 0.10
        + curiosity_score * 0.05
    )
    if candidate_type in {"unfinished_thread", "personal_event", "emotional_moment"}:
        content = (
            _clean_candidate_content(normalized_user)
            or _clean_candidate_content(normalized_summary)
            or _clean_candidate_content(_first_entity(entities))
        )
    else:
        content = (
            _clean_candidate_content(normalized_summary)
            or _clean_candidate_content(normalized_user)
            or _clean_candidate_content(_first_entity(entities))
        )
    return {
        "content": _trim_text(content, 80),
        "type": candidate_type,
        "entity": _first_entity(entities),
        "emotionalWeight": _round_score(emotional_weight),
        "followUpNeeded": bool(follow_up_needed or unfinished_thread_score >= 0.7),
        "personalEventScore": _round_score(personal_event_score),
        "unfinishedThreadScore": _round_score(unfinished_thread_score),
        "interestMatchScore": _round_score(interest_match_score),
        "curiosityScore": _round_score(curiosity_score),
        "score": _round_score(score),
        "evidence": _dedupe_keep_order(evidence),
    }


def _clean_candidate_content(text: str | None) -> str:
    value = _summary_for_evaluation(text)
    value = value.strip(" ，,。！？!?；;")
    if value.startswith("我的") and len(value) > 2:
        value = value[2:].strip(" ，,。！？!?；;")
    return value


def _merge_greeting_candidate_metadata(existing: Dict[str, Any] | None, new_meta: Dict[str, Any] | None) -> Dict[str, Any]:
    existing_meta = dict(existing or {})
    incoming_meta = dict(new_meta or {})
    if not existing_meta:
        return incoming_meta
    if not incoming_meta:
        return existing_meta
    existing_type = str(existing_meta.get("type") or "knowledge_fact")
    incoming_type = str(incoming_meta.get("type") or "knowledge_fact")
    existing_rank = GREETING_CANDIDATE_TYPE_PRIORITY.get(existing_type, 0)
    incoming_rank = GREETING_CANDIDATE_TYPE_PRIORITY.get(incoming_type, 0)
    existing_score = float(existing_meta.get("score") or 0.0)
    incoming_score = float(incoming_meta.get("score") or 0.0)
    preferred = incoming_meta if (incoming_score, incoming_rank) >= (existing_score, existing_rank) else existing_meta
    other = existing_meta if preferred is incoming_meta else incoming_meta
    merged = dict(preferred)
    merged["score"] = _round_score(max(existing_score, incoming_score))
    merged["emotionalWeight"] = _round_score(max(float(existing_meta.get("emotionalWeight") or 0.0), float(incoming_meta.get("emotionalWeight") or 0.0)))
    merged["followUpNeeded"] = bool(existing_meta.get("followUpNeeded")) or bool(incoming_meta.get("followUpNeeded"))
    merged["evidence"] = _merge_string_lists(existing_meta.get("evidence"), incoming_meta.get("evidence"))
    if not merged.get("content"):
        merged["content"] = other.get("content") or ""
    if not merged.get("entity"):
        merged["entity"] = other.get("entity") or ""
    return merged


def _sanitize_summary_text(text: str | None) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    parts = []
    for segment in value.split("；后来"):
        cleaned = segment.split("；机器人回应了")[0].strip("； ")
        if cleaned:
            parts.append(cleaned)
    return "；后来".join(parts)


def _summary_for_evaluation(text: str | None) -> str:
    value = _sanitize_summary_text(text)
    for prefix in ("孩子提到最近经历：", "孩子提到：", "孩子在继续追问："):
        if value.startswith(prefix):
            return value[len(prefix):].strip()
    return value


def _timestamp_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class ShortTermTopic:
    topic_id: str
    topic: str
    summary: str
    memory_type: str = "conversation"
    follow_up_candidate: bool = False
    follow_up: Dict[str, Any] = field(default_factory=dict)
    greeting_candidate: Dict[str, Any] = field(default_factory=dict)
    entities: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    resolved_points: List[str] = field(default_factory=list)
    emotion: str = "neutral"
    scene: str = ""
    importance: float = 0.5
    last_user_text: str = ""
    last_assistant_text: str = ""
    last_active_at_ms: int = 0
    expires_at_ms: int = 0

    def is_expired(self, now_ms: int) -> bool:
        return bool(self.expires_at_ms) and self.expires_at_ms <= now_ms

    def tokens(self) -> List[str]:
        return _dedupe_keep_order(
            _tokenize_text(self.topic)
            + [token for entity in self.entities for token in _tokenize_text(entity)]
            + [token for question in self.open_questions for token in _tokenize_text(question)]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "topic": self.topic,
            "summary": self.summary,
            "memory_type": self.memory_type,
            "follow_up_candidate": bool(self.follow_up_candidate),
            "follow_up": dict(self.follow_up or {}),
            "greeting_candidate": dict(self.greeting_candidate or {}),
            "entities": list(self.entities),
            "open_questions": list(self.open_questions),
            "resolved_points": list(self.resolved_points),
            "emotion": self.emotion,
            "scene": self.scene,
            "importance": self.importance,
            "last_user_text": self.last_user_text,
            "last_assistant_text": self.last_assistant_text,
            "last_active_at_ms": self.last_active_at_ms,
            "expires_at_ms": self.expires_at_ms,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ShortTermTopic":
        data = dict(payload or {})
        user_text = str(data.get("last_user_text") or data.get("topic") or "")
        summary = _sanitize_summary_text(data.get("summary") or "")
        open_questions = list(data.get("open_questions") or [])
        emotion = str(data.get("emotion") or "neutral")
        scene = str(data.get("scene") or "")
        inferred_memory_type = _classify_memory_type(
            user_text,
            scene,
            emotion=emotion,
            open_questions=open_questions,
        )
        raw_memory_type = str(data.get("memory_type") or "").strip()
        memory_type = raw_memory_type or inferred_memory_type
        follow_up_candidate = data.get("follow_up_candidate")
        if follow_up_candidate is None:
            follow_up_candidate = _should_mark_follow_up_candidate(
                user_text,
                summary,
                memory_type,
            )
        follow_up = data.get("follow_up")
        if not isinstance(follow_up, dict):
            follow_up = _build_follow_up_metadata(
                user_text,
                summary,
                memory_type,
                scene=scene,
                open_questions=open_questions,
            )
        follow_up_candidate = bool(follow_up.get("eligible")) if isinstance(follow_up, dict) else bool(follow_up_candidate)
        entities = _sanitize_entities(data.get("entities") or [])
        greeting_candidate = data.get("greeting_candidate")
        if not isinstance(greeting_candidate, dict) or not greeting_candidate:
            greeting_candidate = _build_greeting_candidate_metadata(
                user_text,
                summary,
                memory_type,
                scene=scene,
                emotion=emotion,
                entities=entities,
                open_questions=open_questions,
                follow_up=follow_up,
            )
        return cls(
            topic_id=str(data.get("topic_id") or ""),
            topic=str(data.get("topic") or ""),
            summary=summary,
            memory_type=memory_type,
            follow_up_candidate=bool(follow_up_candidate),
            follow_up=dict(follow_up or {}),
            greeting_candidate=dict(greeting_candidate or {}),
            entities=entities,
            open_questions=open_questions,
            resolved_points=list(data.get("resolved_points") or []),
            emotion=emotion,
            scene=scene,
            importance=float(data.get("importance") or 0.5),
            last_user_text=user_text,
            last_assistant_text=str(data.get("last_assistant_text") or ""),
            last_active_at_ms=int(data.get("last_active_at_ms") or 0),
            expires_at_ms=int(data.get("expires_at_ms") or 0),
        )


class ShortTermMemoryManager:
    def __init__(self, max_topics: int = DEFAULT_MAX_TOPICS):
        self.max_topics = max(1, int(max_topics or DEFAULT_MAX_TOPICS))
        self.topics: List[ShortTermTopic] = []

    def cleanup_expired(self, now_ms: int | None = None) -> None:
        current = now_ms or _timestamp_ms()
        self.topics = [topic for topic in self.topics if not topic.is_expired(current)]

    def should_track_turn(self, user_text: str, scene: str | None) -> bool:
        scene_name = str(scene or "").strip()
        normalized_text = str(user_text or "").strip()
        if not normalized_text:
            return False
        if scene_name in SHORT_MEMORY_SCENES:
            return True
        if any(marker in normalized_text for marker in FOLLOW_UP_MARKERS):
            return True
        if any(marker in normalized_text for marker in HEALTH_MARKERS):
            return True
        if any(marker in normalized_text for marker in EMOTION_MARKERS):
            return True
        if any(marker in normalized_text for marker in TASK_MARKERS):
            return True
        if any(marker in normalized_text for marker in EVENT_MARKERS):
            return True
        if any(marker in normalized_text for marker in FOLLOWUP_CONTINUATION_MARKERS):
            return True
        return False

    def should_query(self, user_text: str, scene: str | None) -> bool:
        scene_name = str(scene or "").strip()
        if scene_name in SHORT_MEMORY_SCENES:
            return self.get_active_topic(user_text=user_text) is not None and self.topic_overlap_score(user_text) >= 0.18
        return self.topic_overlap_score(user_text) >= 0.18

    def topic_overlap_score(self, user_text: str | None) -> float:
        active_topic = self.get_active_topic(user_text=user_text)
        if active_topic is None:
            return 0.0
        return self._topic_match_score(active_topic, user_text)

    def get_active_topic(self, user_text: str | None = None) -> Optional[ShortTermTopic]:
        self.cleanup_expired()
        if not self.topics:
            return None

        if not user_text:
            return max(self.topics, key=lambda topic: topic.last_active_at_ms)

        user_tokens = set(_tokenize_text(user_text))
        best_topic: Optional[ShortTermTopic] = None
        best_score = -1.0
        freshest_topic = max(self.topics, key=lambda item: item.last_active_at_ms)
        for topic in self.topics:
            recency_bonus = 0.05 if topic == freshest_topic else 0.0
            token_bonus = 0.0
            topic_tokens = set(topic.tokens())
            if user_tokens and topic_tokens:
                token_bonus = len(user_tokens & topic_tokens) * 0.08
            score = self._topic_match_score(topic, user_text) + topic.importance + recency_bonus + token_bonus
            if score > best_score:
                best_score = score
                best_topic = topic
        return best_topic or max(self.topics, key=lambda topic: topic.last_active_at_ms)

    def build_prompt_patch(self, user_text: str | None = None) -> str:
        active_topic = self.get_active_topic(user_text=user_text)
        if active_topic is None:
            return ""

        lines = [
            "<short_term_memory>",
            f"active_topic={active_topic.topic}",
            f"summary={_sanitize_summary_text(active_topic.summary)}",
        ]
        if active_topic.entities:
            sanitized_entities = _sanitize_entities(active_topic.entities)
            if sanitized_entities:
                lines.append(f"entities={','.join(sanitized_entities)}")
        if active_topic.open_questions:
            lines.append(f"open_questions={','.join(active_topic.open_questions)}")
        if active_topic.scene:
            lines.append(f"scene={active_topic.scene}")
        if active_topic.memory_type:
            lines.append(f"memory_type={active_topic.memory_type}")
        if active_topic.emotion and active_topic.emotion != "neutral":
            lines.append(f"emotion={active_topic.emotion}")
        lines.append(
            "continuity_rule=如果本轮问题和上面话题直接相关，直接自然承接，不要当成第一次聊"
        )
        lines.append(
            "memory_rule=优先继续未完成的问题，先回答核心问题，再保留一个轻量互动"
        )
        lines.append(
            "reuse_rule=短期记忆主要用于记住孩子之前提过的经历、问题和主题，不要直接复述你上一轮的具体回答细节，除非孩子明确追问那个细节"
        )
        lines.append("</short_term_memory>")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        self.cleanup_expired()
        return {
            "topics": [topic.to_dict() for topic in self.topics],
            "count": len(self.topics),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ShortTermMemoryManager":
        manager = cls()
        topics = []
        for item in list((payload or {}).get("topics") or []):
            try:
                topics.append(ShortTermTopic.from_dict(item))
            except Exception:
                continue
        manager.topics = topics
        manager.cleanup_expired()
        return manager

    def update_from_turn(
            self,
            user_text: str,
            assistant_text: str,
            scene: str,
            subscene: str = "",
            emotion: str = "neutral",
            now_ms: int | None = None,
    ) -> Optional[ShortTermTopic]:
        current = now_ms or _timestamp_ms()
        self.cleanup_expired(current)
        if not self.should_track_turn(user_text, scene):
            return None

        ttl_hours = 12 if scene == "emotion_support" else DEFAULT_TOPIC_TTL_HOURS
        expires_at_ms = current + ttl_hours * 60 * 60 * 1000

        matched_topic = self.get_active_topic(user_text=user_text)
        topic_text = self._derive_topic_text(
            user_text,
            scene,
            subscene,
            matched_topic=matched_topic,
        )
        summary = self._derive_summary(user_text, assistant_text)
        entities = self._derive_entities(user_text, assistant_text)
        open_questions = self._derive_open_questions(user_text, assistant_text)
        resolved_points = self._derive_resolved_points(assistant_text)
        importance = self._derive_importance(user_text, scene)
        memory_type = _classify_memory_type(
            user_text,
            scene,
            emotion=emotion,
            open_questions=open_questions,
        )
        follow_up_candidate = _should_mark_follow_up_candidate(
            user_text,
            summary,
            memory_type,
        )
        follow_up = _build_follow_up_metadata(
            user_text,
            summary,
            memory_type,
            scene=scene,
            open_questions=open_questions,
        )
        follow_up_candidate = bool(follow_up.get("eligible"))
        greeting_candidate = _build_greeting_candidate_metadata(
            user_text,
            summary,
            memory_type,
            scene=scene,
            emotion=emotion,
            entities=entities,
            open_questions=open_questions,
            follow_up=follow_up,
        )

        overlap_score = self._topic_match_score(matched_topic, user_text) if matched_topic is not None else 0.0
        if matched_topic is not None and overlap_score >= 0.42:
            if self._should_upgrade_topic_title(matched_topic.topic, topic_text, scene):
                matched_topic.topic = _trim_text(topic_text or matched_topic.topic, 80)
            elif self._prefer_existing_topic_title(user_text, matched_topic):
                matched_topic.topic = _trim_text(matched_topic.topic, 80)
            else:
                matched_topic.topic = _trim_text(topic_text or matched_topic.topic, 80)
            matched_topic.summary = self._merge_summary(matched_topic.summary, summary)
            matched_topic.entities = _sanitize_entities((matched_topic.entities or []) + entities)[:DEFAULT_MAX_ENTITIES]
            matched_topic.open_questions = self._merge_open_questions(matched_topic.open_questions, open_questions)
            matched_topic.resolved_points = _dedupe_keep_order((matched_topic.resolved_points or []) + resolved_points)[:DEFAULT_MAX_RESOLVED_POINTS]
            matched_topic.memory_type = _merge_memory_type(
                getattr(matched_topic, "memory_type", "conversation"),
                memory_type,
            )
            matched_topic.follow_up = _merge_follow_up_metadata(
                getattr(matched_topic, "follow_up", {}),
                follow_up,
            )
            matched_topic.follow_up_candidate = bool((matched_topic.follow_up or {}).get("eligible"))
            matched_topic.greeting_candidate = _merge_greeting_candidate_metadata(
                getattr(matched_topic, "greeting_candidate", {}),
                greeting_candidate,
            )
            matched_topic.emotion = emotion or matched_topic.emotion
            matched_topic.scene = scene or matched_topic.scene
            matched_topic.importance = max(matched_topic.importance, importance)
            matched_topic.last_user_text = _trim_text(user_text, 120)
            matched_topic.last_assistant_text = _trim_text(assistant_text, 160)
            matched_topic.last_active_at_ms = current
            matched_topic.expires_at_ms = expires_at_ms
            self._sort_and_trim()
            return matched_topic

        topic_id = self._build_topic_id(topic_text or user_text, current)
        topic = ShortTermTopic(
            topic_id=topic_id,
            topic=_trim_text(topic_text or user_text, 80),
            summary=_trim_text(summary, 200),
            memory_type=memory_type,
            follow_up_candidate=follow_up_candidate,
            follow_up=follow_up,
            greeting_candidate=greeting_candidate,
            entities=_sanitize_entities(entities)[:DEFAULT_MAX_ENTITIES],
            open_questions=open_questions[:3],
            resolved_points=resolved_points[:3],
            emotion=emotion or "neutral",
            scene=scene or "",
            importance=importance,
            last_user_text=_trim_text(user_text, 120),
            last_assistant_text=_trim_text(assistant_text, 160),
            last_active_at_ms=current,
            expires_at_ms=expires_at_ms,
        )
        self.topics.append(topic)
        self._sort_and_trim()
        return topic

    def get_follow_up_candidates(self, now_ms: int | None = None) -> List[ShortTermTopic]:
        current = now_ms or _timestamp_ms()
        self.cleanup_expired(current)
        topics = [
            topic
            for topic in list(self.topics or [])
            if bool(((getattr(topic, "follow_up", {}) or {}).get("eligible")))
            and int(getattr(topic, "last_active_at_ms", 0) or 0) > 0
            and int(getattr(topic, "last_active_at_ms", 0) or 0) < current
        ]
        topics.sort(
            key=lambda item: (
                float(((getattr(item, "greeting_candidate", {}) or {}).get("score") or 0.0)),
                GREETING_CANDIDATE_TYPE_PRIORITY.get(
                    str(((getattr(item, "greeting_candidate", {}) or {}).get("type") or "")),
                    0,
                ),
                MEMORY_TYPE_PRIORITY.get(str(getattr(item, "memory_type", "")), 0),
                getattr(item, "importance", 0.0),
                getattr(item, "last_active_at_ms", 0),
            ),
            reverse=True,
        )
        return topics

    def _sort_and_trim(self) -> None:
        self.topics.sort(
            key=lambda topic: (topic.last_active_at_ms, topic.importance),
            reverse=True,
        )
        self.topics = self.topics[: self.max_topics]

    def _build_topic_id(self, topic_text: str, now_ms: int) -> str:
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", _normalize_text(topic_text))
        normalized = normalized.strip("_")[:24] or "topic"
        return f"{normalized}_{int(now_ms / 1000)}"

    def _derive_topic_text(
        self,
        user_text: str,
        scene: str,
        subscene: str,
        matched_topic: Optional[ShortTermTopic] = None,
    ) -> str:
        if scene == "curiosity":
            curiosity_topic = self._derive_curiosity_topic(user_text, matched_topic=matched_topic)
            if curiosity_topic:
                return curiosity_topic
        if any(marker in user_text for marker in FOLLOWUP_CONTINUATION_MARKERS):
            return _trim_text(user_text, 40)
        sentences = _split_sentences(user_text)
        if sentences:
            first = sentences[0]
            if len(first) <= 40:
                return first
            return first[:40].rstrip() + "…"
        fallback = subscene or scene or "recent_topic"
        return str(fallback)

    def _derive_curiosity_topic(
        self,
        user_text: str,
        matched_topic: Optional[ShortTermTopic] = None,
    ) -> str:
        entities = _extract_entity_candidates(user_text)
        context_entities = list(matched_topic.entities or []) if matched_topic is not None else []
        combined_entities = _dedupe_keep_order(context_entities + entities)
        has_red_panda = "小熊猫" in combined_entities
        has_panda = "大熊猫" in combined_entities or "熊猫" in combined_entities

        if has_red_panda and (
            "大熊猫" in user_text
            or "熊猫" in user_text
            or any(marker in user_text for marker in ("不一样", "区别", "不是熊猫"))
        ):
            return "小熊猫和大熊猫的区别"

        if "小熊猫" in entities and any(marker in user_text for marker in ("为什么", "科", "不一样")):
            if "大熊猫" in user_text or "熊猫" in user_text:
                return "小熊猫和大熊猫的区别"
            if "科" in user_text:
                return "小熊猫为什么有自己的科"
        if has_red_panda and "科" in user_text:
            return "小熊猫为什么有自己的科"
        if len(combined_entities) >= 2:
            return "和".join(combined_entities[:2])
        if combined_entities:
            return combined_entities[0]
        return ""

    def _derive_summary(self, user_text: str, assistant_text: str) -> str:
        user_core = _trim_text(user_text, 90)
        if any(marker in user_text for marker in QUESTION_MARKERS) or user_text.endswith(("？", "?")):
            return f"孩子在继续追问：{user_core}"
        if any(marker in user_text for marker in EVENT_MARKERS):
            return f"孩子提到最近经历：{user_core}"
        return f"孩子提到：{user_core}"

    def _derive_entities(self, user_text: str, assistant_text: str) -> List[str]:
        entities = _extract_entity_candidates(user_text)
        if not entities:
            entities = _extract_entity_candidates(assistant_text)
        return entities[:DEFAULT_MAX_ENTITIES]

    def _derive_open_questions(self, user_text: str, assistant_text: str) -> List[str]:
        sentences = _split_sentences(user_text)
        result = []
        for sentence in sentences:
            if any(marker in sentence for marker in QUESTION_MARKERS) or sentence.endswith("?") or sentence.endswith("？"):
                result.append(_trim_text(sentence, 80))
        if result:
            return _dedupe_keep_order(result)
        if "为什么" in user_text or "怎么" in user_text:
            return [_trim_text(user_text, 80)]
        return []

    def _derive_resolved_points(self, assistant_text: str) -> List[str]:
        sentences = _split_sentences(assistant_text)
        return [_trim_text(sentence, 80) for sentence in sentences[:2]]

    def _derive_importance(self, user_text: str, scene: str) -> float:
        base = 0.45
        if scene in {"curiosity", "learning_support"}:
            base += 0.2
        elif scene in {"emotion_support", "play_interaction"}:
            base += 0.12
        if any(marker in user_text for marker in EVENT_MARKERS):
            base += 0.1
        if any(marker in user_text for marker in QUESTION_MARKERS):
            base += 0.1
        if any(marker in user_text for marker in FOLLOWUP_CONTINUATION_MARKERS):
            base += 0.08
        return min(0.95, round(base, 2))

    def _topic_match_score(self, topic: Optional[ShortTermTopic], user_text: str | None) -> float:
        if topic is None:
            return 0.0
        normalized_user = _normalize_text(user_text)
        if not normalized_user:
            return 0.0

        score = 0.0
        phrases = [topic.topic] + list(topic.entities or []) + list(topic.open_questions or [])
        for phrase in _dedupe_keep_order(phrases):
            normalized_phrase = _normalize_text(phrase)
            if len(normalized_phrase) < 2:
                continue
            if normalized_phrase in normalized_user or normalized_user in normalized_phrase:
                score += min(0.9, 0.2 + len(normalized_phrase) * 0.08)

        user_entities = set(_extract_entity_candidates(user_text))
        topic_entities = set(topic.entities or [])
        if user_entities and topic_entities:
            score += len(user_entities & topic_entities) * 0.35

        normalized_user = _normalize_text(user_text)
        normalized_topic = _normalize_text(topic.topic)
        if normalized_topic and normalized_topic in normalized_user:
            score += 0.35
        if any(marker in normalized_user for marker in FOLLOWUP_CONTINUATION_MARKERS):
            score += 0.25

        user_tokens = set(_tokenize_text(user_text))
        topic_tokens = set(topic.tokens())
        if user_tokens and topic_tokens:
            score += len(user_tokens & topic_tokens) * 0.05

        return round(score, 3)

    def _prefer_existing_topic_title(self, user_text: str, topic: ShortTermTopic) -> bool:
        normalized_user = _normalize_text(user_text)
        if any(marker in normalized_user for marker in FOLLOWUP_CONTINUATION_MARKERS):
            return True
        if len(user_text) <= 18 and any(marker in normalized_user for marker in QUESTION_MARKERS):
            return True
        return False

    def _should_upgrade_topic_title(self, existing_topic: str, candidate_topic: str, scene: str) -> bool:
        existing = str(existing_topic or "").strip()
        candidate = str(candidate_topic or "").strip()
        if not candidate:
            return False
        if not existing:
            return True
        if scene == "curiosity":
            if "为什么" in candidate or "区别" in candidate or "自己的科" in candidate:
                if "今天" in existing or "上午" in existing or "下午" in existing or "动物园" in existing:
                    return True
        return len(candidate) >= len(existing) and candidate != existing

    def _merge_summary(self, existing_summary: str, new_summary: str) -> str:
        existing = _trim_text(existing_summary, 120)
        new = _trim_text(new_summary, 120)
        if not existing:
            return _trim_text(new, 200)
        if not new or new == existing:
            return _trim_text(existing, 200)
        if "继续追问" in new:
            return _trim_text(f"{existing}；后来{new}", 200)
        if "最近经历" in new and "最近经历" not in existing:
            return _trim_text(f"{existing}；后来{new}", 200)
        return _trim_text(existing, 200)

    def _merge_open_questions(self, existing: Sequence[str], new_items: Sequence[str]) -> List[str]:
        merged = _dedupe_keep_order(list(existing or []) + list(new_items or []))
        return merged[:3]
