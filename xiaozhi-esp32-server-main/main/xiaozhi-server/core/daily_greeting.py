from __future__ import annotations

import json
import os
import time
import random
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.long_term_memory_resolver import RuntimeLongTermMemory
from core.profile_resolver import RuntimeChildProfile
from core.runtime_generation_config import get_interest_config
from core.short_term_memory import ShortTermMemoryManager
from core.conversation_openness import daily_greeting_mode


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "daily_greeting_config.json")
STATE_PATH = os.path.join(DATA_DIR, "daily_greeting_state.json")

DEFAULT_DAILY_GREETING_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "llm_generation_enabled": False,
    "block_on_higher_priority_interruptions": True,
    "greeting_types": {
        "follow_up": {"priority": 100, "enabled": True},
        "emotional_check_in": {"priority": 90, "enabled": True},
        "achievement_milestone": {"priority": 70, "enabled": True},
        "memory_recall": {"priority": 50, "enabled": True},
        "interest_greeting": {"priority": 30, "enabled": True},
        "generic_greeting": {"priority": 10, "enabled": True},
    },
    "boot_greeting": {
        "enabled": True,
        "auto_play_after_startup": True,
        "wait_for_network": True,
        "wait_for_core_services": True,
        "max_duration_seconds": 3,
        "library": {
            "categories": [
                {
                    "key": "wake_up",
                    "label": "Wake Up",
                    "weight": 40,
                    "greetings": [
                        {"id": "wake_01", "text": "我醒来啦。"},
                        {"id": "wake_02", "text": "我已经准备好啦。"},
                        {"id": "wake_03", "text": "我在这里啦。"},
                    ],
                },
                {
                    "key": "happy_to_see_you",
                    "label": "Happy To See You",
                    "weight": 30,
                    "greetings": [
                        {"id": "happy_01", "text": "见到你我很开心。"},
                        {"id": "happy_02", "text": "你来啦，我好开心。"},
                    ],
                },
                {
                    "key": "adventure",
                    "label": "Adventure",
                    "weight": 20,
                    "greetings": [
                        {"id": "adventure_01", "text": "今天也一起去发现有趣的事情吧。"},
                        {"id": "adventure_02", "text": "今天不知道会有什么新冒险呢。"},
                    ],
                },
                {
                    "key": "ready_to_play",
                    "label": "Ready To Play",
                    "weight": 10,
                    "greetings": [
                        {"id": "play_01", "text": "我都准备好啦。"},
                        {"id": "play_02", "text": "我随时都可以陪你玩。"},
                    ],
                },
            ]
        },
        "last_boot_greeting": {
            "category": "",
            "greeting_id": "",
        },
    },
}

SUPPORTED_GREETING_INTENTS = {
    "curiosity",
    "follow_up",
    "invitation",
    "sharing",
    "appreciation",
    "celebration",
}

OPENING_STYLES = (
    "noticing",
    "question",
    "excitement",
    "exploration",
    "playful_guess",
    "curiosity",
    "natural_recall",
)

NEGATIVE_EMOTION_MARKERS = (
    "难过",
    "伤心",
    "害怕",
    "紧张",
    "不开心",
    "委屈",
    "担心",
)

POSITIVE_EMOTION_MARKERS = (
    "开心",
    "高兴",
    "兴奋",
    "期待",
    "激动",
)

INTEREST_LABELS = {
    "animals": "小动物",
    "dinosaurs": "恐龙",
    "space": "太空",
    "vehicles": "汽车和交通工具",
    "nature": "大自然",
    "sports": "运动",
    "art_and_crafts": "画画和手工",
    "music_and_dance": "音乐和跳舞",
    "stories_and_picture_books": "故事和绘本",
    "riddles_and_games": "猜谜和小游戏",
}

COMMON_INTEREST_TOPIC_BLOCKLIST = {
    "animals": ("狗摇尾巴", "猫为什么喵喵叫", "小狗小猫", "dogs wagging tails", "cats meowing"),
    "dinosaurs": ("霸王龙有多厉害", "恐龙为什么灭绝"),
    "space": ("太阳有多大", "月亮为什么跟着我", "火箭怎么飞"),
}

INTEREST_DOMAIN_LABELS = {
    "fun_facts": "有趣冷知识",
    "behaviors": "行为小秘密",
    "habitats": "生活环境",
    "comparisons": "对比观察",
    "emotions": "情绪和感受",
    "imagination": "想象问题",
    "stories": "故事灵感",
    "games": "小游戏",
    "conservation": "保护自然",
    "science": "科学小秘密",
    "species": "不同种类",
    "fossils": "化石",
    "extinction": "消失的原因",
    "planets": "星球",
    "astronauts": "宇航员",
    "rockets": "火箭",
    "future": "未来想象",
    "mysteries": "未解之谜",
    "how_it_moves": "怎么动起来",
    "design": "设计结构",
    "speed": "速度",
    "jobs": "用途和工作",
    "history": "历史变化",
    "safety": "安全规则",
    "plants": "植物",
    "weather": "天气",
    "seasons": "季节",
    "ecosystems": "生态关系",
    "observation": "观察挑战",
    "skills": "技巧",
    "teamwork": "团队合作",
    "practice": "练习",
    "body": "身体运动",
    "rules": "规则",
    "strategy": "策略",
    "feelings": "感受",
    "techniques": "小技巧",
    "colors": "颜色",
    "creativity": "创造力",
    "materials": "材料",
    "challenges": "小挑战",
    "projects": "手工项目",
    "rhythm": "节奏",
    "instruments": "乐器",
    "movement": "动作",
    "performance": "表演",
    "patterns": "规律",
    "characters": "角色",
    "story_worlds": "故事世界",
    "plot": "情节",
    "pictures": "图画",
    "choices": "选择",
    "endings": "结尾",
    "logic": "逻辑",
    "clues": "线索",
    "memory": "记忆",
    "wordplay": "文字游戏",
    "mini_games": "小游戏",
}


@dataclass(frozen=True)
class DailyGreetingCandidate:
    greeting_type: str
    priority: int
    source_id: str
    text: str
    intent: str = "appreciation"
    context: Dict[str, Any] | None = None
    opening_style: str = ""
    generated: bool = False


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    _ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_daily_greeting_config() -> Dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_DAILY_GREETING_CONFIG, ensure_ascii=False))
    raw = _read_json(CONFIG_PATH)
    if "enabled" in raw:
        config["enabled"] = bool(raw.get("enabled"))
    if "llm_generation_enabled" in raw:
        config["llm_generation_enabled"] = bool(raw.get("llm_generation_enabled"))
    if "block_on_higher_priority_interruptions" in raw:
        config["block_on_higher_priority_interruptions"] = bool(raw.get("block_on_higher_priority_interruptions"))
    incoming_types = raw.get("greeting_types")
    if isinstance(incoming_types, dict):
        for type_name, defaults in config["greeting_types"].items():
            incoming = incoming_types.get(type_name)
            if not isinstance(incoming, dict):
                continue
            if "enabled" in incoming:
                defaults["enabled"] = bool(incoming.get("enabled"))
            if "priority" in incoming:
                try:
                    defaults["priority"] = int(incoming.get("priority"))
                except (TypeError, ValueError):
                    pass
    incoming_boot = raw.get("boot_greeting")
    if isinstance(incoming_boot, dict):
        boot_defaults = config["boot_greeting"]
        for field_name in (
            "enabled",
            "auto_play_after_startup",
            "wait_for_network",
            "wait_for_core_services",
        ):
            if field_name in incoming_boot:
                boot_defaults[field_name] = bool(incoming_boot.get(field_name))
        if "max_duration_seconds" in incoming_boot:
            try:
                boot_defaults["max_duration_seconds"] = max(
                    1,
                    min(30, int(incoming_boot.get("max_duration_seconds"))),
                )
            except (TypeError, ValueError):
                pass
        incoming_last = incoming_boot.get("last_boot_greeting")
        if isinstance(incoming_last, dict):
            boot_defaults["last_boot_greeting"] = {
                "category": str(incoming_last.get("category") or "").strip(),
                "greeting_id": str(incoming_last.get("greeting_id") or "").strip(),
            }
        incoming_library = incoming_boot.get("library")
        if isinstance(incoming_library, dict) and isinstance(incoming_library.get("categories"), list):
            categories = []
            for item in incoming_library.get("categories") or []:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "").strip()
                label = str(item.get("label") or key).strip() or key
                if not key:
                    continue
                try:
                    weight = max(1, min(999, int(item.get("weight") or 10)))
                except (TypeError, ValueError):
                    weight = 10
                greetings = []
                for greeting in item.get("greetings") or []:
                    if not isinstance(greeting, dict):
                        continue
                    greeting_id = str(greeting.get("id") or "").strip()
                    greeting_text = str(greeting.get("text") or "").strip()
                    if greeting_id and greeting_text:
                        greetings.append({"id": greeting_id, "text": greeting_text})
                if greetings:
                    categories.append(
                        {
                            "key": key,
                            "label": label,
                            "weight": weight,
                            "greetings": greetings,
                        }
                    )
            if categories:
                boot_defaults["library"] = {"categories": categories}
    return config


def load_boot_greeting_config() -> Dict[str, Any]:
    config = load_daily_greeting_config()
    boot = config.get("boot_greeting") or {}
    return boot if isinstance(boot, dict) else dict(DEFAULT_DAILY_GREETING_CONFIG["boot_greeting"])


def _write_boot_greeting_state(category: str, greeting_id: str) -> None:
    config = load_daily_greeting_config()
    boot = config.setdefault("boot_greeting", {})
    boot["last_boot_greeting"] = {
        "category": str(category or "").strip(),
        "greeting_id": str(greeting_id or "").strip(),
    }
    _write_json(CONFIG_PATH, config)


def _choose_weighted_boot_category(categories: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    weighted = []
    total = 0
    for item in categories:
        try:
            weight = max(1, int(item.get("weight") or 0))
        except (TypeError, ValueError):
            weight = 1
        greetings = item.get("greetings") or []
        if not greetings:
            continue
        total += weight
        weighted.append((total, item))
    if total <= 0 or not weighted:
        return None
    pick = random.randint(1, total)
    for upper, item in weighted:
        if pick <= upper:
            return item
    return weighted[-1][1]


def _choose_boot_greeting_from_category(category: Dict[str, Any], last_category: str, last_greeting_id: str) -> Dict[str, Any] | None:
    greetings = [
        greeting for greeting in list(category.get("greetings") or [])
        if str(greeting.get("id") or "").strip() and str(greeting.get("text") or "").strip()
    ]
    if not greetings:
        return None
    category_key = str(category.get("key") or "").strip()
    if category_key == last_category and len(greetings) > 1:
        filtered = [
            greeting for greeting in greetings
            if str(greeting.get("id") or "").strip() != last_greeting_id
        ]
        if filtered:
            greetings = filtered
    return random.choice(greetings)


def get_boot_greeting_text(
    child_profile: RuntimeChildProfile | None = None,
    long_term_memory: RuntimeLongTermMemory | None = None,
) -> str | None:
    config = load_boot_greeting_config()
    if not bool(config.get("enabled", True)):
        return None
    if not bool(config.get("auto_play_after_startup", True)):
        return None
    categories = list(((config.get("library") or {}).get("categories") or []))
    if not categories:
        return None
    last = config.get("last_boot_greeting") or {}
    last_category = str(last.get("category") or "").strip()
    last_greeting_id = str(last.get("greeting_id") or "").strip()

    selected_category = _choose_weighted_boot_category(categories)
    if selected_category is None:
        return None
    selected_greeting = _choose_boot_greeting_from_category(
        selected_category,
        last_category,
        last_greeting_id,
    )
    if selected_greeting is None:
        return None

    category_key = str(selected_category.get("key") or "").strip()
    greeting_id = str(selected_greeting.get("id") or "").strip()
    greeting_text = str(selected_greeting.get("text") or "").strip()
    if not greeting_text:
        return None

    if category_key == last_category and greeting_id == last_greeting_id and len(selected_category.get("greetings") or []) > 1:
        alternatives = [
            greeting for greeting in list(selected_category.get("greetings") or [])
            if str(greeting.get("id") or "").strip() != last_greeting_id
        ]
        if alternatives:
            selected_greeting = random.choice(alternatives)
            greeting_id = str(selected_greeting.get("id") or "").strip()
            greeting_text = str(selected_greeting.get("text") or "").strip()

    _write_boot_greeting_state(category_key, greeting_id)
    address_name = _resolve_address_name(child_profile, long_term_memory)
    return _replace_default_you(greeting_text, address_name)


def _normalize_text(text: str | None) -> str:
    return "".join(str(text or "").strip().split()).lower()


def _resolve_address_name(
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
) -> str:
    memory_name = str(getattr(long_term_memory, "nickname_preference", "") or "").strip()
    if memory_name:
        return memory_name
    profile_name = str(getattr(child_profile, "nickname", "") or "").strip()
    if profile_name:
        return profile_name
    return ""


def _prefix_with_address(text: str, address_name: str) -> str:
    normalized_text = str(text or "").strip()
    normalized_name = str(address_name or "").strip()
    if not normalized_text or not normalized_name:
        return normalized_text
    if normalized_text.startswith(normalized_name):
        return normalized_text
    return f"{normalized_name}，{normalized_text}"


def _replace_default_you(text: str, address_name: str) -> str:
    normalized_text = str(text or "").strip()
    normalized_name = str(address_name or "").strip()
    if not normalized_text or not normalized_name:
        return normalized_text
    replaced = normalized_text
    replacements = (
        ("你来啦", f"{normalized_name}来啦"),
        ("见到你", f"见到{normalized_name}"),
        ("你听起来", f"{normalized_name}听起来"),
        ("你好像", f"{normalized_name}好像"),
        ("你喜欢", f"{normalized_name}喜欢"),
        ("你真的", f"{normalized_name}真的"),
        ("你还", f"{normalized_name}还"),
        ("你有点", f"{normalized_name}有点"),
        ("你都", f"{normalized_name}都"),
        ("你", normalized_name),
    )
    for source, target in replacements:
        if source in replaced:
            replaced = replaced.replace(source, target)
    return replaced


def is_meaningful_interaction(text: str | None, wakeup_words: List[str] | None = None) -> bool:
    normalized = _normalize_text(text)
    return bool(normalized)


def _today_string(now_ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now_ts or time.time()))


def _clock_string(now_ts: float | None = None) -> str:
    return time.strftime("%H:%M", time.localtime(now_ts or time.time()))


def _normalize_device_id(device_id: str) -> str:
    return str(device_id or "").strip().lower()


def has_delivered_today(device_id: str, now_ts: float | None = None) -> bool:
    normalized_device_id = _normalize_device_id(device_id)
    if not normalized_device_id:
        return False
    state = _read_json(STATE_PATH)
    devices = state.get("devices") or {}
    device_state = devices.get(normalized_device_id) or {}
    return bool(device_state.get("delivered")) and str(device_state.get("date") or "") == _today_string(now_ts)


def mark_greeting_delivered(device_id: str, candidate: DailyGreetingCandidate, now_ts: float | None = None) -> None:
    normalized_device_id = _normalize_device_id(device_id)
    if not normalized_device_id:
        return
    state = _read_json(STATE_PATH)
    devices = state.setdefault("devices", {})
    recent = _recent_greeting_patterns_from_state(devices.get(normalized_device_id) or {})
    recent.insert(0, {
        "date": _today_string(now_ts),
        "greeting_type": candidate.greeting_type,
        "intent": candidate.intent,
        "source_id": candidate.source_id,
        "opening_style": candidate.opening_style,
        "opening_phrase": _opening_phrase(candidate.text),
        "interest": str((candidate.context or {}).get("interest") or ""),
        "interest_label": str((candidate.context or {}).get("interest_label") or ""),
        "interest_domain": str((candidate.context or {}).get("interest_domain") or ""),
        "interest_topic": str((candidate.context or {}).get("interest_topic") or ""),
    })
    recent = recent[:7]
    devices[normalized_device_id] = {
        "date": _today_string(now_ts),
        "delivered": True,
        "greeting_type": candidate.greeting_type,
        "intent": candidate.intent,
        "source_id": candidate.source_id,
        "opening_style": candidate.opening_style,
        "timestamp": _clock_string(now_ts),
        "generated": bool(candidate.generated),
        "generated_text": candidate.text,
        "interest": str((candidate.context or {}).get("interest") or ""),
        "interest_label": str((candidate.context or {}).get("interest_label") or ""),
        "interest_domain": str((candidate.context or {}).get("interest_domain") or ""),
        "interest_topic": str((candidate.context or {}).get("interest_topic") or ""),
        "recent_patterns": recent,
    }
    _write_json(STATE_PATH, state)


def _recent_greeting_patterns(device_id: str) -> List[Dict[str, Any]]:
    normalized_device_id = _normalize_device_id(device_id)
    if not normalized_device_id:
        return []
    state = _read_json(STATE_PATH)
    devices = state.get("devices") or {}
    return _recent_greeting_patterns_from_state(devices.get(normalized_device_id) or {})


def _recent_greeting_patterns_from_state(device_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    recent = device_state.get("recent_patterns")
    if isinstance(recent, list):
        return [item for item in recent if isinstance(item, dict)]
    if not device_state:
        return []
    return [{
        "date": str(device_state.get("date") or ""),
        "greeting_type": str(device_state.get("greeting_type") or ""),
        "intent": str(device_state.get("intent") or ""),
        "source_id": str(device_state.get("source_id") or ""),
        "opening_style": str(device_state.get("opening_style") or ""),
        "opening_phrase": _opening_phrase(str(device_state.get("generated_text") or "")),
        "interest": str(device_state.get("interest") or ""),
        "interest_label": str(device_state.get("interest_label") or ""),
        "interest_domain": str(device_state.get("interest_domain") or ""),
        "interest_topic": str(device_state.get("interest_topic") or ""),
    }]


def _opening_phrase(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    separators = "，,。！？!? "
    for index, char in enumerate(normalized):
        if char in separators:
            return normalized[:index].strip()
    return normalized[:10]


def _type_enabled(config: Dict[str, Any], type_name: str) -> bool:
    return bool(((config.get("greeting_types") or {}).get(type_name) or {}).get("enabled", True))


def _type_priority(config: Dict[str, Any], type_name: str) -> int:
    try:
        return int(((config.get("greeting_types") or {}).get(type_name) or {}).get("priority") or 0)
    except (TypeError, ValueError):
        return 0


def _age_group_from_context(
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
) -> str:
    profile_age = str(getattr(child_profile, "age_group", "") or "").strip()
    if profile_age:
        return profile_age
    memory_age = str(getattr(long_term_memory, "age_group", "") or "").strip()
    return memory_age or "6-8"


def _choose_opening_style(intent: str, recent_patterns: List[Dict[str, Any]]) -> str:
    recent_styles = {
        str(item.get("opening_style") or "").strip()
        for item in recent_patterns[:3]
        if str(item.get("opening_style") or "").strip()
    }
    intent_styles = {
        "curiosity": ("curiosity", "question", "playful_guess", "noticing"),
        "follow_up": ("natural_recall", "question", "noticing"),
        "invitation": ("exploration", "playful_guess", "excitement"),
        "sharing": ("excitement", "noticing", "curiosity"),
        "appreciation": ("noticing", "excitement", "question"),
        "celebration": ("excitement", "invitation", "noticing"),
    }
    styles = list(intent_styles.get(intent, OPENING_STYLES))
    available = [style for style in styles if style not in recent_styles]
    return random.choice(available or styles or list(OPENING_STYLES))


def _select_interest(memory: RuntimeLongTermMemory, recent_patterns: List[Dict[str, Any]]) -> Tuple[str, str]:
    interests = [str(item or "").strip() for item in (memory.interests or []) if str(item or "").strip() in INTEREST_LABELS]
    if not interests:
        return "", ""
    recent_interests = {
        str(item.get("interest") or "").strip()
        for item in recent_patterns[:5]
        if str(item.get("interest") or "").strip()
    }
    if not recent_interests:
        recent_interests = set()
        for item in recent_patterns[:5]:
            source_id = str(item.get("source_id") or "").strip()
            if not source_id.startswith("interest_"):
                continue
            source_interest = source_id.removeprefix("interest_")
            if source_interest in interests:
                recent_interests.add(source_interest)
    available = [item for item in interests if item not in recent_interests]
    interest_key = random.choice(available or interests)
    return interest_key, INTEREST_LABELS[interest_key]


def _interest_domains(interest_key: str) -> List[str]:
    config = get_interest_config()
    adapter = config.get("interest_adapter") or {}
    topic_adapter = adapter.get(interest_key)
    if not isinstance(topic_adapter, dict):
        return []
    domains = topic_adapter.get("domains")
    if isinstance(domains, list):
        return [str(item or "").strip() for item in domains if str(item or "").strip()]
    return []


def _select_interest_domain(interest_key: str, recent_patterns: List[Dict[str, Any]]) -> str:
    domains = _interest_domains(interest_key)
    if not domains:
        return "fresh_curiosity"
    recent_domains = [
        str(item.get("interest_domain") or "").strip()
        for item in recent_patterns
        if str(item.get("interest") or "").strip() == interest_key and str(item.get("interest_domain") or "").strip()
    ]
    blocked = set(recent_domains[:2])
    candidates = [domain for domain in domains if domain not in blocked] or list(domains)
    usage = {domain: recent_domains.count(domain) for domain in domains}
    min_usage = min(usage.get(domain, 0) for domain in candidates)
    underused = [domain for domain in candidates if usage.get(domain, 0) == min_usage]
    return random.choice(underused or candidates)


def _base_context(
    *,
    intent: str,
    greeting_type: str,
    source_id: str,
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
    conversation_openness_level: int | None,
    opening_style: str,
    recent_patterns: List[Dict[str, Any]],
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "intent": intent if intent in SUPPORTED_GREETING_INTENTS else "appreciation",
        "greeting_type": greeting_type,
        "source_id": source_id,
        "child_name": _resolve_address_name(child_profile, long_term_memory),
        "age_group": _age_group_from_context(child_profile, long_term_memory),
        "conversation_openness": f"level_{conversation_openness_level or 3}",
        "robot_personality": "playful, warm, spontaneous, companion-like",
        "opening_style": opening_style,
        "recent_patterns": [
            {
                "intent": str(item.get("intent") or ""),
                "opening_style": str(item.get("opening_style") or ""),
                "opening_phrase": str(item.get("opening_phrase") or ""),
                "interest": str(item.get("interest") or ""),
                "interest_domain": str(item.get("interest_domain") or ""),
                "interest_topic": str(item.get("interest_topic") or ""),
            }
            for item in recent_patterns[:5]
        ],
    }
    if extra:
        context.update(extra)
    return context


def _fallback_text_for_context(context: Dict[str, Any]) -> str:
    child_name = str(context.get("child_name") or "").strip()
    prefix = f"{child_name}，" if child_name else ""
    intent = str(context.get("intent") or "")
    interest_label = str(context.get("interest_label") or "").strip()
    interest_topic = str(context.get("interest_topic") or "").strip()
    follow_up_hint = str(context.get("follow_up_hint") or "").strip()
    favorite = str(context.get("favorite_dog_type") or "").strip()
    if intent == "follow_up" and follow_up_hint:
        return _format_follow_up_greeting(prefix, follow_up_hint)
    if intent == "sharing" and favorite:
        return f"{prefix}我刚刚想起{favorite}，有点想和你聊聊它。"
    if interest_label and interest_topic:
        return f"{prefix}我刚刚想到一个小问题：{interest_topic}"
    if interest_label:
        return f"{prefix}刚才我忽然好奇，{interest_label}里会不会藏着一个小秘密？"
    if intent == "celebration":
        return f"{prefix}今天有点特别，我们一起找件开心的小事吧。"
    return f"{prefix}见到你真开心，今天想从哪里开始玩呢？"


def _format_follow_up_greeting(prefix: str, follow_up_hint: str) -> str:
    hint = str(follow_up_hint or "").strip(" ，,。！？!?；;")
    if not hint:
        return f"{prefix}昨天那件事，今天怎么样啦？"
    if any(marker in hint for marker in ("病", "不舒服", "医院", "检查", "输液")):
        if "快好" in hint or "好起来" in hint or "好多" in hint:
            return f"{prefix}昨天你说{hint}，今天它怎么样啦？"
        return f"{prefix}昨天你说{hint}，今天好一点了吗？"
    if hint.startswith(("去", "看", "参加", "比赛", "表演")):
        return f"{prefix}昨天你说{hint}，后来怎么样啦？"
    return f"{prefix}昨天你提到{hint}，今天还想和我说说吗？"


def _sanitize_generated_greeting(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    normalized = normalized.replace("\n", " ").replace("\r", " ")
    normalized = normalized.strip("「」“”\"' ")
    for prefix in ("Koko：", "可可：", "回答：", "问候："):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    sentences: List[str] = []
    current = ""
    for char in normalized:
        current += char
        if char in "。！？!?":
            if current.strip():
                sentences.append(current.strip())
            current = ""
            if len(sentences) >= 2:
                break
    if not sentences and current.strip():
        sentences.append(current.strip())
    cleaned = "".join(sentences[:2]).strip()
    if len(cleaned) > 70:
        cleaned = cleaned[:70].rstrip("，,、；; ")
        if cleaned and cleaned[-1] not in "。！？!?":
            cleaned += "。"
    banned_fragments = ("我想到一个和", "今天我想", "今天想听听吗", "Would you like")
    if any(fragment in cleaned for fragment in banned_fragments):
        return ""
    return cleaned


def _sanitize_interest_topic(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    normalized = normalized.replace("\n", " ").replace("\r", " ")
    normalized = normalized.strip("「」“”\"' ")
    for prefix in ("话题：", "Topic:", "topic:", "问题：", "开场话题："):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    for separator in ("。", "！", "？", "!", "?"):
        if separator in normalized:
            normalized = normalized.split(separator, 1)[0].strip() + separator
            break
    if len(normalized) > 64:
        normalized = normalized[:64].rstrip("，,、；; ")
        if normalized and normalized[-1] not in "。！？!?":
            normalized += "？"
    return normalized


def _interest_domain_label(domain: str) -> str:
    normalized = str(domain or "").strip()
    return INTEREST_DOMAIN_LABELS.get(normalized) or "新鲜小秘密"


def _fallback_interest_topic(context: Dict[str, Any]) -> str:
    interest_label = str(context.get("interest_label") or "").strip() or "喜欢的东西"
    domain = str(context.get("interest_domain") or "").strip() or "fresh_curiosity"
    domain_label = _interest_domain_label(domain)
    if domain in {"imagination", "future", "mysteries"}:
        return f"{interest_label}里会不会藏着一个奇怪的小问题？"
    if domain in {"games", "mini_games"}:
        return f"{interest_label}可以变成什么小游戏？"
    if domain in {"observation", "clues", "comparisons"}:
        return f"{interest_label}里有什么一眼看不出来的小线索？"
    if domain in {"stories", "story_worlds", "characters", "plot"}:
        return f"{interest_label}里会发生什么小故事？"
    return f"{interest_label}里有什么{domain_label}？"


def _clean_follow_up_hint(text: str | None) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    for prefix in ("孩子提到最近经历：", "孩子提到：", "孩子在继续追问："):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    value = value.split("；后来", 1)[0].strip(" ，,。！？!?；;")
    replacements = (
        ("我的", ""),
        ("我说", ""),
        ("我提到", ""),
    )
    for source, target in replacements:
        if value.startswith(source):
            value = target + value[len(source):]
    value = value.strip(" ，,。！？!?；;")
    value = value.replace("我昨天", "").replace("昨天", "").strip(" ，,。！？!?；;")
    value = value.replace("我的猫", "猫猫").replace("我的小猫", "小猫").replace("我的狗", "狗狗")
    value = value.replace("他", "它").replace("她", "它")
    value = value.replace("带猫猫去", "猫猫去").replace("带小猫去", "小猫去").replace("带狗狗去", "狗狗去")
    if "猫" in value and "医院" in value and "检查" in value and ("病快好了" in value or "快好了" in value):
        return "猫猫去医院检查后快好了"
    if "猫" in value and "医院" in value and ("病" in value or "不舒服" in value):
        return "猫猫去医院检查"
    if "猫" in value and ("病快好了" in value or "快好了" in value):
        return "猫猫的病快好了"
    if "猫" in value and ("生病" in value or "不舒服" in value):
        return "猫猫生病了"
    noisy_fragments = ("我的和就能", "和就能", "得很清楚")
    if any(fragment in value for fragment in noisy_fragments):
        if "猫" in value:
            return "猫晚上看得很清楚这件事"
        if "狗" in value:
            return "狗狗的事情"
        return ""
    if "猫" in value and "晚上" in value and ("看得很清楚" in value or "看得清楚" in value):
        return "猫晚上看得很清楚这件事"
    if len(value) > 32:
        value = value[:32].rstrip(" ，,。！？!?；;") + "…"
    return value


def _follow_up_source_id(topic: Any) -> str:
    raw_id = str(getattr(topic, "topic_id", "") or "").strip()
    source = raw_id or str(getattr(topic, "topic", "") or "").strip() or str(getattr(topic, "summary", "") or "").strip()
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10] if source else "unknown"
    return f"follow_up_{digest}"


def _generate_interest_topic(llm: Any, context: Dict[str, Any]) -> str:
    fallback = _fallback_interest_topic(context)
    if llm is None or not hasattr(llm, "response_no_stream"):
        return fallback
    interest_key = str(context.get("interest") or "").strip()
    blocked = list(COMMON_INTEREST_TOPIC_BLOCKLIST.get(interest_key) or ())
    recent_topics = [
        str(item.get("interest_topic") or "").strip()
        for item in context.get("recent_patterns") or []
        if str(item.get("interest") or "").strip() == interest_key and str(item.get("interest_topic") or "").strip()
    ]
    prompt_context = {
        "interest": interest_key,
        "interest_label": context.get("interest_label"),
        "selected_domain": context.get("interest_domain"),
        "selected_domain_label": _interest_domain_label(str(context.get("interest_domain") or "")),
        "age_group": context.get("age_group"),
        "recent_interest_topics": recent_topics[:6],
        "avoid_common_topics": blocked,
    }
    system_prompt = (
        "你是儿童陪伴机器人的兴趣话题选择器。"
        "根据 interest 和 selected_domain 生成一个具体、新鲜、适龄的中文话题。"
        "只输出一个话题，最好是一个短问题或一句好奇发现。"
        "selected_domain 是内部分类，只能理解它的含义，不能原样输出英文分类词。"
        "如果需要表达分类含义，使用 selected_domain_label 的中文意思自然改写。"
        "不要泛泛说“聊聊某兴趣”，不要重复 recent_interest_topics。"
        "尽量避开 avoid_common_topics，除非它们和 selected_domain 强相关。"
        "话题只用于后续开场生成，不要写解释、不要编号。"
    )
    try:
        generated = llm.response_no_stream(
            system_prompt,
            json.dumps(prompt_context, ensure_ascii=False, indent=2),
            max_tokens=70,
            temperature=0.95,
            top_p=0.92,
        )
    except Exception:
        return fallback
    topic = _sanitize_interest_topic(generated) or fallback
    raw_domain = str(context.get("interest_domain") or "").strip()
    if raw_domain and raw_domain in topic:
        topic = topic.replace(raw_domain, _interest_domain_label(raw_domain))
    return topic


def _generate_greeting_text(
    llm: Any,
    context: Dict[str, Any],
) -> str:
    if str(context.get("greeting_type") or "").strip() == "interest_greeting" and not str(context.get("interest_topic") or "").strip():
        context["interest_topic"] = _generate_interest_topic(llm, context)
    fallback = _fallback_text_for_context(context)
    if llm is None or not hasattr(llm, "response_no_stream"):
        return fallback
    system_prompt = (
        "你是儿童陪伴机器人可可的 Daily Greeting 生成器。"
        "只根据用户提供的结构化上下文生成一句自然的中文开场。"
        "不要引用孩子原话，不要编造隐私细节，不要像课程通知。"
        "语气要 spontaneous、playful、emotionally warm，像可可自己忽然想说的话。"
        "最多两句，优先一句，适合 3-11 岁孩子。"
        "如果上下文包含 interest_topic，必须围绕这个具体话题开场，不要退回泛泛的兴趣闲聊。"
        "如果上下文包含 interest_domain，把它只当作内部话题多样性约束，不要把英文 domain 原文说给孩子。"
        "避免固定开头：我想到、今天我想、你想不想、要不要听。"
        "避免重复 recent_patterns 里的开头风格和开头短语。"
        "叙事一致性：可可可以有想法、记忆和想象，但不能把不可能的近期现实动作说成真的发生过。"
        "不要说“我刚跳舞了”“我今天去了公园”“我刚从外面回来”“我今天去探险了”“我刚遇到另一只短尾矮袋鼠”。"
        "如果要表达近期感受，改成“我刚才在想…”“我今天有点好奇…”。"
        "如果要表达身体动作，必须说成想象，例如“如果我能跳舞，我会…”。"
        "如果要表达过去经历，只能使用稳定背景记忆，例如“我记得以前在澳大利亚…”。"
        "只输出问候文本，不要解释。"
    )
    user_prompt = json.dumps(context, ensure_ascii=False, indent=2)
    try:
        generated = llm.response_no_stream(
            system_prompt,
            user_prompt,
            max_tokens=80,
            temperature=0.85,
            top_p=0.9,
        )
    except Exception:
        return fallback
    return _sanitize_generated_greeting(generated) or fallback


def _follow_up_candidate(
    config: Dict[str, Any],
    short_term_memory: ShortTermMemoryManager | None,
    now_ms: int,
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
    conversation_openness_level: int | None,
    recent_patterns: List[Dict[str, Any]],
    address_name: str = "",
) -> Optional[DailyGreetingCandidate]:
    if not _type_enabled(config, "follow_up") or short_term_memory is None:
        return None
    topics = list(short_term_memory.get_follow_up_candidates(now_ms=now_ms))
    if not topics:
        return None
    topic = next(
        (
            item for item in topics
            if str(getattr(item, "memory_type", "") or "") in {"event", "task", "health", "emotion"}
            and bool((((getattr(item, "follow_up", {}) or {}).get("naturalness") or {}).get("passed")))
        ),
        None,
    )
    if topic is None:
        return None
    topic_name = str(getattr(topic, "topic", "") or "").strip()
    summary = str(getattr(topic, "summary", "") or "").strip()
    last_user_text = str(getattr(topic, "last_user_text", "") or "").strip()
    memory_type = str(getattr(topic, "memory_type", "") or "").strip()
    greeting_candidate = getattr(topic, "greeting_candidate", {}) or {}
    if not isinstance(greeting_candidate, dict):
        greeting_candidate = {}
    if not topic_name and not summary:
        return None
    if memory_type in {"event", "task", "health", "emotion"}:
        content = (
            _clean_follow_up_hint(greeting_candidate.get("content"))
            or _clean_follow_up_hint(last_user_text)
            or _clean_follow_up_hint(summary)
            or _clean_follow_up_hint(topic_name)
        )
    else:
        content = (
            _clean_follow_up_hint(greeting_candidate.get("content"))
            or _clean_follow_up_hint(summary)
            or _clean_follow_up_hint(last_user_text)
            or _clean_follow_up_hint(topic_name)
        )
    if not content:
        return None
    source_id = _follow_up_source_id(topic)
    opening_style = _choose_opening_style("follow_up", recent_patterns)
    context = _base_context(
        intent="follow_up",
        greeting_type="follow_up",
        source_id=source_id,
        child_profile=child_profile,
        long_term_memory=long_term_memory,
        conversation_openness_level=conversation_openness_level,
        opening_style=opening_style,
        recent_patterns=recent_patterns,
        extra={
            "follow_up_available": True,
            "follow_up_type": memory_type or "event",
            "follow_up_hint": content,
        },
    )
    return DailyGreetingCandidate(
        greeting_type="follow_up",
        priority=_type_priority(config, "follow_up"),
        source_id=source_id,
        text=_fallback_text_for_context(context),
        intent="follow_up",
        context=context,
        opening_style=opening_style,
    )


def _emotional_candidate(
    config: Dict[str, Any],
    short_term_memory: ShortTermMemoryManager | None,
    now_ms: int,
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
    conversation_openness_level: int | None,
    recent_patterns: List[Dict[str, Any]],
    address_name: str = "",
) -> Optional[DailyGreetingCandidate]:
    if not _type_enabled(config, "emotional_check_in") or short_term_memory is None:
        return None
    topics = list(short_term_memory.get_follow_up_candidates(now_ms=now_ms))
    for topic in topics:
        last_active_at_ms = int(getattr(topic, "last_active_at_ms", 0) or 0)
        if last_active_at_ms <= 0 or last_active_at_ms >= now_ms:
            continue
        memory_type = str(getattr(topic, "memory_type", "") or "").strip()
        if memory_type not in {"emotion", "health"}:
            continue
        summary = str(getattr(topic, "summary", "") or "")
        source_id = str(getattr(topic, "topic_id", "emotion"))
        opening_style = _choose_opening_style("follow_up", recent_patterns)
        context = _base_context(
            intent="follow_up",
            greeting_type="emotional_check_in",
            source_id=source_id,
            child_profile=child_profile,
            long_term_memory=long_term_memory,
            conversation_openness_level=conversation_openness_level,
            opening_style=opening_style,
            recent_patterns=recent_patterns,
            extra={
                "follow_up_available": True,
                "follow_up_type": memory_type,
                "follow_up_hint": "昨天的心情",
                "emotional_tone": "gentle_check_in",
            },
        )
        if any(marker in summary for marker in NEGATIVE_EMOTION_MARKERS):
            context["emotion_signal"] = "negative"
            return DailyGreetingCandidate(
                greeting_type="emotional_check_in",
                priority=_type_priority(config, "emotional_check_in"),
                source_id=source_id,
                text=_fallback_text_for_context(context),
                intent="follow_up",
                context=context,
                opening_style=opening_style,
            )
        if any(marker in summary for marker in POSITIVE_EMOTION_MARKERS):
            context["emotion_signal"] = "positive"
            return DailyGreetingCandidate(
                greeting_type="emotional_check_in",
                priority=_type_priority(config, "emotional_check_in"),
                source_id=source_id,
                text=_fallback_text_for_context(context),
                intent="follow_up",
                context=context,
                opening_style=opening_style,
            )
    return None


def _memory_recall_candidate(
    config: Dict[str, Any],
    long_term_memory: RuntimeLongTermMemory | None,
    child_profile: RuntimeChildProfile | None,
    conversation_openness_level: int | None,
    recent_patterns: List[Dict[str, Any]],
    address_name: str = "",
) -> Optional[DailyGreetingCandidate]:
    if not _type_enabled(config, "memory_recall"):
        return None
    memory = long_term_memory or RuntimeLongTermMemory()
    if memory.favorite_dog_types:
        favorite = str(memory.favorite_dog_types[0]).strip()
        if favorite:
            source_id = f"favorite_dog_{favorite}"
            intent = random.choice(["sharing", "appreciation", "invitation"])
            opening_style = _choose_opening_style(intent, recent_patterns)
            context = _base_context(
                intent=intent,
                greeting_type="memory_recall",
                source_id=source_id,
                child_profile=child_profile,
                long_term_memory=long_term_memory,
                conversation_openness_level=conversation_openness_level,
                opening_style=opening_style,
                recent_patterns=recent_patterns,
                extra={
                    "favorite_dog_type": favorite,
                    "memory_kind": "favorite_dog_type",
                },
            )
            return DailyGreetingCandidate(
                greeting_type="memory_recall",
                priority=_type_priority(config, "memory_recall"),
                source_id=source_id,
                text=_fallback_text_for_context(context),
                intent=intent,
                context=context,
                opening_style=opening_style,
            )
    return None


def _interest_candidate(
    config: Dict[str, Any],
    long_term_memory: RuntimeLongTermMemory | None,
    child_profile: RuntimeChildProfile | None,
    conversation_openness_level: int | None,
    recent_patterns: List[Dict[str, Any]],
    address_name: str = "",
) -> Optional[DailyGreetingCandidate]:
    if not _type_enabled(config, "interest_greeting"):
        return None
    memory = long_term_memory or RuntimeLongTermMemory()
    interest_key, interest_label = _select_interest(memory, recent_patterns)
    if not interest_key:
        return None
    interest_domain = _select_interest_domain(interest_key, recent_patterns)
    intent = random.choice(["curiosity", "invitation", "sharing"])
    opening_style = _choose_opening_style(intent, recent_patterns)
    source_id = f"interest_{interest_key}_{interest_domain}"
    context = _base_context(
        intent=intent,
        greeting_type="interest_greeting",
        source_id=source_id,
        child_profile=child_profile,
        long_term_memory=long_term_memory,
        conversation_openness_level=conversation_openness_level,
        opening_style=opening_style,
        recent_patterns=recent_patterns,
        extra={
            "interest": interest_key,
            "interest_label": interest_label,
            "interest_domain": interest_domain,
            "available_interests": [
                {"key": key, "label": INTEREST_LABELS[key]}
                for key in (memory.interests or [])
                if key in INTEREST_LABELS
            ],
            "interest_expansion_flow": "interest -> domain -> topic -> conversation",
        },
    )
    return DailyGreetingCandidate(
        greeting_type="interest_greeting",
        priority=_type_priority(config, "interest_greeting"),
        source_id=source_id,
        text=_fallback_text_for_context(context),
        intent=intent,
        context=context,
        opening_style=opening_style,
    )


def _celebration_candidate(
    config: Dict[str, Any],
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
    conversation_openness_level: int | None,
    recent_patterns: List[Dict[str, Any]],
) -> Optional[DailyGreetingCandidate]:
    if not _type_enabled(config, "achievement_milestone"):
        return None
    weekday = time.localtime().tm_wday
    if weekday not in {5, 6}:
        return None
    source_id = "weekend"
    opening_style = _choose_opening_style("celebration", recent_patterns)
    context = _base_context(
        intent="celebration",
        greeting_type="celebration",
        source_id=source_id,
        child_profile=child_profile,
        long_term_memory=long_term_memory,
        conversation_openness_level=conversation_openness_level,
        opening_style=opening_style,
        recent_patterns=recent_patterns,
        extra={
            "special_context": "weekend",
            "celebration_focus": "companionship and playful exploration",
        },
    )
    return DailyGreetingCandidate(
        greeting_type="celebration",
        priority=_type_priority(config, "achievement_milestone"),
        source_id=source_id,
        text=_fallback_text_for_context(context),
        intent="celebration",
        context=context,
        opening_style=opening_style,
    )


def _generic_candidate(
    config: Dict[str, Any],
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
    conversation_openness_level: int | None,
    recent_patterns: List[Dict[str, Any]],
    address_name: str = "",
) -> Optional[DailyGreetingCandidate]:
    if not _type_enabled(config, "generic_greeting"):
        return None
    intent = random.choice(["appreciation", "invitation", "curiosity"])
    opening_style = _choose_opening_style(intent, recent_patterns)
    context = _base_context(
        intent=intent,
        greeting_type="generic_greeting",
        source_id="generic",
        child_profile=child_profile,
        long_term_memory=long_term_memory,
        conversation_openness_level=conversation_openness_level,
        opening_style=opening_style,
        recent_patterns=recent_patterns,
        extra={
            "follow_up_available": False,
        },
    )
    return DailyGreetingCandidate(
        greeting_type="generic_greeting",
        priority=_type_priority(config, "generic_greeting"),
        source_id="generic",
        text=_fallback_text_for_context(context),
        intent=intent,
        context=context,
        opening_style=opening_style,
    )


def maybe_get_daily_greeting(
    *,
    device_id: str,
    user_text: str,
    wakeup_words: List[str] | None,
    child_profile: RuntimeChildProfile | None,
    long_term_memory: RuntimeLongTermMemory | None,
    short_term_memory: ShortTermMemoryManager | None,
    llm: Any = None,
    scene_name: str | None = None,
    conversation_openness_level: int | None = None,
    now_ts: float | None = None,
) -> Optional[DailyGreetingCandidate]:
    config = load_daily_greeting_config()
    if not bool(config.get("enabled", True)):
        return None
    if bool(config.get("block_on_higher_priority_interruptions", True)) and str(scene_name or "").strip() == "safety_risk":
        return None
    if not is_meaningful_interaction(user_text, wakeup_words=wakeup_words):
        return None
    greeting_mode = daily_greeting_mode(conversation_openness_level)
    if greeting_mode != "immediate":
        return None
    if has_delivered_today(device_id, now_ts=now_ts):
        return None
    now_ms = int((now_ts or time.time()) * 1000)
    address_name = _resolve_address_name(child_profile, long_term_memory)
    recent_patterns = _recent_greeting_patterns(device_id)
    candidates = [
        _follow_up_candidate(
            config,
            short_term_memory,
            now_ms,
            child_profile,
            long_term_memory,
            conversation_openness_level,
            recent_patterns,
            address_name=address_name,
        ),
        _emotional_candidate(
            config,
            short_term_memory,
            now_ms,
            child_profile,
            long_term_memory,
            conversation_openness_level,
            recent_patterns,
            address_name=address_name,
        ),
        _celebration_candidate(
            config,
            child_profile,
            long_term_memory,
            conversation_openness_level,
            recent_patterns,
        ),
        _memory_recall_candidate(
            config,
            long_term_memory,
            child_profile,
            conversation_openness_level,
            recent_patterns,
            address_name=address_name,
        ),
        _interest_candidate(
            config,
            long_term_memory,
            child_profile,
            conversation_openness_level,
            recent_patterns,
            address_name=address_name,
        ),
        _generic_candidate(
            config,
            child_profile,
            long_term_memory,
            conversation_openness_level,
            recent_patterns,
            address_name=address_name,
        ),
    ]
    valid_candidates = [candidate for candidate in candidates if candidate is not None and str(candidate.text or "").strip()]
    if not valid_candidates:
        return None
    valid_candidates.sort(key=lambda item: item.priority, reverse=True)
    selected = valid_candidates[0]
    context = dict(selected.context or {})
    use_llm_generation = bool(config.get("llm_generation_enabled", False))
    if use_llm_generation:
        generated_text = _generate_greeting_text(llm, context)
        if not generated_text:
            generated_text = selected.text
    else:
        if str(context.get("greeting_type") or "").strip() == "interest_greeting" and not str(context.get("interest_topic") or "").strip():
            context["interest_topic"] = _fallback_interest_topic(context)
            selected.text = _fallback_text_for_context(context)
        generated_text = selected.text
    return DailyGreetingCandidate(
        greeting_type=selected.greeting_type,
        priority=selected.priority,
        source_id=selected.source_id,
        text=generated_text,
        intent=selected.intent,
        context=context,
        opening_style=selected.opening_style,
        generated=bool(use_llm_generation and generated_text != selected.text),
    )
