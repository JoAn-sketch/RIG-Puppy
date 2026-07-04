from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


DEFAULT_MAX_TOPICS = 5
DEFAULT_TOPIC_TTL_HOURS = 24
DEFAULT_MAX_ENTITIES = 6

SHORT_MEMORY_SCENES = {
    "curiosity",
    "learning_support",
    "emotion_support",
    "play_interaction",
}

EVENT_MARKERS = (
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

QUESTION_MARKERS = (
    "为什么",
    "怎么",
    "是什么",
    "什么意思",
    "是不是",
    "能不能",
    "会不会",
)

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
    "已经",
    "还是",
    "就是",
    "然后",
    "自己",
    "我们",
    "你们",
    "他们",
}

ENTITY_SPLIT_PATTERN = re.compile(
    r"(为什么|怎么|是什么|什么意思|是不是|能不能|会不会|因为|所以|如果|但是|然后|刚刚|刚才|今天|上午|下午|早上|晚上|中午|自己|已经|我们|你们|他们|我的|你的|它的|这个|那个|一个|去了|看到|看了|去|看|在|和|跟|是|有|了|的|吗|呢|吧|呀|啊)"
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
    chinese_blocks = re.findall(r"[\u4e00-\u9fff]{2,24}", value)
    for block in chinese_blocks:
        pieces = ENTITY_SPLIT_PATTERN.split(block)
        for piece in pieces:
            piece = piece.strip()
            if len(piece) < 2:
                continue
            if piece in STOPWORDS:
                continue
            if any(generic in piece for generic in GENERIC_ENTITY_PARTS):
                continue
            if len(piece) > 8:
                for size in (4, 3):
                    for index in range(0, len(piece) - size + 1):
                        sub = piece[index:index + size]
                        if sub not in STOPWORDS and not any(generic in sub for generic in GENERIC_ENTITY_PARTS):
                            candidates.append(sub)
            else:
                candidates.append(piece)

    alpha_tokens = re.findall(r"[a-z0-9]{2,24}", value.lower())
    candidates.extend(alpha_tokens)
    return _dedupe_keep_order(candidates)


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


def _trim_text(text: str | None, max_len: int) -> str:
    value = str(text or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


def _timestamp_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class ShortTermTopic:
    topic_id: str
    topic: str
    summary: str
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
        if any(marker in normalized_text for marker in EVENT_MARKERS):
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
            f"summary={active_topic.summary}",
        ]
        if active_topic.entities:
            lines.append(f"entities={','.join(active_topic.entities)}")
        if active_topic.open_questions:
            lines.append(f"open_questions={','.join(active_topic.open_questions)}")
        if active_topic.scene:
            lines.append(f"scene={active_topic.scene}")
        if active_topic.emotion and active_topic.emotion != "neutral":
            lines.append(f"emotion={active_topic.emotion}")
        lines.append(
            "continuity_rule=如果本轮问题和上面话题直接相关，直接自然承接，不要当成第一次聊"
        )
        lines.append(
            "memory_rule=优先继续未完成的问题，先回答核心问题，再保留一个轻量互动"
        )
        lines.append("</short_term_memory>")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        self.cleanup_expired()
        return {
            "topics": [topic.to_dict() for topic in self.topics],
            "count": len(self.topics),
        }

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

        topic_text = self._derive_topic_text(user_text, scene, subscene)
        summary = self._derive_summary(user_text, assistant_text)
        entities = self._derive_entities(user_text, assistant_text)
        open_questions = self._derive_open_questions(user_text, assistant_text)
        resolved_points = self._derive_resolved_points(assistant_text)
        importance = self._derive_importance(user_text, scene)

        matched_topic = self.get_active_topic(user_text=user_text)
        overlap_score = self._topic_match_score(matched_topic, user_text) if matched_topic is not None else 0.0
        if matched_topic is not None and overlap_score >= 0.55:
            matched_topic.topic = _trim_text(topic_text or matched_topic.topic, 80)
            matched_topic.summary = _trim_text(summary or matched_topic.summary, 200)
            matched_topic.entities = _dedupe_keep_order((matched_topic.entities or []) + entities)[:DEFAULT_MAX_ENTITIES]
            matched_topic.open_questions = _dedupe_keep_order(open_questions)[:3]
            matched_topic.resolved_points = _dedupe_keep_order((matched_topic.resolved_points or []) + resolved_points)[:3]
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
            entities=entities[:DEFAULT_MAX_ENTITIES],
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

    def _derive_topic_text(self, user_text: str, scene: str, subscene: str) -> str:
        sentences = _split_sentences(user_text)
        if sentences:
            first = sentences[0]
            if len(first) <= 40:
                return first
            return first[:40].rstrip() + "…"
        fallback = subscene or scene or "recent_topic"
        return str(fallback)

    def _derive_summary(self, user_text: str, assistant_text: str) -> str:
        user_core = _trim_text(user_text, 90)
        assistant_core = _trim_text(assistant_text, 100)
        if assistant_core:
            return f"孩子提到{user_core}；机器人回应了{assistant_core}"
        return f"孩子提到{user_core}"

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

        user_tokens = set(_tokenize_text(user_text))
        topic_tokens = set(topic.tokens())
        if user_tokens and topic_tokens:
            score += len(user_tokens & topic_tokens) * 0.05

        return round(score, 3)
