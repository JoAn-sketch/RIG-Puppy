from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class TopicState:
    topic: str
    category: str
    turn_count: int
    engagement_score: float
    saturation_score: float
    last_updated: int
    recent_topics: List[str]
    recent_user_moves: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TopicDecision:
    action: str
    reason: str
    transition_type: str
    topic_source: str
    guidance: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


INTEREST_CATEGORY_KEYWORDS = {
    "animals": ("狗", "小狗", "猫", "小猫", "动物", "熊猫", "狐狸", "兔", "鸟", "鱼", "蜜蜂", "企鹅", "宠物"),
    "dinosaurs": ("恐龙", "霸王龙", "三角龙", "化石"),
    "space": ("太空", "宇宙", "星球", "月亮", "太阳", "火星", "火箭", "宇航员"),
    "vehicles": ("车", "汽车", "公交", "火车", "飞机", "交通", "轮船", "地铁"),
    "nature": ("大自然", "树", "花", "草", "森林", "天气", "下雨", "云", "风", "海", "山"),
    "sports": ("运动", "足球", "篮球", "跑步", "游泳", "跳绳", "比赛"),
    "art_and_crafts": ("画", "画画", "手工", "颜色", "剪纸", "涂色", "粘土"),
    "music_and_dance": ("音乐", "跳舞", "唱歌", "节奏", "乐器", "钢琴", "鼓"),
    "stories_and_picture_books": ("故事", "绘本", "童话", "角色", "书"),
    "riddles_and_games": ("猜谜", "谜语", "游戏", "小游戏", "线索", "挑战"),
}

CATEGORY_LABELS = {
    "animals": "小动物",
    "dinosaurs": "恐龙",
    "space": "太空",
    "vehicles": "交通工具",
    "nature": "大自然",
    "sports": "运动",
    "art_and_crafts": "画画和手工",
    "music_and_dance": "音乐和跳舞",
    "stories_and_picture_books": "故事和绘本",
    "riddles_and_games": "猜谜和小游戏",
    "general": "当前话题",
}

POSITIVE_ENGAGEMENT_MARKERS = (
    "为什么",
    "怎么",
    "然后呢",
    "还有",
    "我也",
    "我喜欢",
    "太好玩",
    "好有趣",
    "真的吗",
    "再讲",
    "想知道",
    "?",
    "？",
    "!",
    "！",
)

LOW_ENGAGEMENT_MARKERS = (
    "不知道",
    "随便",
    "都行",
    "没有",
    "不想",
    "算了",
    "嗯",
    "哦",
    "啊",
)

TOPIC_SWITCH_MARKERS = (
    "换个",
    "别说",
    "不聊",
    "讲别的",
    "说别的",
    "下一个",
)


def update_topic_lifecycle(
    *,
    previous_state: Dict[str, Any] | None,
    user_text: str | None,
    scene_name: str,
    subscene: str,
    openness_level: int,
    timestamp_ms: int,
    interests: List[str] | None = None,
) -> Dict[str, Any]:
    text = str(user_text or "").strip()
    previous = _normalize_previous_state(previous_state, timestamp_ms)
    extracted = _extract_topic(text, scene_name, subscene, interests or [])
    same_topic = _is_same_topic(previous, extracted)
    turn_count = int(previous.get("turn_count") or 0) + 1 if same_topic else 1
    recent_topics = _update_recent_list(previous.get("recent_topics"), extracted["topic"], max_size=8)
    user_move = _classify_user_move(text, same_topic=same_topic)
    recent_user_moves = _update_recent_list(previous.get("recent_user_moves"), user_move, max_size=8)
    engagement = _estimate_engagement(text, recent_user_moves, same_topic=same_topic)
    saturation = _estimate_saturation(
        turn_count=turn_count,
        recent_topics=recent_topics,
        recent_user_moves=recent_user_moves,
        same_topic=same_topic,
    )
    topic_state = TopicState(
        topic=extracted["topic"],
        category=extracted["category"],
        turn_count=turn_count,
        engagement_score=engagement,
        saturation_score=saturation,
        last_updated=timestamp_ms,
        recent_topics=recent_topics,
        recent_user_moves=recent_user_moves,
    )
    decision = decide_topic_action(
        openness_level=openness_level,
        topic_state=topic_state,
        user_text=text,
    )
    return {
        "topic_state": topic_state.to_dict(),
        "topic_decision": decision.to_dict(),
    }


def decide_topic_action(
    *,
    openness_level: int,
    topic_state: TopicState,
    user_text: str | None = None,
) -> TopicDecision:
    level = max(1, min(5, int(openness_level or 3)))
    text = str(user_text or "").strip()
    if level <= 2:
        return TopicDecision(
            action="continue",
            reason="openness_level_blocks_proactive_topic_change",
            transition_type="none",
            topic_source="current_request",
            guidance="优先完成孩子当前请求，不主动换题，不主动扩展。",
        )
    if _contains_any(text, TOPIC_SWITCH_MARKERS):
        return TopicDecision(
            action="transition" if level >= 4 else "expand",
            reason="child_requested_topic_switch",
            transition_type="child_requested",
            topic_source="current_interest",
            guidance="孩子已经表达想换方向，可以自然承接并切到相关或新的轻话题。",
        )
    if level == 3:
        return TopicDecision(
            action="continue",
            reason="neutral_openness_continue_current_topic",
            transition_type="none",
            topic_source="current_topic",
            guidance="继续回答当前问题；最多保留一个轻量相关追问，不引入无关兴趣。",
        )
    if topic_state.turn_count <= 3 and topic_state.saturation_score < 0.55:
        return TopicDecision(
            action="continue",
            reason="topic_still_fresh",
            transition_type="none",
            topic_source="current_topic",
            guidance="当前话题还新鲜，继续沿着孩子的问题回答。",
        )
    if level == 4:
        return TopicDecision(
            action="expand",
            reason="open_to_related_expansion",
            transition_type="related",
            topic_source="current_topic",
            guidance="可以从当前话题扩展到相邻方向，但不要跳到无关新兴趣。",
        )
    if topic_state.turn_count >= 7 and (
        topic_state.saturation_score >= 0.58 or topic_state.engagement_score <= 0.45
    ):
        return TopicDecision(
            action="transition",
            reason="topic_saturated_and_openness_high",
            transition_type=_select_transition_type(topic_state),
            topic_source=_select_topic_source(topic_state),
            guidance="先用一句话收束当前话题，再自然开启一个新话题；不要突然跳转。",
        )
    if topic_state.turn_count >= 4 or topic_state.saturation_score >= 0.5:
        return TopicDecision(
            action="expand",
            reason="topic_middle_stage",
            transition_type="related",
            topic_source="current_topic",
            guidance="优先做相关扩展，让话题出现新角度，避免重复同一个例子。",
        )
    return TopicDecision(
        action="continue",
        reason="default_continue",
        transition_type="none",
        topic_source="current_topic",
        guidance="继续当前话题，保持简短完整。",
    )


def build_topic_lifecycle_prompt_patch(state: Dict[str, Any]) -> str:
    topic_state = state.get("topic_state") or {}
    decision = state.get("topic_decision") or {}
    if not topic_state or not decision:
        return ""
    lines = [
        "<topic_lifecycle>",
        f"topic={topic_state.get('topic') or ''}",
        f"category={topic_state.get('category') or 'general'}",
        f"category_label={CATEGORY_LABELS.get(str(topic_state.get('category') or 'general'), '当前话题')}",
        f"turn_count={int(topic_state.get('turn_count') or 0)}",
        f"engagement_score={float(topic_state.get('engagement_score') or 0):.2f}",
        f"saturation_score={float(topic_state.get('saturation_score') or 0):.2f}",
        f"topic_action={decision.get('action') or 'continue'}",
        f"topic_action_reason={decision.get('reason') or ''}",
        f"transition_type={decision.get('transition_type') or 'none'}",
        f"topic_source={decision.get('topic_source') or 'current_topic'}",
        f"guidance={decision.get('guidance') or ''}",
        "rule=Topic Lifecycle 只决定对话方向，不覆盖孩子当前问题；必须先回应孩子当前输入。",
        "rule=continue 表示继续当前话题；expand 表示做相关扩展；transition 表示先自然收束再开启新话题。",
        "</topic_lifecycle>",
    ]
    return "\n".join(lines)


def _normalize_previous_state(previous_state: Dict[str, Any] | None, timestamp_ms: int) -> Dict[str, Any]:
    if not isinstance(previous_state, dict):
        return {
            "topic": "",
            "category": "general",
            "turn_count": 0,
            "engagement_score": 0.5,
            "saturation_score": 0.0,
            "last_updated": timestamp_ms,
            "recent_topics": [],
            "recent_user_moves": [],
        }
    normalized = dict(previous_state)
    normalized.setdefault("topic", "")
    normalized.setdefault("category", "general")
    normalized.setdefault("turn_count", 0)
    normalized.setdefault("engagement_score", 0.5)
    normalized.setdefault("saturation_score", 0.0)
    normalized.setdefault("last_updated", timestamp_ms)
    normalized.setdefault("recent_topics", [])
    normalized.setdefault("recent_user_moves", [])
    return normalized


def _extract_topic(text: str, scene_name: str, subscene: str, interests: List[str]) -> Dict[str, str]:
    normalized = _normalize_text(text)
    for category, keywords in INTEREST_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if _normalize_text(keyword) and _normalize_text(keyword) in normalized:
                return {"topic": keyword, "category": category}
    for interest in interests:
        normalized_interest = str(interest or "").strip()
        if normalized_interest and normalized_interest in INTEREST_CATEGORY_KEYWORDS:
            return {
                "topic": CATEGORY_LABELS.get(normalized_interest, normalized_interest),
                "category": normalized_interest,
            }
    clean_subscene = str(subscene or "").strip()
    if clean_subscene and clean_subscene != "greeting":
        return {"topic": clean_subscene, "category": _category_from_subscene(clean_subscene)}
    clean_scene = str(scene_name or "").strip() or "conversation"
    return {"topic": clean_scene, "category": "general"}


def _category_from_subscene(subscene: str) -> str:
    normalized = _normalize_text(subscene)
    if any(item in normalized for item in ("animal", "science", "natural")):
        return "nature"
    if "story" in normalized:
        return "stories_and_picture_books"
    if "game" in normalized:
        return "riddles_and_games"
    return "general"


def _is_same_topic(previous: Dict[str, Any], extracted: Dict[str, str]) -> bool:
    previous_topic = str(previous.get("topic") or "").strip()
    previous_category = str(previous.get("category") or "general").strip()
    if not previous_topic:
        return False
    if previous_topic == extracted["topic"]:
        return True
    return previous_category == extracted["category"] and extracted["category"] != "general"


def _classify_user_move(text: str, *, same_topic: bool) -> str:
    if not text:
        return "empty"
    if _contains_any(text, TOPIC_SWITCH_MARKERS):
        return "topic_switch"
    if _contains_any(text, POSITIVE_ENGAGEMENT_MARKERS):
        return "engaged"
    if len(_normalize_text(text)) <= 3 or _contains_any(text, LOW_ENGAGEMENT_MARKERS):
        return "low_engagement"
    if same_topic:
        return "same_topic_detail"
    return "new_topic"


def _estimate_engagement(text: str, recent_user_moves: List[str], *, same_topic: bool) -> float:
    score = 0.55
    normalized = _normalize_text(text)
    if _contains_any(text, POSITIVE_ENGAGEMENT_MARKERS):
        score += 0.25
    if len(normalized) >= 12:
        score += 0.12
    if same_topic:
        score += 0.06
    if _contains_any(text, LOW_ENGAGEMENT_MARKERS) or len(normalized) <= 2:
        score -= 0.25
    low_count = sum(1 for item in recent_user_moves[:4] if item == "low_engagement")
    score -= low_count * 0.08
    return _clamp(score, 0.0, 1.0)


def _estimate_saturation(
    *,
    turn_count: int,
    recent_topics: List[str],
    recent_user_moves: List[str],
    same_topic: bool,
) -> float:
    base = 1.0 / (1.0 + math.exp(-(turn_count - 5) / 1.4))
    repeated_topic_count = recent_topics[:6].count(recent_topics[0]) if recent_topics else 0
    if repeated_topic_count >= 4:
        base += 0.18
    if same_topic and turn_count >= 4:
        base += 0.08
    if any(item == "new_topic" for item in recent_user_moves[:2]):
        base -= 0.15
    return _clamp(base, 0.0, 1.0)


def _select_transition_type(topic_state: TopicState) -> str:
    if topic_state.category in {"animals", "nature", "space", "dinosaurs"}:
        return "curiosity"
    return "related"


def _select_topic_source(topic_state: TopicState) -> str:
    if topic_state.category and topic_state.category != "general":
        return "current_interest"
    return "quokka_inner_world"


def _update_recent_list(value: Any, item: str, max_size: int) -> List[str]:
    recent = [str(entry or "").strip() for entry in (value or []) if str(entry or "").strip()]
    if item:
        recent.insert(0, item)
    return recent[:max_size]


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(marker) in normalized for marker in markers if marker)


def _normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", "", str(text or "").strip().lower())


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
