from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict

from core.interest_key_normalizer import normalize_interest_key, normalize_interest_keys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
AGE_PROFILE_PATH = os.path.join(DATA_DIR, "age_profiles.json")
INTERACTION_POLICY_PATH = os.path.join(DATA_DIR, "scene_interaction_policies.json")
INTERESTS_CONFIG_PATH = os.path.join(DATA_DIR, "interest_influence.json")
SCENE_INTEREST_CONFIG_PATH = os.path.join(DATA_DIR, "scene_interest_config.json")


DEFAULT_AGE_PROFILES: Dict[str, Dict[str, Any]] = {
    "3-5": {
        "vocabulary_level": "very_simple",
        "max_new_concepts": 2,
        "abstract_concept_level": "none",
        "question_style": "observation",
        "support_level": "high",
    },
    "6-8": {
        "vocabulary_level": "simple",
        "max_new_concepts": 4,
        "abstract_concept_level": "limited",
        "question_style": "exploration",
        "support_level": "medium_high",
    },
    "9-11": {
        "vocabulary_level": "age_appropriate",
        "max_new_concepts": 6,
        "abstract_concept_level": "allowed",
        "question_style": "discussion",
        "support_level": "medium",
    },
}


DEFAULT_INTERACTION_POLICY: Dict[str, Any] = {
    "information_budget": "medium",
    "reasoning_depth": 2,
    "interaction_style": "exploration",
    "conversation_pacing": "balanced",
    "emotional_priority": "medium",
}


SCENE_INTERACTION_POLICY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "safety_risk": {
        "information_budget": "low",
        "reasoning_depth": 1,
        "interaction_style": "observation",
        "conversation_pacing": "progressive",
        "emotional_priority": "high",
    },
    "emotion_support": {
        "information_budget": "low",
        "reasoning_depth": 1,
        "interaction_style": "exploration",
        "conversation_pacing": "progressive",
        "emotional_priority": "high",
    },
    "curiosity": {
        "information_budget": "medium",
        "reasoning_depth": 2,
        "interaction_style": "exploration",
        "conversation_pacing": "balanced",
        "emotional_priority": "medium",
    },
    "learning_support": {
        "information_budget": "low",
        "reasoning_depth": 1,
        "interaction_style": "observation",
        "conversation_pacing": "progressive",
        "emotional_priority": "high",
    },
    "play_interaction": {
        "information_budget": "low",
        "reasoning_depth": 1,
        "interaction_style": "observation",
        "conversation_pacing": "balanced",
        "emotional_priority": "medium",
    },
    "system_repair": {
        "information_budget": "low",
        "reasoning_depth": 1,
        "interaction_style": "discussion",
        "conversation_pacing": "progressive",
        "emotional_priority": "medium",
    },
    "relationship_building": {
        "information_budget": "low",
        "reasoning_depth": 1,
        "interaction_style": "observation",
        "conversation_pacing": "balanced",
        "emotional_priority": "high",
    },
}


DEFAULT_INTEREST_TOPICS = [
    {"key": "animals", "label": "🐶 小动物"},
    {"key": "dinosaurs", "label": "🦖 恐龙"},
    {"key": "space", "label": "🚀 太空"},
    {"key": "vehicles", "label": "🚗 汽车和交通工具"},
    {"key": "nature", "label": "🌳 大自然"},
    {"key": "sports", "label": "⚽ 运动"},
    {"key": "art_and_crafts", "label": "🎨 画画和手工"},
    {"key": "music_and_dance", "label": "🎵 音乐和跳舞"},
    {"key": "stories_and_picture_books", "label": "📚 故事和绘本"},
    {"key": "riddles_and_games", "label": "🧩 猜谜和小游戏"},
]


DEFAULT_INTEREST_INFLUENCE_POLICY: Dict[str, str] = {
    "example_bias": "high",
    "story_bias": "high",
    "conversation_bias": "medium",
    "game_bias": "medium",
    "memory_reference": "occasionally",
}


DEFAULT_INTEREST_ADAPTER: Dict[str, Dict[str, Any]] = {
    "animals": {
        "domains": [
            "fun_facts",
            "behaviors",
            "habitats",
            "comparisons",
            "emotions",
            "imagination",
            "stories",
            "games",
            "conservation",
            "science",
        ],
        "example_context": ["pets", "mammals", "wildlife"],
        "story_context": ["animal_adventure", "friendship", "caring_for_animals"],
        "conversation_context": ["animal_facts", "zoos", "animal_behaviors"],
        "game_context": ["animal_guessing", "animal_quiz"],
    },
    "dinosaurs": {
        "domains": [
            "species",
            "fossils",
            "behaviors",
            "extinction",
            "imagination",
            "comparisons",
            "habitats",
            "science",
        ],
        "example_context": ["dinosaur_species", "fossils"],
        "story_context": ["dinosaur_adventure", "time_travel"],
        "conversation_context": ["dinosaur_facts", "paleontology"],
        "game_context": ["dinosaur_quiz"],
    },
    "space": {
        "domains": [
            "fun_facts",
            "planets",
            "astronauts",
            "rockets",
            "imagination",
            "future",
            "mysteries",
            "science",
        ],
        "example_context": ["planets", "rockets", "astronauts"],
        "story_context": ["space_adventure", "exploration", "missions"],
        "conversation_context": ["astronomy", "planets", "space_facts"],
        "game_context": ["space_quiz", "planet_guessing"],
    },
    "vehicles": {
        "domains": [
            "how_it_moves",
            "design",
            "speed",
            "jobs",
            "history",
            "future",
            "safety",
            "imagination",
            "comparisons",
        ],
        "example_context": ["cars", "transportation", "traffic_tools"],
        "story_context": ["travel_adventure", "rescue_missions", "city_journeys"],
        "conversation_context": ["vehicle_facts", "transportation", "how_things_move"],
        "game_context": ["vehicle_guessing", "traffic_quiz"],
    },
    "nature": {
        "domains": [
            "plants",
            "weather",
            "seasons",
            "habitats",
            "ecosystems",
            "observation",
            "conservation",
            "imagination",
            "science",
        ],
        "example_context": ["plants", "weather", "outdoors"],
        "story_context": ["forest_adventure", "exploration", "nature_friendship"],
        "conversation_context": ["nature_facts", "seasons", "outdoor_observation"],
        "game_context": ["nature_quiz", "outdoor_guessing"],
    },
    "sports": {
        "domains": [
            "skills",
            "teamwork",
            "practice",
            "body",
            "rules",
            "strategy",
            "feelings",
            "games",
            "comparisons",
        ],
        "example_context": ["games", "movement", "teamwork"],
        "story_context": ["sports_challenge", "teamwork", "practice_growth"],
        "conversation_context": ["sports_facts", "movement", "competition"],
        "game_context": ["sports_quiz", "movement_guessing"],
    },
    "art_and_crafts": {
        "domains": [
            "techniques",
            "colors",
            "creativity",
            "materials",
            "challenges",
            "observation",
            "imagination",
            "projects",
        ],
        "example_context": ["colors", "making_things", "creative_tools"],
        "story_context": ["creative_adventure", "making_projects", "art_friendship"],
        "conversation_context": ["art_ideas", "craft_materials", "creative_process"],
        "game_context": ["art_guessing", "craft_quiz"],
    },
    "music_and_dance": {
        "domains": [
            "rhythm",
            "instruments",
            "movement",
            "feelings",
            "creativity",
            "performance",
            "patterns",
            "games",
        ],
        "example_context": ["rhythm", "songs", "movement"],
        "story_context": ["music_adventure", "dance_party", "performance_fun"],
        "conversation_context": ["music_facts", "instruments", "rhythm_patterns"],
        "game_context": ["music_quiz", "rhythm_guessing"],
    },
    "stories_and_picture_books": {
        "domains": [
            "characters",
            "story_worlds",
            "plot",
            "feelings",
            "imagination",
            "pictures",
            "choices",
            "endings",
        ],
        "example_context": ["characters", "story_worlds", "picture_books"],
        "story_context": ["storybook_adventure", "imagination", "friendship"],
        "conversation_context": ["story_talk", "book_characters", "plot_curiosity"],
        "game_context": ["story_quiz", "character_guessing"],
    },
    "riddles_and_games": {
        "domains": [
            "logic",
            "patterns",
            "clues",
            "memory",
            "wordplay",
            "strategy",
            "mini_games",
            "challenges",
        ],
        "example_context": ["patterns", "clues", "playful_logic"],
        "story_context": ["puzzle_adventure", "mystery_fun", "problem_solving"],
        "conversation_context": ["riddle_talk", "mini_games", "playful_thinking"],
        "game_context": ["riddle_quiz", "guessing_game"],
    },
}


DEFAULT_SCENE_INTEREST_CONFIGS: Dict[str, Dict[str, bool]] = {
    "safety_risk": {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": False,
    },
    "emotion_support": {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": False,
    },
    "curiosity": {
        "use_interest_examples": True,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": False,
    },
    "learning_support": {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": False,
    },
    "play_interaction": {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": True,
        "use_interest_conversation": False,
    },
    "system_repair": {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": False,
    },
    "relationship_building": {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": True,
    },
}


INTEREST_CAPABILITY_CONTEXT_MAP: Dict[str, tuple[str, str]] = {
    "use_interest_examples": ("example_context", "example_bias"),
    "use_interest_story": ("story_context", "story_bias"),
    "use_interest_games": ("game_context", "game_bias"),
    "use_interest_conversation": ("conversation_context", "conversation_bias"),
}


def _load_json_file(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _normalize_age_profile(age_group: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    defaults = dict(DEFAULT_AGE_PROFILES.get(age_group) or DEFAULT_AGE_PROFILES["6-8"])
    merged = dict(defaults)
    incoming = raw if isinstance(raw, dict) else {}
    for key in defaults.keys():
        if key not in incoming:
            continue
        if key == "max_new_concepts":
            try:
                merged[key] = max(1, min(12, int(incoming[key])))
            except (TypeError, ValueError):
                continue
            continue
        value = str(incoming[key] or "").strip()
        if value:
            merged[key] = value
    return merged


def _normalize_interaction_policy(scene_name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    defaults = dict(SCENE_INTERACTION_POLICY_DEFAULTS.get(scene_name) or DEFAULT_INTERACTION_POLICY)
    merged = dict(defaults)
    incoming = raw if isinstance(raw, dict) else {}
    for key in defaults.keys():
        if key not in incoming:
            continue
        if key == "reasoning_depth":
            try:
                merged[key] = max(1, min(3, int(incoming[key])))
            except (TypeError, ValueError):
                continue
            continue
        value = str(incoming[key] or "").strip()
        if value:
            merged[key] = value
    return merged


def _normalize_interest_context_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        value = str(value or "").split(",")
    normalized: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_interest_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    config = {
        "favorite_topics": list(DEFAULT_INTEREST_TOPICS),
        "interest_influence": dict(DEFAULT_INTEREST_INFLUENCE_POLICY),
        "interest_adapter": json.loads(json.dumps(DEFAULT_INTEREST_ADAPTER, ensure_ascii=False)),
    }
    if not isinstance(raw, dict):
        return config

    topics = raw.get("favorite_topics")
    if isinstance(topics, list):
        normalized_topics = []
        for item in topics:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            label = str(item.get("label") or "").strip()
            if key and label:
                normalized_topics.append({"key": key, "label": label})
        if normalized_topics:
            config["favorite_topics"] = normalized_topics

    incoming_policy = raw.get("interest_influence")
    if isinstance(incoming_policy, dict):
        merged_policy = dict(DEFAULT_INTEREST_INFLUENCE_POLICY)
        for key in DEFAULT_INTEREST_INFLUENCE_POLICY.keys():
            value = str(incoming_policy.get(key) or "").strip()
            if value:
                merged_policy[key] = value
        config["interest_influence"] = merged_policy

    incoming_adapter = raw.get("interest_adapter")
    if isinstance(incoming_adapter, dict):
        merged_adapter = json.loads(json.dumps(DEFAULT_INTEREST_ADAPTER, ensure_ascii=False))
        for topic_key, defaults in DEFAULT_INTEREST_ADAPTER.items():
            incoming_topic = incoming_adapter.get(topic_key)
            if not isinstance(incoming_topic, dict):
                continue
            merged_topic = dict(defaults)
            for field_name in defaults.keys():
                if field_name not in incoming_topic:
                    continue
                merged_topic[field_name] = _normalize_interest_context_list(
                    incoming_topic.get(field_name)
                )
            merged_adapter[topic_key] = merged_topic
        config["interest_adapter"] = merged_adapter
    return config


def _normalize_scene_interest_config(scene_name: str, raw: Dict[str, Any]) -> Dict[str, bool]:
    defaults = dict(DEFAULT_SCENE_INTEREST_CONFIGS.get(scene_name) or {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": False,
    })
    merged = dict(defaults)
    incoming = raw if isinstance(raw, dict) else {}
    for key in defaults.keys():
        if key not in incoming:
            continue
        merged[key] = bool(incoming[key])
    return merged


@lru_cache(maxsize=1)
def _get_age_profiles_snapshot() -> Dict[str, Dict[str, Any]]:
    raw = _load_json_file(AGE_PROFILE_PATH)
    return {
        age_group: _normalize_age_profile(age_group, raw.get(age_group) or {})
        for age_group in DEFAULT_AGE_PROFILES.keys()
    }


@lru_cache(maxsize=1)
def _get_interaction_policy_snapshot() -> Dict[str, Dict[str, Any]]:
    raw = _load_json_file(INTERACTION_POLICY_PATH)
    merged: Dict[str, Dict[str, Any]] = {}
    for scene_name in SCENE_INTERACTION_POLICY_DEFAULTS.keys():
        merged[scene_name] = _normalize_interaction_policy(scene_name, raw.get(scene_name) or {})
    for scene_name, scene_value in raw.items():
        if scene_name not in merged and isinstance(scene_value, dict):
            merged[scene_name] = _normalize_interaction_policy(scene_name, scene_value)
    return merged


@lru_cache(maxsize=1)
def _get_interest_config_snapshot() -> Dict[str, Any]:
    raw = _load_json_file(INTERESTS_CONFIG_PATH)
    return _normalize_interest_config(raw)


@lru_cache(maxsize=1)
def _get_scene_interest_config_snapshot() -> Dict[str, Dict[str, bool]]:
    raw = _load_json_file(SCENE_INTEREST_CONFIG_PATH)
    merged: Dict[str, Dict[str, bool]] = {}
    for scene_name in DEFAULT_SCENE_INTEREST_CONFIGS.keys():
        merged[scene_name] = _normalize_scene_interest_config(scene_name, raw.get(scene_name) or {})
    for scene_name, scene_value in raw.items():
        if scene_name not in merged and isinstance(scene_value, dict):
            merged[scene_name] = _normalize_scene_interest_config(scene_name, scene_value)
    return merged


def refresh_runtime_generation_config_cache() -> None:
    _get_age_profiles_snapshot.cache_clear()
    _get_interaction_policy_snapshot.cache_clear()
    _get_interest_config_snapshot.cache_clear()
    _get_scene_interest_config_snapshot.cache_clear()


def get_age_profile(age_group: str | None) -> Dict[str, Any]:
    normalized = (age_group or "6-8").strip() or "6-8"
    profiles = _get_age_profiles_snapshot()
    return dict(profiles.get(normalized) or profiles["6-8"])


def get_interaction_policy(scene_name: str | None) -> Dict[str, Any]:
    normalized = (scene_name or "").strip()
    policies = _get_interaction_policy_snapshot()
    if normalized in policies:
        return dict(policies[normalized])
    return dict(DEFAULT_INTERACTION_POLICY)


def get_interest_config() -> Dict[str, Any]:
    snapshot = _get_interest_config_snapshot()
    return {
        "favorite_topics": list(snapshot.get("favorite_topics") or []),
        "interest_influence": dict(snapshot.get("interest_influence") or {}),
        "interest_adapter": json.loads(
            json.dumps(snapshot.get("interest_adapter") or {}, ensure_ascii=False)
        ),
    }


def get_scene_interest_config(scene_name: str | None) -> Dict[str, bool]:
    normalized = (scene_name or "").strip()
    configs = _get_scene_interest_config_snapshot()
    if normalized in configs:
        return dict(configs[normalized])
    return _normalize_scene_interest_config(normalized, {})


def get_interest_generation_context(
    scene_name: str | None,
    favorite_topics: list[str] | None,
) -> Dict[str, Any]:
    config = _get_interest_config_snapshot()
    normalized_scene = str(scene_name or "").strip()
    normalized_topics = normalize_interest_keys(favorite_topics or [])
    if not normalized_topics:
        return {
            "favorite_topics": [],
            "interest_influence": dict(config.get("interest_influence") or {}),
            "contexts": {},
        }

    adapter = config.get("interest_adapter") or {}
    influence = dict(config.get("interest_influence") or {})
    scene_interest_config = get_scene_interest_config(normalized_scene)
    contexts: Dict[str, list[str]] = {}

    for capability_key, (context_type, policy_field) in INTEREST_CAPABILITY_CONTEXT_MAP.items():
        if not scene_interest_config.get(capability_key):
            continue
        if str(influence.get(policy_field) or "off").strip() == "off":
            continue
        merged_items: list[str] = []
        for topic in normalized_topics:
            topic_adapter = adapter.get(normalize_interest_key(topic))
            if not isinstance(topic_adapter, dict):
                continue
            for item in topic_adapter.get(context_type) or []:
                text = str(item or "").strip()
                if text and text not in merged_items:
                    merged_items.append(text)
        if merged_items:
            contexts[context_type] = merged_items

    return {
        "favorite_topics": normalized_topics,
        "interest_influence": influence,
        "scene_interest_config": scene_interest_config,
        "contexts": contexts,
    }
