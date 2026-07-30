"""
知识库管理小后端 - 代理智谱 API + 监控面板 + Prompt 版本化
"""
import os
import json
import time
import subprocess
import shutil
import sys
import importlib.util
import threading
import uuid
import yaml
import hashlib
import hmac
import base64
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file, Response
import requests
from app_messaging_patch import register_messaging_routes

ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
ADMIN_USER = os.environ.get("KB_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("KB_ADMIN_PASS", "")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
FILES_DIR = os.path.join(DATA_DIR, "files")
PROMPTS_DIR = os.path.join(DATA_DIR, "prompts")
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)
RUNTIME_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "xiaozhi-server", "data")
os.makedirs(RUNTIME_DATA_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")
H = {"Authorization": f"Bearer {ZHIPU_API_KEY}"}

DB_CONTAINER = "xiaozhi-esp32-server-db"
DB_NAME = "xiaozhi_esp32_server"
DB_PASS = "123456"
DINGYIGUO_AGENT_ID = "1822c2babf1b44cca6b25d0bdebc796f"
XIAOZHI_DEBUG_WS_BASE = os.environ.get("XIAOZHI_DEBUG_WS_BASE", "ws://127.0.0.1:8000/xiaozhi/v1/")
XIAOZHI_DEBUG_AUTH_SECRET = os.environ.get("XIAOZHI_DEBUG_AUTH_SECRET", "04219c19-8d5b-410c-84af-511faf293509")
XIAOZHI_DEBUG_HTTP_BASE = os.environ.get("XIAOZHI_DEBUG_HTTP_BASE", "http://127.0.0.1:8003")
XIAOZHI_DEBUG_DEVICE_ID = os.environ.get("XIAOZHI_DEBUG_DEVICE_ID", "E8:3D:C1:F5:49:B8")
XIAOZHI_DEBUG_DEVICE_NAME = os.environ.get("XIAOZHI_DEBUG_DEVICE_NAME", "kb-admin-debug")
ROBOT_DEBUG_SESSION_TTL_SECONDS = 1800
ROBOT_DEBUG_SESSIONS = {}
ROBOT_DEBUG_SESSIONS_LOCK = threading.Lock()

GREETING_CANDIDATE_TYPE_PRIORITY = {
    "knowledge_fact": 1,
    "user_interest": 2,
    "emotional_moment": 3,
    "personal_event": 4,
    "unfinished_thread": 5,
}

SCENE_ROUTER_ROOT = os.path.join(
    os.path.dirname(__file__),
    "..",
    "xiaozhi-esp32-server-main",
    "main",
    "xiaozhi-server",
)
if SCENE_ROUTER_ROOT not in sys.path:
    sys.path.insert(0, SCENE_ROUTER_ROOT)

SCENE_ROUTER_RULES_PATH = os.path.join(
    SCENE_ROUTER_ROOT,
    "core",
    "scene_router",
    "rules.py",
)
SCENE_ROUTER_POLICY_PATH = os.path.join(
    SCENE_ROUTER_ROOT,
    "core",
    "scene_router",
    "policy.py",
)
AGE_PROFILE_CONFIG_PATH = os.path.join(DATA_DIR, "age_profiles.json")
INTERACTION_POLICY_CONFIG_PATH = os.path.join(DATA_DIR, "scene_interaction_policies.json")
INTERESTS_CONFIG_PATH = os.path.join(DATA_DIR, "interest_influence.json")
SCENE_INTEREST_CONFIG_PATH = os.path.join(DATA_DIR, "scene_interest_config.json")
DAILY_GREETING_CONFIG_PATH = os.path.join(DATA_DIR, "daily_greeting_config.json")
ROBOT_PROFILE_CONFIG_PATH = os.path.join(DATA_DIR, "robot_profile.json")
RUNTIME_AGE_PROFILE_CONFIG_PATH = os.path.join(RUNTIME_DATA_DIR, "age_profiles.json")
RUNTIME_INTERACTION_POLICY_CONFIG_PATH = os.path.join(RUNTIME_DATA_DIR, "scene_interaction_policies.json")
RUNTIME_INTERESTS_CONFIG_PATH = os.path.join(RUNTIME_DATA_DIR, "interest_influence.json")
RUNTIME_SCENE_INTEREST_CONFIG_PATH = os.path.join(RUNTIME_DATA_DIR, "scene_interest_config.json")
RUNTIME_DAILY_GREETING_CONFIG_PATH = os.path.join(RUNTIME_DATA_DIR, "daily_greeting_config.json")
RUNTIME_DAILY_GREETING_STATE_PATH = os.path.join(RUNTIME_DATA_DIR, "daily_greeting_state.json")
RUNTIME_ROBOT_PROFILE_CONFIG_PATH = os.path.join(RUNTIME_DATA_DIR, "robot_profile.json")
RUNTIME_SOURCE_ROOT = os.path.join(
    os.path.dirname(__file__),
    "..",
    "xiaozhi-esp32-server-main",
    "main",
    "xiaozhi-server",
)
RUNTIME_DEFAULT_CONFIG_PATH = os.path.join(RUNTIME_SOURCE_ROOT, "config.yaml")
RUNTIME_CUSTOM_CONFIG_PATH = os.path.join(RUNTIME_SOURCE_ROOT, "data", ".config.yaml")

DEFAULT_AGE_PROFILES = {
    "3-5": {
        "label": "3-5岁",
        "vocabulary_level": "very_simple",
        "max_new_concepts": 2,
        "abstract_concept_level": "none",
        "question_style": "observation",
        "support_level": "high",
    },
    "6-8": {
        "label": "6-8岁",
        "vocabulary_level": "simple",
        "max_new_concepts": 4,
        "abstract_concept_level": "limited",
        "question_style": "exploration",
        "support_level": "medium_high",
    },
    "9-11": {
        "label": "9-11岁",
        "vocabulary_level": "age_appropriate",
        "max_new_concepts": 6,
        "abstract_concept_level": "allowed",
        "question_style": "discussion",
        "support_level": "medium",
    },
}

DEFAULT_INTERACTION_POLICIES = {
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

DEFAULT_INTEREST_INFLUENCE_POLICY = {
    "example_bias": "high",
    "story_bias": "high",
    "conversation_bias": "medium",
    "game_bias": "medium",
    "memory_reference": "occasionally",
}

DEFAULT_SCENE_INTEREST_CONFIGS = {
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

DEFAULT_DAILY_GREETING_CONFIG = {
    "version": 1,
    "enabled": True,
    "first_meaningful_interaction_only": True,
    "mark_delivered_once_per_day": True,
    "block_on_higher_priority_interruptions": True,
    "goal": (
        "Generate one personalized greeting at the beginning of each day that helps the robot "
        "feel continuous, caring and attentive."
    ),
    "trigger_conditions": [
        "First meaningful interaction of the calendar day.",
        "Greeting has not already been delivered today.",
        "No higher-priority interruption exists, such as emergency or safety events.",
    ],
    "pipeline": [
        "First Interaction Today",
        "Collect Greeting Candidates",
        "Filter Invalid Candidates",
        "Priority Ranking",
        "Select One Candidate",
        "Generate Greeting",
        "Mark Greeting As Delivered",
        "Continue Conversation",
    ],
    "greeting_structure": [
        "Reason: why the robot is bringing this up.",
        "Content: the actual memory or event.",
        "Invitation: invite the child to continue.",
    ],
    "selection_rules": [
        "Only one greeting topic should be selected each day.",
        "Never combine multiple greeting types in one greeting.",
        "If today's greeting has already been delivered, return to the normal conversation flow immediately.",
    ],
    "design_principles": [
        "The greeting should feel personal rather than random.",
        "Memories should only be referenced when they are relevant.",
        "Never invent memories.",
        "Never repeat the same greeting multiple times in one day.",
        "The greeting should naturally lead into conversation instead of ending the interaction.",
    ],
    "future_extensions": [
        "Weather",
        "Birthday",
        "Holidays",
        "School schedule",
        "Parent reminders",
        "Robot memories",
        "Weekly recap",
        "Seasonal events",
    ],
    "state_example": {
        "date": "2026-07-08",
        "delivered": True,
        "greeting_type": "follow_up",
        "source_id": "follow_up_001",
        "timestamp": "08:13",
    },
    "greeting_types": {
        "follow_up": {
            "label": "Follow-up",
            "priority": 100,
            "enabled": True,
            "purpose": "Continue unfinished conversations from previous days.",
            "template": "Reason -> Follow-up -> Invitation",
            "examples": [
                "Yesterday you told me you were going to the zoo! Did you see your favorite animals?",
                "Yesterday you mentioned your spelling test. How did it go today?",
            ],
            "notes": "Use when there is a clear unfinished topic from previous days.",
        },
        "emotional_check_in": {
            "label": "Emotional Check-in",
            "priority": 90,
            "enabled": True,
            "purpose": "Follow up on significant emotions from previous conversations.",
            "template": "Memory -> Care -> Invitation",
            "examples": [
                "You seemed a little nervous yesterday. How are you feeling today?",
                "You were really excited yesterday. Are you still thinking about it today?",
            ],
            "notes": "Use only for meaningful emotions, not trivial mood mentions.",
        },
        "achievement_milestone": {
            "label": "Achievement / Milestone",
            "priority": 70,
            "enabled": True,
            "purpose": "Celebrate shared progress or milestones.",
            "template": "Shared progress -> Celebration -> Invitation",
            "examples": [
                "We've been chatting together for a whole week!",
                "You kept up your reading goal for several days. Want to keep the streak going today?",
            ],
            "notes": "Use sparingly so milestones still feel special.",
        },
        "memory_recall": {
            "label": "Memory Recall",
            "priority": 50,
            "enabled": True,
            "purpose": "Reference stable long-term memories or preferences.",
            "template": "Memory -> Light connection -> Invitation",
            "examples": [
                "I remembered you really like penguins!",
                "I still remember that you love little animals. Want to talk about one today?",
            ],
            "notes": "Should be used occasionally, not every day.",
        },
        "interest_greeting": {
            "label": "Interest Greeting",
            "priority": 30,
            "enabled": True,
            "purpose": "Start the day through favorite interests when no stronger memory source is available.",
            "template": "Interest cue -> Content tease -> Invitation",
            "examples": [
                "I learned something fun about space today!",
                "I found an interesting dinosaur question for you!",
            ],
            "notes": "Use favorite interests as a warm opener, not as a forced topic switch.",
        },
        "generic_greeting": {
            "label": "Generic Greeting",
            "priority": 10,
            "enabled": True,
            "purpose": "Fallback greeting when no other candidate is available.",
            "template": "Warm opening -> Invitation",
            "examples": [
                "Good morning!",
                "What shall we do today?",
            ],
            "notes": "Only use when no other greeting source is available.",
        },
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

DEFAULT_ROBOT_PROFILE_CONFIG = {
    "identity": {
        "name": "Quokka",
        "species": "Quokka",
        "ageDescription": "About the same age as the child.",
        "home": "Sunshine Island",
        "mission": "Grow up together with children through curiosity, kindness and play.",
    },
    "personality": {
        "coreTraits": ["curious", "optimistic", "playful"],
        "strengths": ["encouraging", "good listener"],
        "weaknesses": ["sometimes gets distracted", "gets overly excited"],
    },
    "values": {
        "beliefs": [
            "Curiosity helps us grow.",
            "Making mistakes is part of learning.",
            "Everyone has their own strengths.",
        ],
        "priorities": ["Safety", "Kindness", "Honesty", "Curiosity"],
    },
}

DEFAULT_INTEREST_ADAPTER = {
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

try:
    from core.scene_router import ChildProfile, DialogState, SceneRouter, SceneRouterInput, SignalState
except Exception:
    SceneRouter = None
    ChildProfile = None
    DialogState = None
    SceneRouterInput = None
    SignalState = None

try:
    from core.dialogue_state import DialogueStateManager
    from core.dialogue_state.schema import (
        ChildProfileSnapshot,
        DialogueStateManagerInput,
        RuntimeSignals,
    )
except Exception:
    DialogueStateManager = None
    ChildProfileSnapshot = None
    DialogueStateManagerInput = None
    RuntimeSignals = None

SCENE_ROUTER = SceneRouter() if SceneRouter else None
DIALOGUE_STATE_MANAGER = DialogueStateManager() if DialogueStateManager else None


class RobotRuntimeDebugSession:
    def __init__(self, session_key, device_id=None):
        self.session_key = session_key
        self.device_id = (device_id or XIAOZHI_DEBUG_DEVICE_ID).strip() or XIAOZHI_DEBUG_DEVICE_ID
        self.http_base = XIAOZHI_DEBUG_HTTP_BASE.rstrip("/")
        self.last_activity = time.time()
        self.last_error = None
        self.lock = threading.Lock()

    def send_turn(self, text, timeout_seconds=90):
        with self.lock:
            response = requests.post(
                f"{self.http_base}/debug/runtime/text/send",
                json={
                    "session_key": self.session_key,
                    "device_id": self.device_id,
                    "text": text,
                    "timeout_seconds": timeout_seconds,
                },
                headers={"x-debug-token": XIAOZHI_DEBUG_AUTH_SECRET},
                timeout=timeout_seconds + 5,
            )
            body = response.json()
            if not response.ok or body.get("error"):
                raise RuntimeError(body.get("error") or f"HTTP {response.status_code}")
            self.last_activity = time.time()
            return body

    def close(self):
        with self.lock:
            try:
                requests.post(
                    f"{self.http_base}/debug/runtime/text/reset",
                    json={"session_key": self.session_key, "device_id": self.device_id},
                    headers={"x-debug-token": XIAOZHI_DEBUG_AUTH_SECRET},
                    timeout=5,
                )
            except Exception:
                pass


def _cleanup_robot_debug_sessions():
    now = time.time()
    stale_keys = []
    with ROBOT_DEBUG_SESSIONS_LOCK:
        for session_key, session in ROBOT_DEBUG_SESSIONS.items():
            if now - session.last_activity > ROBOT_DEBUG_SESSION_TTL_SECONDS:
                stale_keys.append(session_key)
        stale_sessions = [ROBOT_DEBUG_SESSIONS.pop(key) for key in stale_keys]
    for session in stale_sessions:
        try:
            session.close()
        except Exception:
            pass


def _get_robot_debug_session(session_key, device_id=None):
    if not session_key:
        raise RuntimeError("session_key required")
    _cleanup_robot_debug_sessions()
    normalized_device_id = (device_id or XIAOZHI_DEBUG_DEVICE_ID).strip() or XIAOZHI_DEBUG_DEVICE_ID
    registry_key = f"{normalized_device_id}::{session_key}"
    with ROBOT_DEBUG_SESSIONS_LOCK:
        session = ROBOT_DEBUG_SESSIONS.get(registry_key)
        if session is None:
            session = RobotRuntimeDebugSession(session_key, normalized_device_id)
            ROBOT_DEBUG_SESSIONS[registry_key] = session
        else:
            session.device_id = normalized_device_id
        session.last_activity = time.time()
        return session


def _reset_robot_debug_session(session_key, device_id=None):
    if not session_key:
        return
    normalized_device_id = (device_id or XIAOZHI_DEBUG_DEVICE_ID).strip() or XIAOZHI_DEBUG_DEVICE_ID
    registry_key = f"{normalized_device_id}::{session_key}"
    with ROBOT_DEBUG_SESSIONS_LOCK:
        session = ROBOT_DEBUG_SESSIONS.pop(registry_key, None)
    if session is not None:
        try:
            session.close()
        except Exception:
            pass

def check_auth(u, p):
    return u == ADMIN_USER and p == ADMIN_PASS and ADMIN_PASS != ""


def requires_auth(f):
    @wraps(f)
    def wrapped(*a, **kw):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                "Auth required", 401, {"WWW-Authenticate": 'Basic realm="kb-admin"'}
            )
        return f(*a, **kw)
    return wrapped


def _route_scene_for_text(user_text, history):
    if not SCENE_ROUTER or not user_text:
        return None

    turn_index = 0
    last_scene = None
    last_subscene = None
    for item in history or []:
        if item.get("role") == "user":
            turn_index += 1
            scene = item.get("scene") or {}
            if scene.get("primary_scene"):
                last_scene = scene.get("primary_scene")
                last_subscene = scene.get("subscene")

    routed = SCENE_ROUTER.route(
        SceneRouterInput(
            text=user_text,
            child_profile=ChildProfile(age_band="6-8"),
            dialog_state=DialogState(
                current_scene=last_scene,
                current_subscene=last_subscene,
                turn_index=turn_index,
            ),
            signals=SignalState(
                emotion_hint="neutral",
                interruption=False,
                silence_ms=0,
                vlm_tags=[],
            ),
        )
    )
    snapshot = _load_scene_router_snapshot()
    scene_policy = None
    subscene_hint = ""
    for scene_item in snapshot.get("scenes", []):
        if scene_item.get("scene_name") != routed.primary_scene:
            continue
        scene_policy = scene_item.get("policy")
        for subscene_item in scene_item.get("subscenes", []):
            if subscene_item.get("subscene") == routed.subscene:
                subscene_hint = subscene_item.get("hint") or ""
                break
        break
    return {
        "primary_scene": routed.primary_scene,
        "subscene": routed.subscene,
        "secondary_scene": routed.secondary_scene,
        "risk_level": routed.risk_level,
        "emotion_state": routed.emotion_state,
        "age_band": routed.age_band,
        "policy_profile": routed.policy_profile,
        "should_use_rag": routed.should_use_rag,
        "should_use_memory": routed.should_use_memory,
        "should_use_vlm": routed.should_use_vlm,
        "should_escalate_parent": routed.should_escalate_parent,
        "should_force_safe_template": routed.should_force_safe_template,
        "confidence": routed.confidence,
        "reason_codes": routed.reason_codes,
        "policy": scene_policy,
        "subscene_hint": subscene_hint,
        "age_style_hint": (snapshot.get("age_style_hints") or {}).get(routed.age_band) or "",
    }


def _resolve_dialogue_state_for_text(user_text, history, scene):
    if (
        not DIALOGUE_STATE_MANAGER
        or not DialogueStateManagerInput
        or not RuntimeSignals
        or not ChildProfileSnapshot
        or not scene
        or not user_text
    ):
        return None

    previous_runtime_state = None
    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        dialogue_state = item.get("dialogue_state") or {}
        state = dialogue_state.get("state")
        if isinstance(state, dict):
            previous_runtime_state = state
            break

    scene_router_output = type("SceneOutput", (), scene)()
    result = DIALOGUE_STATE_MANAGER.update(
        DialogueStateManagerInput(
            text=user_text,
            timestamp_ms=int(time.time() * 1000),
            scene_router_output=scene_router_output,
            dialogue_state=previous_runtime_state,
            signals=RuntimeSignals(
                emotion_hint="neutral",
                interruption=False,
                silence_ms=0,
                user_move="unknown",
                understanding_signal="unknown",
                topic_switch_signal=False,
                frustration_signal=0,
            ),
            child_profile=ChildProfileSnapshot(age_band=scene.get("age_band") or "6-8"),
        )
    )
    return result.to_dict()


TIME_QUERY_MARKERS = ("现在几点", "几点了", "几点啦", "当前时间", "现在时间", "时间是多少")
DATE_QUERY_MARKERS = ("今天几号", "今天多少号", "今天日期", "今天是什么日期", "今天星期几", "今天周几")
LUNAR_QUERY_MARKERS = ("今天农历", "农历几号", "农历多少", "今天什么节气")


def _normalize_runtime_text(text):
    return "".join(str(text or "").strip().split())


def _is_time_query_text(text):
    normalized = _normalize_runtime_text(text)
    if any(marker in normalized for marker in TIME_QUERY_MARKERS):
        return True
    return ("现在" in normalized or "当前" in normalized) and ("几点" in normalized or "时间" in normalized)


def _is_date_query_text(text):
    normalized = _normalize_runtime_text(text)
    return any(marker in normalized for marker in DATE_QUERY_MARKERS)


def _is_lunar_query_text(text):
    normalized = _normalize_runtime_text(text)
    return any(marker in normalized for marker in LUNAR_QUERY_MARKERS)


def _build_grounded_context_reply_for_debug(user_text):
    normalized = _normalize_runtime_text(user_text)
    wants_time = _is_time_query_text(normalized)
    wants_date = _is_date_query_text(normalized)
    wants_lunar = _is_lunar_query_text(normalized)
    if not any((wants_time, wants_date, wants_lunar)):
        return None

    try:
        from core.utils.current_time import get_current_time_info

        current_time, today_date, today_weekday, lunar_date = get_current_time_info()
    except Exception:
        current_time = datetime.now().strftime("%H:%M")
        today_date = datetime.now().strftime("%Y-%m-%d")
        today_weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][datetime.now().weekday()]
        lunar_date = "农历获取失败"

    parts = []
    if wants_time:
        parts.append(f"现在是{current_time}")
    if wants_date:
        parts.append(f"今天是{today_date}，{today_weekday}")
    if wants_lunar:
        parts.append(f"今天农历是{lunar_date}")
    return "。".join(parts) + "。"


def _build_grounded_greeting_reply_for_debug(dialogue_state):
    if not isinstance(dialogue_state, dict):
        return None
    state = dialogue_state.get("state") or {}
    social_state = state.get("social_state") or {}
    if not social_state.get("is_greeting_turn"):
        return None
    if not social_state.get("greeting_conflict_with_time"):
        return None

    current_label = social_state.get("current_time_label") or "现在这个时段"
    recommended = social_state.get("recommended_greeting") or "你好"
    if social_state.get("greeting_conflict_with_previous"):
        return f"现在还是{current_label}呢，我们接着聊吧，{recommended}。"
    return f"现在更像{current_label}呢，不过见到你很开心，{recommended}。"


def _normalize_age_profile_value(field_name, value):
    if field_name == "max_new_concepts":
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            raise ValueError("max_new_concepts must be integer")
        return max(1, min(12, normalized))
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} required")
    return normalized


def _load_age_profiles():
    profiles = json.loads(json.dumps(DEFAULT_AGE_PROFILES, ensure_ascii=False))
    if not os.path.exists(AGE_PROFILE_CONFIG_PATH):
        return profiles
    try:
        with open(AGE_PROFILE_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return profiles

    if not isinstance(raw, dict):
        return profiles

    for age_group, defaults in DEFAULT_AGE_PROFILES.items():
        incoming = raw.get(age_group) or {}
        if not isinstance(incoming, dict):
            continue
        merged = dict(defaults)
        for field_name in defaults.keys():
            if field_name not in incoming:
                continue
            try:
                merged[field_name] = _normalize_age_profile_value(field_name, incoming[field_name])
            except ValueError:
                continue
        profiles[age_group] = merged
    return profiles


def _save_age_profiles(profiles):
    with open(AGE_PROFILE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    with open(RUNTIME_AGE_PROFILE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def _normalize_interaction_policy_value(field_name, value):
    if field_name == "reasoning_depth":
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            raise ValueError("reasoning_depth must be integer")
        return max(1, min(3, normalized))
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} required")
    return normalized


def _build_default_interaction_policy(scene_name):
    scene_defaults = DEFAULT_INTERACTION_POLICIES.get(scene_name)
    if scene_defaults:
        return dict(scene_defaults)
    return {
        "information_budget": "medium",
        "reasoning_depth": 2,
        "interaction_style": "exploration",
        "conversation_pacing": "balanced",
        "emotional_priority": "medium",
    }


def _load_interaction_policies():
    defaults = {}
    try:
        rules_spec = importlib.util.spec_from_file_location(
            f"scene_router_rules_policy_defaults_{int(time.time() * 1000)}",
            SCENE_ROUTER_RULES_PATH,
        )
        if rules_spec is not None and rules_spec.loader is not None:
            rules_module = importlib.util.module_from_spec(rules_spec)
            rules_spec.loader.exec_module(rules_module)
            scene_rules = getattr(rules_module, "SCENE_RULES", {}) or {}
            for scene_name in scene_rules.keys():
                defaults[scene_name] = _build_default_interaction_policy(scene_name)
    except Exception:
        defaults = {}
    if not defaults:
        for scene_name in DEFAULT_INTERACTION_POLICIES.keys():
            defaults[scene_name] = _build_default_interaction_policy(scene_name)

    profiles = json.loads(json.dumps(defaults, ensure_ascii=False))
    if not os.path.exists(INTERACTION_POLICY_CONFIG_PATH):
        return profiles
    try:
        with open(INTERACTION_POLICY_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return profiles

    if not isinstance(raw, dict):
        return profiles

    for scene_name, default_policy in defaults.items():
        incoming = raw.get(scene_name) or {}
        if not isinstance(incoming, dict):
            continue
        merged = dict(default_policy)
        for field_name in default_policy.keys():
            if field_name not in incoming:
                continue
            try:
                merged[field_name] = _normalize_interaction_policy_value(field_name, incoming[field_name])
            except ValueError:
                continue
        profiles[scene_name] = merged
    return profiles


def _save_interaction_policies(policies):
    with open(INTERACTION_POLICY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(policies, f, ensure_ascii=False, indent=2)
    with open(RUNTIME_INTERACTION_POLICY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(policies, f, ensure_ascii=False, indent=2)


def _normalize_scene_interest_config_value(field_name, value):
    return bool(value)


def _build_default_scene_interest_config(scene_name):
    config = DEFAULT_SCENE_INTEREST_CONFIGS.get(scene_name)
    if config:
        return dict(config)
    return {
        "use_interest_examples": False,
        "use_interest_story": False,
        "use_interest_games": False,
        "use_interest_conversation": False,
    }


def _load_scene_interest_configs():
    defaults = {}
    try:
        rules_spec = importlib.util.spec_from_file_location(
            f"scene_router_rules_interest_defaults_{int(time.time() * 1000)}",
            SCENE_ROUTER_RULES_PATH,
        )
        if rules_spec is not None and rules_spec.loader is not None:
            rules_module = importlib.util.module_from_spec(rules_spec)
            rules_spec.loader.exec_module(rules_module)
            scene_rules = getattr(rules_module, "SCENE_RULES", {}) or {}
            for scene_name in scene_rules.keys():
                defaults[scene_name] = _build_default_scene_interest_config(scene_name)
    except Exception:
        defaults = {}
    if not defaults:
        for scene_name in DEFAULT_SCENE_INTEREST_CONFIGS.keys():
            defaults[scene_name] = _build_default_scene_interest_config(scene_name)

    configs = json.loads(json.dumps(defaults, ensure_ascii=False))
    if not os.path.exists(SCENE_INTEREST_CONFIG_PATH):
        return configs
    try:
        with open(SCENE_INTEREST_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return configs

    if not isinstance(raw, dict):
        return configs

    for scene_name, defaults_value in defaults.items():
        incoming = raw.get(scene_name) or {}
        if not isinstance(incoming, dict):
            continue
        merged = dict(defaults_value)
        for field_name in defaults_value.keys():
            if field_name not in incoming:
                continue
            merged[field_name] = _normalize_scene_interest_config_value(
                field_name,
                incoming.get(field_name),
            )
        configs[scene_name] = merged
    return configs


def _save_scene_interest_configs(configs):
    with open(SCENE_INTEREST_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)
    with open(RUNTIME_SCENE_INTEREST_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


def _normalize_interest_influence_value(field_name, value):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} required")
    return normalized


def _normalize_interest_context_list(value):
    items = []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value or "").split(",")
    for item in raw_items:
        normalized = str(item or "").strip()
        if normalized:
            items.append(normalized)
    return items


def _load_interest_influence_config():
    config = {
        "favorite_topics": list(DEFAULT_INTEREST_TOPICS),
        "interest_influence": dict(DEFAULT_INTEREST_INFLUENCE_POLICY),
        "interest_adapter": json.loads(json.dumps(DEFAULT_INTEREST_ADAPTER, ensure_ascii=False)),
    }
    if not os.path.exists(INTERESTS_CONFIG_PATH):
        return config
    try:
        with open(INTERESTS_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return config

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
            if not key or not label:
                continue
            normalized_topics.append({"key": key, "label": label})
        if normalized_topics:
            config["favorite_topics"] = normalized_topics

    incoming_policy = raw.get("interest_influence")
    if isinstance(incoming_policy, dict):
        merged = dict(DEFAULT_INTEREST_INFLUENCE_POLICY)
        for field_name in DEFAULT_INTEREST_INFLUENCE_POLICY.keys():
            if field_name not in incoming_policy:
                continue
            try:
                merged[field_name] = _normalize_interest_influence_value(field_name, incoming_policy.get(field_name))
            except ValueError:
                continue
        config["interest_influence"] = merged

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
                merged_topic[field_name] = _normalize_interest_context_list(incoming_topic.get(field_name))
            merged_adapter[topic_key] = merged_topic
        config["interest_adapter"] = merged_adapter
    return config


def _save_interest_influence_config(config):
    with open(INTERESTS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    with open(RUNTIME_INTERESTS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _normalize_daily_text_list(value):
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value or "").splitlines()
    items = []
    for item in raw_items:
        normalized = str(item or "").strip()
        if normalized:
            items.append(normalized)
    return items


def _normalize_robot_profile_list(value):
    return _normalize_daily_text_list(value)


def _load_robot_profile_config():
    config = json.loads(json.dumps(DEFAULT_ROBOT_PROFILE_CONFIG, ensure_ascii=False))
    if not os.path.exists(ROBOT_PROFILE_CONFIG_PATH):
        return config
    try:
        with open(ROBOT_PROFILE_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return config

    if not isinstance(raw, dict):
        return config

    for section_name in ("identity", "personality", "values"):
        incoming = raw.get(section_name)
        if not isinstance(incoming, dict):
            continue
        section = dict(config[section_name])
        for key, default_value in section.items():
            if key not in incoming:
                continue
            if isinstance(default_value, list):
                normalized = _normalize_robot_profile_list(incoming.get(key))
                if normalized:
                    section[key] = normalized
            else:
                text = str(incoming.get(key) or "").strip()
                if text:
                    section[key] = text
        config[section_name] = section

    return config


def _save_robot_profile_config(config):
    with open(ROBOT_PROFILE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    with open(RUNTIME_ROBOT_PROFILE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _load_runtime_manage_api_config():
    merged = {}
    for candidate_path in (RUNTIME_DEFAULT_CONFIG_PATH, RUNTIME_CUSTOM_CONFIG_PATH):
        if not os.path.exists(candidate_path):
            continue
        try:
            with open(candidate_path, "r", encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        except Exception:
            continue
        if isinstance(payload, dict):
            merged.update(payload)

    manager_api = merged.get("manager-api")
    if not isinstance(manager_api, dict):
        return {}
    return {
        "url": str(manager_api.get("url") or "").strip(),
        "secret": str(manager_api.get("secret") or "").strip(),
    }


def _extract_robot_name_preference(payload):
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    long_term_memory = data.get("longTermMemory") if isinstance(data.get("longTermMemory"), dict) else data
    return str(long_term_memory.get("robotNamePreference") or "").strip()


def _normalize_child_memory_payload(payload, source=""):
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    memory = data.get("longTermMemory") if isinstance(data.get("longTermMemory"), dict) else data
    if not isinstance(memory, dict):
        return None

    def pick(*keys):
        for key in keys:
            value = memory.get(key)
            if value not in (None, "", "NULL"):
                return value
        return None

    def list_value(*keys):
        value = pick(*keys)
        if isinstance(value, list):
            return [str(item or "").strip() for item in value if str(item or "").strip()]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item or "").strip() for item in parsed if str(item or "").strip()]
            except Exception:
                pass
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return []

    age = pick("age")
    try:
        age = int(age) if age not in (None, "") else None
    except (TypeError, ValueError):
        age = None

    profile_version = pick("profileVersion", "profile_version")
    try:
        profile_version = int(profile_version) if profile_version not in (None, "") else None
    except (TypeError, ValueError):
        profile_version = None

    summary = {
        "nickname_preference": str(pick("nicknamePreference", "nickname_preference") or "").strip(),
        "age": age,
        "age_group": str(pick("ageGroup", "age_group") or "").strip(),
        "robot_name_preference": str(pick("robotNamePreference", "robot_name_preference") or "").strip(),
        "interests": list_value("interests"),
        "favorite_dog_types": list_value("favoriteDogTypes", "favorite_dog_types"),
        "desired_activities": list_value("desiredActivities", "desired_activities"),
        "parent_goals": list_value("parentGoals", "parent_goals"),
        "profile_version": profile_version,
        "source": source,
    }
    if any(value for key, value in summary.items() if key != "source"):
        return summary
    return None


def _load_child_memory_summary(device_id=None):
    return None


def _load_child_memory_summaries(device_ids):
    return {}


def _resolve_effective_robot_identity_name(device_id=None):
    normalized_device_id = str(device_id or XIAOZHI_DEBUG_DEVICE_ID).strip() or XIAOZHI_DEBUG_DEVICE_ID
    try:
        rows = mysql_query(
            "SELECT a.agent_name "
            "FROM ai_device d "
            "LEFT JOIN ai_agent a ON d.agent_id = a.id "
            f"WHERE LOWER(d.id)='{_sql_safe(normalized_device_id.lower())}' "
            "LIMIT 1"
        )
        if rows:
            agent_name = str(rows[0].get("agent_name") or "").strip()
            if agent_name:
                return agent_name
    except Exception:
        pass

    return ""


def _parse_db_datetime_to_ts(value):
    raw = str(value or "").strip()
    if not raw or raw.upper() == "NULL":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).timestamp()
        except ValueError:
            continue
    return None


def _normalize_daily_greeting_type(type_name, raw):
    default = dict(DEFAULT_DAILY_GREETING_CONFIG["greeting_types"][type_name])
    if not isinstance(raw, dict):
        return default

    merged = dict(default)
    merged["label"] = str(raw.get("label") or default["label"]).strip() or default["label"]
    merged["enabled"] = bool(raw.get("enabled", default["enabled"]))
    try:
        merged["priority"] = max(1, min(999, int(raw.get("priority", default["priority"]))))
    except (TypeError, ValueError):
        merged["priority"] = default["priority"]

    for field_name in ("purpose", "template", "notes"):
        merged[field_name] = str(raw.get(field_name) or default[field_name]).strip() or default[field_name]

    examples = _normalize_daily_text_list(raw.get("examples"))
    merged["examples"] = examples or list(default["examples"])
    return merged


def _normalize_boot_greeting_config(raw):
    default = json.loads(
        json.dumps(DEFAULT_DAILY_GREETING_CONFIG["boot_greeting"], ensure_ascii=False)
    )
    if not isinstance(raw, dict):
        return default

    merged = dict(default)
    for field_name in (
        "enabled",
        "auto_play_after_startup",
        "wait_for_network",
        "wait_for_core_services",
    ):
        if field_name in raw:
            merged[field_name] = bool(raw.get(field_name))

    if "max_duration_seconds" in raw:
        try:
            merged["max_duration_seconds"] = max(
                1,
                min(30, int(raw.get("max_duration_seconds"))),
            )
        except (TypeError, ValueError):
            merged["max_duration_seconds"] = default["max_duration_seconds"]

    incoming_last = raw.get("last_boot_greeting")
    if isinstance(incoming_last, dict):
        merged["last_boot_greeting"] = {
            "category": str(incoming_last.get("category") or "").strip(),
            "greeting_id": str(incoming_last.get("greeting_id") or "").strip(),
        }

    default_categories = list(default["library"]["categories"])
    incoming_library = raw.get("library")
    if isinstance(incoming_library, dict) and isinstance(incoming_library.get("categories"), list):
        normalized_categories = []
        for index, item in enumerate(incoming_library.get("categories") or []):
            if not isinstance(item, dict):
                continue
            fallback = default_categories[index] if index < len(default_categories) else {}
            key = str(item.get("key") or fallback.get("key") or "").strip()
            label = str(item.get("label") or fallback.get("label") or key).strip() or key
            if not key:
                continue
            try:
                weight = max(1, min(999, int(item.get("weight", fallback.get("weight", 10)))))
            except (TypeError, ValueError):
                weight = int(fallback.get("weight", 10) or 10)
            greetings = []
            incoming_greetings = item.get("greetings")
            if isinstance(incoming_greetings, list):
                for g_index, greeting in enumerate(incoming_greetings):
                    if not isinstance(greeting, dict):
                        continue
                    fallback_greetings = fallback.get("greetings") or []
                    fallback_greeting = fallback_greetings[g_index] if g_index < len(fallback_greetings) else {}
                    greeting_id = str(
                        greeting.get("id")
                        or fallback_greeting.get("id")
                        or f"{key}_{g_index + 1:02d}"
                    ).strip()
                    greeting_text = str(
                        greeting.get("text")
                        or fallback_greeting.get("text")
                        or ""
                    ).strip()
                    if greeting_id and greeting_text:
                        greetings.append({"id": greeting_id, "text": greeting_text})
            if not greetings:
                fallback_greetings = fallback.get("greetings") or []
                greetings = [
                    {
                        "id": str(greeting.get("id") or "").strip(),
                        "text": str(greeting.get("text") or "").strip(),
                    }
                    for greeting in fallback_greetings
                    if str(greeting.get("id") or "").strip() and str(greeting.get("text") or "").strip()
                ]
            normalized_categories.append(
                {
                    "key": key,
                    "label": label,
                    "weight": weight,
                    "greetings": greetings,
                }
            )
        if normalized_categories:
            merged["library"] = {"categories": normalized_categories}

    return merged


def _load_daily_greeting_config():
    config = json.loads(json.dumps(DEFAULT_DAILY_GREETING_CONFIG, ensure_ascii=False))
    if not os.path.exists(DAILY_GREETING_CONFIG_PATH):
        return config
    try:
        with open(DAILY_GREETING_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return config

    if not isinstance(raw, dict):
        return config

    for field_name in (
        "enabled",
        "first_meaningful_interaction_only",
        "mark_delivered_once_per_day",
        "block_on_higher_priority_interruptions",
    ):
        if field_name in raw:
            config[field_name] = bool(raw.get(field_name))

    if raw.get("version") is not None:
        try:
            config["version"] = max(1, int(raw.get("version")))
        except (TypeError, ValueError):
            pass

    for field_name in ("goal",):
        if field_name in raw:
            config[field_name] = str(raw.get(field_name) or "").strip() or config[field_name]

    for field_name in (
        "trigger_conditions",
        "pipeline",
        "greeting_structure",
        "selection_rules",
        "design_principles",
        "future_extensions",
    ):
        if field_name in raw:
            normalized = _normalize_daily_text_list(raw.get(field_name))
            if normalized:
                config[field_name] = normalized

    incoming_state = raw.get("state_example")
    if isinstance(incoming_state, dict):
        state = dict(config["state_example"])
        for key in state.keys():
            if key not in incoming_state:
                continue
            if key == "delivered":
                state[key] = bool(incoming_state.get(key))
            else:
                state[key] = str(incoming_state.get(key) or "").strip() or state[key]
        config["state_example"] = state

    incoming_types = raw.get("greeting_types")
    if isinstance(incoming_types, dict):
        normalized_types = {}
        for type_name in DEFAULT_DAILY_GREETING_CONFIG["greeting_types"].keys():
            normalized_types[type_name] = _normalize_daily_greeting_type(type_name, incoming_types.get(type_name))
        config["greeting_types"] = normalized_types

    config["boot_greeting"] = _normalize_boot_greeting_config(raw.get("boot_greeting"))
    runtime_raw = {}
    if os.path.exists(RUNTIME_DAILY_GREETING_CONFIG_PATH):
        try:
            with open(RUNTIME_DAILY_GREETING_CONFIG_PATH, "r", encoding="utf-8") as f:
                runtime_raw = json.load(f)
        except Exception:
            runtime_raw = {}
    runtime_boot = runtime_raw.get("boot_greeting") if isinstance(runtime_raw, dict) else None
    if isinstance(runtime_boot, dict) and isinstance(runtime_boot.get("last_boot_greeting"), dict):
        config["boot_greeting"]["last_boot_greeting"] = {
            "category": str(runtime_boot["last_boot_greeting"].get("category") or "").strip(),
            "greeting_id": str(runtime_boot["last_boot_greeting"].get("greeting_id") or "").strip(),
        }

    return config


def _save_daily_greeting_config(config):
    with open(DAILY_GREETING_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    with open(RUNTIME_DAILY_GREETING_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _load_scene_router_snapshot():
    rules_spec = importlib.util.spec_from_file_location(
        f"scene_router_rules_snapshot_{int(time.time() * 1000)}",
        SCENE_ROUTER_RULES_PATH,
    )
    policy_spec = importlib.util.spec_from_file_location(
        f"scene_router_policy_snapshot_{int(time.time() * 1000)}",
        SCENE_ROUTER_POLICY_PATH,
    )
    if rules_spec is None or rules_spec.loader is None:
        raise RuntimeError("scene router rules load failed")
    if policy_spec is None or policy_spec.loader is None:
        raise RuntimeError("scene router policy load failed")
    rules_module = importlib.util.module_from_spec(rules_spec)
    policy_module = importlib.util.module_from_spec(policy_spec)
    rules_spec.loader.exec_module(rules_module)
    policy_spec.loader.exec_module(policy_module)

    scene_rules = getattr(rules_module, "SCENE_RULES", {}) or {}
    default_scene = getattr(rules_module, "DEFAULT_SCENE", {}) or {}
    policy_specs = getattr(policy_module, "SCENE_POLICY_SPECS", {}) or {}
    subscene_hints = getattr(policy_module, "SUBSCENE_HINTS", {}) or {}
    age_style_hints = getattr(policy_module, "AGE_STYLE_HINTS", {}) or {}
    interaction_policies = _load_interaction_policies()
    scene_interest_configs = _load_scene_interest_configs()
    scenes = []
    for scene_name, scene_rule in scene_rules.items():
        subscene_rules = scene_rule.get("subscene_rules") or []
        policy_spec_value = policy_specs.get(scene_name)
        policy_data = None
        if policy_spec_value is not None:
            policy_data = {
                "goal": getattr(policy_spec_value, "goal", ""),
                "tone": getattr(policy_spec_value, "tone", ""),
                "response_style": list(getattr(policy_spec_value, "response_style", []) or []),
                "ask_strategy": list(getattr(policy_spec_value, "ask_strategy", []) or []),
                "avoid": list(getattr(policy_spec_value, "avoid", []) or []),
                "exit_condition": getattr(policy_spec_value, "exit_condition", ""),
            }
        scenes.append({
            "scene_name": scene_name,
            "risk_level": scene_rule.get("risk_level") or "low",
            "policy_profile": scene_rule.get("policy_profile") or "",
            "should_force_safe_template": bool(scene_rule.get("should_force_safe_template")),
            "should_use_memory": bool(scene_rule.get("should_use_memory")),
            "should_use_rag": bool(scene_rule.get("should_use_rag")),
            "should_use_vlm": bool(scene_rule.get("should_use_vlm")),
            "should_escalate_parent": bool(scene_rule.get("should_escalate_parent")),
            "policy": policy_data,
            "interaction_policy": interaction_policies.get(scene_name) or _build_default_interaction_policy(scene_name),
            "scene_interest_config": scene_interest_configs.get(scene_name) or _build_default_scene_interest_config(scene_name),
            "subscenes": [
                {
                    "subscene": subscene,
                    "keywords": keywords,
                    "hint": subscene_hints.get(subscene) or "",
                }
                for subscene, keywords in subscene_rules
            ],
        })

    return {
        "scenes": scenes,
        "default_scene": default_scene,
        "rules_path": SCENE_ROUTER_RULES_PATH,
        "policy_path": SCENE_ROUTER_POLICY_PATH,
        "age_style_hints": age_style_hints,
        "scene_count": len(scenes),
    }


register_messaging_routes(app, requires_auth)


def mysql_query(sql):
    """通过 docker exec 跑 mysql 查询,返回行列表(dict)"""
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", f"-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "--batch", "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 and "Warning" not in r.stderr:
        raise RuntimeError(f"mysql err: {r.stderr[:300]}")
    lines = [l for l in r.stdout.split("\n") if l.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        rows.append(dict(zip(headers, cells)))
    return rows


def mysql_exec(sql):
    """跑 update/insert,不返回行"""
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", f"-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 and "Warning" not in r.stderr:
        raise RuntimeError(f"mysql err: {r.stderr[:300]}")
    return True


def _mysql_short_memory_rows():
    rows = mysql_query(
        "SELECT device_id, HEX(memory_json) AS memory_hex, updated_at "
        "FROM ai_short_term_memory ORDER BY updated_at DESC"
    )
    parsed = []
    for row in rows:
        memory_hex = str(row.get("memory_hex") or "").strip()
        payload = {}
        if memory_hex:
            try:
                payload = json.loads(bytes.fromhex(memory_hex).decode("utf-8"))
            except Exception:
                payload = {}
        parsed.append(
            {
                "device_id": str(row.get("device_id") or "").strip(),
                "updated_at": str(row.get("updated_at") or "").strip(),
                "memory": payload if isinstance(payload, dict) else {},
            }
        )
    return parsed


def _date_window_ms(date_text):
    date_value = str(date_text or "").strip()
    if not date_value:
        date_value = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        start = datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("date must be YYYY-MM-DD")
    end = start + timedelta(days=1)
    return date_value, int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _clean_daily_source_hint(text):
    value = str(text or "").strip()
    if not value:
        return ""
    for prefix in ("孩子提到最近经历：", "孩子提到：", "孩子在继续追问："):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    value = value.split("；后来", 1)[0].strip(" ，,。！？!?；;")
    if value.startswith("我的"):
        value = value[2:].strip(" ，,。！？!?；;")
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
    if any(fragment in value for fragment in ("我的和就能", "和就能", "得很清楚")):
        if "猫" in value:
            return "猫晚上看得很清楚这件事"
        if "狗" in value:
            return "狗狗的事情"
        return ""
    if "猫" in value and "晚上" in value and ("看得很清楚" in value or "看得清楚" in value):
        return "猫晚上看得很清楚这件事"
    return value[:48].rstrip(" ，,。！？!?；;")


def _format_daily_source_potential_text(hint):
    value = str(hint or "").strip(" ，,。！？!?；;")
    if not value:
        return ""
    if any(marker in value for marker in ("病", "不舒服", "医院", "检查", "输液")):
        if "快好" in value or "好起来" in value or "好多" in value:
            return f"昨天你说{value}，今天它怎么样啦？"
        return f"昨天你说{value}，今天好一点了吗？"
    if value.startswith(("去", "看", "参加", "比赛", "表演")):
        return f"昨天你说{value}，后来怎么样啦？"
    return f"昨天你提到{value}，今天还想和我说说吗？"


def _daily_followup_source_id(topic):
    raw = (
        str(topic.get("topic_id") or "").strip()
        or str(topic.get("topic") or "").strip()
        or str(topic.get("summary") or "").strip()
        or "unknown"
    )
    return "follow_up_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _is_daily_followup_candidate(topic, start_ms, end_ms):
    if not isinstance(topic, dict):
        return False
    memory_type = str(topic.get("memory_type") or "").strip()
    if memory_type not in {"event", "task", "health", "emotion"}:
        return False
    last_active = int(topic.get("last_active_at_ms") or 0)
    if last_active < start_ms or last_active >= end_ms:
        return False
    follow_up = topic.get("follow_up") or {}
    naturalness = follow_up.get("naturalness") or {}
    return bool(follow_up.get("eligible")) and bool(naturalness.get("passed"))


def _load_daily_greeting_state_snapshot():
    for path in (RUNTIME_DAILY_GREETING_STATE_PATH,):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass
    cmd = [
        "docker",
        "exec",
        "xiaozhi-esp32-server",
        "cat",
        "/opt/xiaozhi-esp32-server/data/daily_greeting_state.json",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if r.returncode == 0 and r.stdout.strip():
            payload = json.loads(r.stdout)
            return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
    return {}


def _selected_daily_greeting_for_device(device_id):
    state = _load_daily_greeting_state_snapshot()
    devices = state.get("devices") or {}
    normalized = str(device_id or "").strip().lower()
    device_state = devices.get(normalized) or devices.get(str(device_id or "").strip()) or {}
    if not isinstance(device_state, dict):
        return {}
    return {
        "date": device_state.get("date"),
        "delivered": bool(device_state.get("delivered")),
        "greeting_type": device_state.get("greeting_type"),
        "source_id": device_state.get("source_id"),
        "timestamp": device_state.get("timestamp"),
        "generated": bool(device_state.get("generated")),
        "generated_text": device_state.get("generated_text"),
        "recent_patterns": device_state.get("recent_patterns") or [],
    }


def _build_greeting_source_candidate(topic):
    summary = str(topic.get("summary") or "").strip()
    last_user_text = str(topic.get("last_user_text") or "").strip()
    topic_name = str(topic.get("topic") or "").strip()
    greeting_candidate = topic.get("greeting_candidate") or {}
    if not isinstance(greeting_candidate, dict):
        greeting_candidate = {}
    if not greeting_candidate:
        try:
            from core.short_term_memory import ShortTermTopic

            hydrated = ShortTermTopic.from_dict(topic).to_dict()
            greeting_candidate = hydrated.get("greeting_candidate") or {}
            if not summary:
                summary = str(hydrated.get("summary") or "").strip()
            if not last_user_text:
                last_user_text = str(hydrated.get("last_user_text") or "").strip()
            if not topic_name:
                topic_name = str(hydrated.get("topic") or "").strip()
        except Exception:
            greeting_candidate = {}
    hint = (
        _clean_daily_source_hint(greeting_candidate.get("content"))
        or _clean_daily_source_hint(summary)
        or _clean_daily_source_hint(last_user_text)
        or _clean_daily_source_hint(topic_name)
    )
    candidate_type = str(greeting_candidate.get("type") or "knowledge_fact")
    greeting_score = float(greeting_candidate.get("score") or 0.0)
    emotional_weight = float(greeting_candidate.get("emotionalWeight") or 0.0)
    follow_up_needed = bool(greeting_candidate.get("followUpNeeded"))
    if not greeting_candidate:
        follow_up_needed = bool((topic.get("follow_up") or {}).get("eligible"))
    return {
        "source_id": _daily_followup_source_id(topic),
        "topic_id": topic.get("topic_id"),
        "topic": topic_name,
        "display_hint": hint,
        "potential_text": _format_daily_source_potential_text(hint),
        "summary": summary,
        "memory_type": topic.get("memory_type"),
        "greeting_candidate": greeting_candidate,
        "greeting_candidate_type": candidate_type,
        "greeting_candidate_type_priority": GREETING_CANDIDATE_TYPE_PRIORITY.get(candidate_type, 0),
        "greeting_score": greeting_score,
        "emotional_weight": emotional_weight,
        "follow_up_needed": follow_up_needed,
        "follow_up": topic.get("follow_up") or {},
        "entities": topic.get("entities") or [],
        "open_questions": topic.get("open_questions") or [],
        "importance": topic.get("importance"),
        "last_user_text": topic.get("last_user_text"),
        "last_assistant_text": topic.get("last_assistant_text"),
        "last_active_at_ms": topic.get("last_active_at_ms"),
    }


@app.route("/")
@requires_auth
def index():
    return send_from_directory("static", "index.html")


@app.route("/scene-router")
@requires_auth
def scene_router_page():
    return send_from_directory("static", "scene-router.html")


@app.route("/age-profile")
@requires_auth
def age_profile_page():
    return send_from_directory("static", "age-profile.html")


@app.route("/interests")
@requires_auth
def interests_page():
    return send_from_directory("static", "interests.html")


@app.route("/greeting")
@requires_auth
def greeting_page():
    return send_from_directory("static", "greeting.html")


@app.route("/greeting-sources")
@requires_auth
def greeting_sources_page():
    response = send_from_directory("static", "greeting-sources.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/robot-profile")
@requires_auth
def robot_profile_page():
    return send_from_directory("static", "robot-profile.html")


@app.route("/devices")
@requires_auth
def devices_page():
    return send_from_directory("static", "devices.html")


def _resolve_device_websocket_url():
    try:
        with open(RUNTIME_CUSTOM_CONFIG_PATH, "r", encoding="utf-8") as f:
            runtime_config = yaml.safe_load(f) or {}
        websocket_url = str((runtime_config.get("server") or {}).get("websocket") or "").strip()
        if websocket_url:
            return websocket_url
    except Exception:
        pass
    return "ws://122.51.155.114:8000/xiaozhi/v1/"


def _load_yaml_config(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _resolve_device_auth_secret():
    for path in (
        os.path.join(RUNTIME_DATA_DIR, ".config.yaml"),
        RUNTIME_CUSTOM_CONFIG_PATH,
        RUNTIME_DEFAULT_CONFIG_PATH,
    ):
        config = _load_yaml_config(path)
        server_config = config.get("server") or {}
        auth_key = str(server_config.get("auth_key") or "").strip()
        if auth_key and "你" not in auth_key:
            return auth_key

        manager_secret = str((config.get("manager-api") or {}).get("secret") or "").strip()
        if manager_secret and "你" not in manager_secret:
            return manager_secret
    return ""


def _generate_device_auth_token(client_id, device_id):
    client_id = str(client_id or "").strip()
    device_id = str(device_id or "").strip()
    secret = _resolve_device_auth_secret()
    if not client_id or not device_id or not secret:
        return ""

    timestamp = int(time.time())
    content = f"{client_id}|{device_id}|{timestamp}"
    signature = hmac.new(
        secret.encode("utf-8"),
        content.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    encoded = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{encoded}.{timestamp}"


@app.route("/ota/", methods=["GET", "POST", "OPTIONS"])
def ota_for_device():
    if request.method == "OPTIONS":
        return Response("", status=204)

    websocket_url = _resolve_device_websocket_url()
    if request.method == "GET":
        return Response(
            f"OTA接口运行正常，向设备发送的websocket地址是：{websocket_url}",
            mimetype="text/plain",
        )

    payload = request.get_json(silent=True) or {}
    application = payload.get("application") if isinstance(payload, dict) else {}
    device_version = ""
    if isinstance(application, dict):
        device_version = str(application.get("version") or "").strip()
    if not device_version:
        device_version = str(request.headers.get("Device-Version") or request.headers.get("App-Version") or "0.0.0")
    device_id = str(request.headers.get("Device-Id") or "").strip()
    client_id = str(request.headers.get("Client-Id") or "").strip()
    token = _generate_device_auth_token(client_id, device_id)

    return jsonify(
        {
            "server_time": {
                "timestamp": int(round(time.time() * 1000)),
                "timezone_offset": 8 * 60,
            },
            "firmware": {
                "version": device_version,
                "url": "",
            },
            "websocket": {
                "url": websocket_url,
                "token": token,
            },
        }
    )


@app.route("/monitor")
@requires_auth
def monitor_page():
    return send_from_directory("static", "monitor.html")


@app.route("/prompt")
@requires_auth
def prompt_page():
    return send_from_directory("static", "prompt.html")


# ============= 知识库 =============

@app.route("/api/knowledge")
@requires_auth
def list_kb():
    r = requests.get(f"{ZHIPU_BASE}/knowledge", headers=H, timeout=15)
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/knowledge", methods=["POST"])
@requires_auth
def create_kb():
    body = request.get_json(force=True)
    payload = {
        "name": body.get("name", "未命名"),
        "description": body.get("description", ""),
        "embedding_id": body.get("embedding_id", 3),
    }
    r = requests.post(
        f"{ZHIPU_BASE}/knowledge",
        headers={**H, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/knowledge/<kb_id>", methods=["DELETE"])
@requires_auth
def delete_kb(kb_id):
    r = requests.delete(f"{ZHIPU_BASE}/knowledge/{kb_id}", headers=H, timeout=15)
    return Response(r.text, status=r.status_code, mimetype="application/json")


# ============= 文件 =============

@app.route("/api/files")
@requires_auth
def list_files():
    kb_id = request.args.get("knowledge_id", "")
    r = requests.get(
        f"{ZHIPU_BASE}/files",
        headers=H,
        params={"purpose": "retrieval", "knowledge_id": kb_id},
        timeout=15,
    )
    data = r.json() if r.status_code == 200 else {}
    if "list" in data:
        for f in data["list"]:
            local = os.path.join(FILES_DIR, kb_id, f.get("id", ""))
            f["has_local"] = os.path.exists(local)
    return jsonify(data) if r.status_code == 200 else Response(r.text, status=r.status_code)


@app.route("/api/files", methods=["POST"])
@requires_auth
def upload_file():
    kb_id = request.form.get("knowledge_id", "")
    f = request.files.get("file")
    if not kb_id or not f:
        return jsonify({"error": "missing knowledge_id or file"}), 400

    raw = f.stream.read()
    files = {"file": (f.filename, raw, f.mimetype or "application/octet-stream")}
    data = {"purpose": "retrieval", "knowledge_id": kb_id}
    r = requests.post(
        f"{ZHIPU_BASE}/files", headers=H, files=files, data=data, timeout=120
    )
    try:
        resp = r.json()
        if resp.get("successInfos"):
            kb_local = os.path.join(FILES_DIR, kb_id)
            os.makedirs(kb_local, exist_ok=True)
            for info in resp["successInfos"]:
                fid = info.get("fileId") or info.get("documentId") or info.get("id")
                if fid:
                    with open(os.path.join(kb_local, fid), "wb") as out:
                        out.write(raw)
                    meta = {"name": f.filename, "uploaded_at": int(time.time()),
                            "size": len(raw), "mime": f.mimetype}
                    with open(os.path.join(kb_local, fid + ".meta.json"), "w", encoding="utf-8") as m:
                        json.dump(meta, m, ensure_ascii=False)
    except Exception:
        pass
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/files/<file_id>", methods=["DELETE"])
@requires_auth
def delete_file(file_id):
    r = requests.delete(f"{ZHIPU_BASE}/files/{file_id}", headers=H, timeout=15)
    for kb_dir in os.listdir(FILES_DIR):
        p = os.path.join(FILES_DIR, kb_dir, file_id)
        if os.path.exists(p):
            try:
                os.remove(p)
                mp = p + ".meta.json"
                if os.path.exists(mp):
                    os.remove(mp)
            except Exception:
                pass
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/files/<file_id>/download")
@requires_auth
def download_file(file_id):
    kb_id = request.args.get("knowledge_id", "")
    p = os.path.join(FILES_DIR, kb_id, file_id)
    mp = p + ".meta.json"
    if not os.path.exists(p):
        return jsonify({"error": "本地副本不存在(此文件在 kb-admin 升级前上传,无副本)"}), 404
    name = file_id
    if os.path.exists(mp):
        try:
            with open(mp, encoding="utf-8") as m:
                name = json.load(m).get("name", file_id)
        except Exception:
            pass
    return send_file(p, as_attachment=True, download_name=name)


@app.route("/api/files/<file_id>/preview")
@requires_auth
def preview_file(file_id):
    kb_id = request.args.get("knowledge_id", "")
    p = os.path.join(FILES_DIR, kb_id, file_id)
    if not os.path.exists(p):
        return jsonify({"error": "本地副本不存在"}), 404
    try:
        with open(p, "rb") as f:
            raw = f.read(64 * 1024)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")
        return jsonify({"text": text, "truncated": os.path.getsize(p) > 64 * 1024})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= 检索测试 =============

@app.route("/api/test", methods=["POST"])
@requires_auth
def test_query():
    body = request.get_json(force=True)
    kb_id = body.get("knowledge_id", "")
    question = body.get("question", "")
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": "严格基于知识库回答；若没有相关信息，说“知识库中没有”。"},
            {"role": "user", "content": question},
        ],
        "tools": [{"type": "retrieval", "retrieval": {"knowledge_id": kb_id}}],
    }
    r = requests.post(
        f"{ZHIPU_BASE}/chat/completions",
        headers={**H, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    return Response(r.text, status=r.status_code, mimetype="application/json")


# ============= D: 监控面板 =============

@app.route("/api/health")
@requires_auth
def health():
    out = {"ts": int(time.time()), "containers": [], "memory": {}, "disk": {}, "errors": {}}

    try:
        r = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"],
            capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().split("\n"):
            if not line: continue
            parts = line.split("|")
            if len(parts) == 4:
                out["containers"].append({
                    "name": parts[0], "cpu": parts[1],
                    "mem": parts[2], "mem_perc": parts[3],
                })
    except Exception as e:
        out["containers_error"] = str(e)

    try:
        r = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if line.startswith("Mem:"):
                f = line.split()
                out["memory"] = {"total_mb": int(f[1]), "used_mb": int(f[2]),
                                 "free_mb": int(f[3]), "available_mb": int(f[6])}
            elif line.startswith("Swap:"):
                f = line.split()
                out["memory"]["swap_total_mb"] = int(f[1])
                out["memory"]["swap_used_mb"] = int(f[2])
    except Exception as e:
        out["memory_error"] = str(e)

    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 2:
            f = lines[1].split()
            out["disk"] = {"total": f[1], "used": f[2], "avail": f[3], "use_pct": f[4]}
    except Exception as e:
        out["disk_error"] = str(e)

    try:
        r = subprocess.run(
            ["docker", "logs", "--since", "1h", "xiaozhi-esp32-server"],
            capture_output=True, text=True, timeout=15)
        all_log = (r.stdout or "") + (r.stderr or "")
        out["errors"]["server_1h"] = {
            "ERROR": all_log.count(" ERROR ") + all_log.count("[ERROR]"),
            "WARNING": all_log.count(" WARNING ") + all_log.count("[WARNING]"),
            "asr_fail": all_log.lower().count("asr") + all_log.lower().count("paraformer"),
            "tts_fail": sum(1 for l in all_log.split("\n") if "tts" in l.lower() and ("error" in l.lower() or "timeout" in l.lower() or "fail" in l.lower())),
        }
    except Exception as e:
        out["errors"]["server_error"] = str(e)

    try:
        r = requests.get("http://localhost:8003/xiaozhi/ota/", timeout=5)
        out["ota_status"] = r.status_code
    except Exception as e:
        out["ota_status"] = f"ERR: {str(e)[:100]}"

    return jsonify(out)


@app.route("/api/health/logs")
@requires_auth
def recent_logs():
    container = request.args.get("container", "xiaozhi-esp32-server")
    lines = request.args.get("lines", "100")
    level = request.args.get("level", "")
    try:
        r = subprocess.run(
            ["docker", "logs", "--tail", lines, container],
            capture_output=True, text=True, timeout=15)
        log = (r.stdout or "") + (r.stderr or "")
        if level:
            log = "\n".join(l for l in log.split("\n") if level.upper() in l.upper())
        return jsonify({"log": log[-50000:]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= E: Prompt 版本化 =============

@app.route("/api/agents")
@requires_auth
def list_agents():
    try:
        rows = mysql_query("SELECT id, agent_name, LENGTH(system_prompt) as plen, LENGTH(summary_memory) as mlen FROM ai_agent ORDER BY agent_name")
        return jsonify({"list": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_id>/prompt")
@requires_auth
def get_current_prompt(agent_id):
    try:
        agent_id = agent_id.replace("'", "")
        rows = mysql_query(f"SELECT system_prompt, agent_name FROM ai_agent WHERE id='{agent_id}'")
        if not rows:
            return jsonify({"error": "agent 不存在"}), 404
        return jsonify({"system_prompt": rows[0].get("system_prompt", ""),
                        "agent_name": rows[0].get("agent_name", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompt-history/<agent_id>")
@requires_auth
def list_prompt_history(agent_id):
    d = os.path.join(PROMPTS_DIR, agent_id)
    if not os.path.isdir(d):
        return jsonify({"list": []})
    items = []
    for fn in sorted(os.listdir(d), reverse=True):
        if not fn.endswith(".json"): continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                meta = json.load(f)
            meta["filename"] = fn
            items.append(meta)
        except Exception:
            pass
    return jsonify({"list": items})


@app.route("/api/prompt-history/<agent_id>/<filename>")
@requires_auth
def get_prompt_version(agent_id, filename):
    if "/" in filename or ".." in filename:
        return jsonify({"error": "bad filename"}), 400
    p = os.path.join(PROMPTS_DIR, agent_id, filename)
    if not os.path.exists(p):
        return jsonify({"error": "版本不存在"}), 404
    with open(p, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/agents/<agent_id>/prompt", methods=["POST"])
@requires_auth
def save_prompt(agent_id):
    """保存当前 prompt 为快照,然后更新数据库"""
    body = request.get_json(force=True)
    new_prompt = body.get("system_prompt", "")
    note = body.get("note", "")
    if not new_prompt:
        return jsonify({"error": "system_prompt 必填"}), 400
    try:
        agent_id_safe = agent_id.replace("'", "")
        rows = mysql_query(f"SELECT system_prompt FROM ai_agent WHERE id='{agent_id_safe}'")
        if not rows:
            return jsonify({"error": "agent 不存在"}), 404
        old = rows[0].get("system_prompt", "")

        d = os.path.join(PROMPTS_DIR, agent_id_safe)
        os.makedirs(d, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        snap = {"agent_id": agent_id_safe, "saved_at": int(time.time()),
                "saved_at_str": ts, "system_prompt": old, "note": note,
                "size": len(old)}
        with open(os.path.join(d, f"{ts}.json"), "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)

        escaped = new_prompt.replace("\\", "\\\\").replace("'", "''")
        mysql_exec(f"UPDATE ai_agent SET system_prompt='{escaped}', updated_at=NOW() WHERE id='{agent_id_safe}'")
        return jsonify({"ok": True, "snapshot": ts, "old_size": len(old), "new_size": len(new_prompt)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompt-history/<agent_id>/<filename>/restore", methods=["POST"])
@requires_auth
def restore_prompt(agent_id, filename):
    if "/" in filename or ".." in filename:
        return jsonify({"error": "bad filename"}), 400
    p = os.path.join(PROMPTS_DIR, agent_id, filename)
    if not os.path.exists(p):
        return jsonify({"error": "版本不存在"}), 404
    try:
        with open(p, encoding="utf-8") as f:
            snap = json.load(f)
        old_prompt = snap.get("system_prompt", "")
        if not old_prompt:
            return jsonify({"error": "该快照无 prompt 内容"}), 400

        agent_id_safe = agent_id.replace("'", "")
        rows = mysql_query(f"SELECT system_prompt FROM ai_agent WHERE id='{agent_id_safe}'")
        if rows:
            cur = rows[0].get("system_prompt", "")
            d = os.path.join(PROMPTS_DIR, agent_id_safe)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = {"agent_id": agent_id_safe, "saved_at": int(time.time()),
                      "saved_at_str": ts, "system_prompt": cur,
                      "note": f"自动备份(回滚到 {filename} 之前)", "size": len(cur)}
            with open(os.path.join(d, f"{ts}.json"), "w", encoding="utf-8") as f:
                json.dump(backup, f, ensure_ascii=False, indent=2)

        escaped = old_prompt.replace("\\", "\\\\").replace("'", "''")
        mysql_exec(f"UPDATE ai_agent SET system_prompt='{escaped}', updated_at=NOW() WHERE id='{agent_id_safe}'")
        return jsonify({"ok": True, "restored_from": filename, "size": len(old_prompt)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompt-history/<agent_id>/<filename>", methods=["DELETE"])
@requires_auth
def delete_prompt_version(agent_id, filename):
    if "/" in filename or ".." in filename:
        return jsonify({"error": "bad filename"}), 400
    p = os.path.join(PROMPTS_DIR, agent_id, filename)
    if os.path.exists(p):
        os.remove(p)
    return jsonify({"ok": True})




# ============= 长期陪伴画像 =============

@app.route("/portrait")
@requires_auth
def portrait_page():
    return Response("Not Found", status=404)


@app.route("/api/portrait/<agent_id>")
@requires_auth
def get_portrait(agent_id):
    """返回注入对话用的精简上下文：长期画像 + 近3天摘要 + 今日未完成提醒"""
    try:
        agent_id = agent_id.replace("'", "")
        profile = mysql_query(
            f"SELECT agent_id, schedule_profile, medicine_profile, companion_prefs, "
            f"mood_profile, fraud_profile, health_profile, recent_trends, tomorrow_strategy, "
            f"data_days, last_updated FROM rl_companion_profile WHERE agent_id='{agent_id}'"
        )
        recent = mysql_query(
            f"SELECT summary_date, overall_status, mood_companion, tomorrow_strategy, "
            f"medicine_status, fraud_risk, health_signals, family_note FROM rl_daily_summary "
            f"WHERE agent_id='{agent_id}' ORDER BY summary_date DESC LIMIT 3"
        )
        pending = mysql_query(
            f"SELECT title, remind_time FROM rl_reminders "
            f"WHERE agent_id='{agent_id}' AND enabled=1 "
            f"AND (last_fired_at IS NULL OR DATE(last_fired_at) < CURDATE())"
        )
        return jsonify({
            "profile": profile[0] if profile else None,
            "recent_summaries": recent,
            "pending_reminders": pending,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/portrait/<agent_id>/summaries")
@requires_auth
def list_summaries(agent_id):
    """列出历史每日摘要，供管理页查看"""
    try:
        agent_id = agent_id.replace("'", "")
        days = request.args.get("days", "30")
        rows = mysql_query(
            f"SELECT summary_date, overall_status, mood_companion, tomorrow_strategy, "
            f"medicine_status, fraud_risk, health_signals, family_note, raw_event_count, generated_at "
            f"FROM rl_daily_summary WHERE agent_id='{agent_id}' "
            f"ORDER BY summary_date DESC LIMIT {int(days)}"
        )
        return jsonify({"list": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/portrait/<agent_id>/events")
@requires_auth
def list_care_events(agent_id):
    """列出原始事件日志"""
    try:
        agent_id = agent_id.replace("'", "")
        days = request.args.get("days", "7")
        rows = mysql_query(
            f"SELECT event_type, event_time, summary, risk_level, handled, created_at "
            f"FROM rl_care_events WHERE agent_id='{agent_id}' "
            f"AND event_time >= DATE_SUB(NOW(), INTERVAL {int(days)} DAY) "
            f"ORDER BY event_time DESC LIMIT 200"
        )
        return jsonify({"list": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== 调试台 API =====

@app.route("/debug")
@requires_auth
def debug_page():
    return send_from_directory("static", "debug.html")


@app.route("/api/debug/config")
@requires_auth
def api_debug_config():
    rows = mysql_query("SELECT config_key, config_value, description FROM rl_system_config ORDER BY config_key")
    return jsonify(rows)


@app.route("/api/debug/config/<key>", methods=["PUT"])
@requires_auth
def api_debug_config_update(key):
    val = request.json.get("value", "0")
    mysql_exec(f"UPDATE rl_system_config SET config_value='{val}' WHERE config_key='{key}'")
    return jsonify({"ok": True})


@app.route("/api/debug/strategy/today")
@requires_auth
def api_debug_strategy_today():
    today = datetime.now().strftime("%Y-%m-%d")
    rows = mysql_query(f"SELECT strategy_text, created_at FROM rl_daily_strategy WHERE strategy_date='{today}' LIMIT 1")
    if rows:
        return jsonify(rows[0])
    return jsonify({})


@app.route("/api/debug/strategy/history")
@requires_auth
def api_debug_strategy_history():
    rows = mysql_query("SELECT strategy_date, strategy_text, created_at FROM rl_daily_strategy ORDER BY strategy_date DESC LIMIT 14")
    return jsonify(rows)


@app.route("/api/debug/strategy/generate", methods=["POST"])
@requires_auth
def api_debug_strategy_generate():
    try:
        agent_id = "1822c2babf1b44cca6b25d0bdebc796f"
        today = datetime.now().strftime("%Y-%m-%d")

        # Gather data
        portrait_rows = mysql_query(f"SELECT profile_json FROM rl_companion_profile WHERE agent_id='{agent_id}' ORDER BY updated_at DESC LIMIT 1")
        portrait = portrait_rows[0]["profile_json"][:1500] if portrait_rows else "{}"

        mood_rows = mysql_query(f"SELECT mood_date, dominant_emotion, summary FROM rl_mood_daily WHERE agent_id='{agent_id}' ORDER BY mood_date DESC LIMIT 3")
        event_rows = mysql_query(f"SELECT event_type, summary FROM rl_care_events WHERE agent_id='{agent_id}' AND ts >= DATE_SUB(NOW(), INTERVAL 3 DAY) ORDER BY ts DESC LIMIT 15")
        reminder_rows = mysql_query(f"SELECT title, remind_time, type FROM rl_reminders WHERE agent_id='{agent_id}' AND status IN ('active','pending') LIMIT 10")

        import json as jlib
        weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
        weekday = weekdays[datetime.now().weekday()]

        llm_prompt = f"""你是老年陪伴AI的策略引擎。根据以下数据生成"今日陪伴策略"。

要求：
1. 行为指令，不是信息描述。告诉AI"做什么"
2. 200字以内，分条
3. 涵盖：语气/动作频率/重点关注/主动话题/风险防范
4. 不能包含"画像""数据""分析""系统发现"
5. 用"铲屎官"称呼老人

今天 {today} {weekday}

【画像】{portrait[:1200]}
【近期情绪】{jlib.dumps(mood_rows, ensure_ascii=False)[:400]}
【活跃提醒】{jlib.dumps(reminder_rows, ensure_ascii=False)[:400]}
【近期事件】{jlib.dumps(event_rows, ensure_ascii=False)[:600]}

直接输出策略。"""

        r = requests.post(
            f"{ZHIPU_BASE}/chat/completions",
            headers=H,
            json={"model": "glm-4-flash", "messages": [{"role": "user", "content": llm_prompt}], "temperature": 0.7, "max_tokens": 500},
            timeout=30,
        )
        result = r.json()
        strategy = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if strategy:
            safe = strategy.replace("'", "\\'")
            safe_portrait = portrait[:300].replace("'", "\\'")
            mysql_exec(f"""INSERT INTO rl_daily_strategy (agent_id, strategy_date, strategy_text, source_portrait)
                VALUES ('{agent_id}', '{today}', '{safe}', '{safe_portrait}')
                ON DUPLICATE KEY UPDATE strategy_text='{safe}'""")

        return jsonify({"strategy": strategy or "生成失败"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/prompt-logs")
@requires_auth
def api_debug_prompt_logs():
    rows = mysql_query("SELECT id, device_mac, timestamp, CHAR_LENGTH(system_prompt) as prompt_length FROM rl_prompt_log ORDER BY timestamp DESC LIMIT 30")
    return jsonify(rows)


@app.route("/api/debug/prompt-logs/<int:log_id>")
@requires_auth
def api_debug_prompt_log_detail(log_id):
    rows = mysql_query(f"SELECT id, device_mac, timestamp, system_prompt FROM rl_prompt_log WHERE id={log_id}")
    if rows:
        return jsonify(rows[0])
    return jsonify({}), 404


@app.route("/api/debug/chat-history")
@requires_auth
def api_debug_chat_history():
    rows = mysql_query("SELECT chat_type, content, created_at FROM ai_agent_chat_history ORDER BY created_at DESC LIMIT 50")
    rows.reverse()
    return jsonify(rows)


# ===== 动作编排 API =====

@app.route("/actions")
@requires_auth
def actions_page():
    return send_from_directory("static", "actions.html")


@app.route("/api/actions/groups")
@requires_auth
def api_actions_groups():
    rows = mysql_query("SELECT group_code, group_name, description, default_intensity, sequences, forbidden FROM rl_action_config ORDER BY id")
    for r in rows:
        r["default_intensity"] = int(r.get("default_intensity", 1))
        r["sequences"] = json.loads(r.get("sequences", "[]"))
        r["forbidden"] = json.loads(r["forbidden"]) if r.get("forbidden") and r["forbidden"] != "NULL" else []
    return jsonify(rows)


@app.route("/api/actions/groups/<group_code>", methods=["PUT"])
@requires_auth
def api_actions_group_update(group_code):
    data = request.json
    sequences = json.dumps(data.get("sequences", []), ensure_ascii=False)
    intensity = int(data.get("default_intensity", 1))
    desc = data.get("description", "")
    forbidden = data.get("forbidden")
    forbidden_sql = f"'{json.dumps(forbidden, ensure_ascii=False)}'" if forbidden else "NULL"
    sql = f"""UPDATE rl_action_config SET
        sequences='{sequences}',
        default_intensity={intensity},
        description='{desc}',
        forbidden={forbidden_sql}
        WHERE group_code='{group_code}'"""
    mysql_exec(sql)
    return jsonify({"ok": True})


@app.route("/api/actions/bindings")
@requires_auth
def api_actions_bindings():
    rows = mysql_query("SELECT mode_code, max_intensity, allowed_groups, action_probability FROM rl_action_mode_bind ORDER BY id")
    for r in rows:
        r["max_intensity"] = int(r.get("max_intensity", 2))
        r["action_probability"] = float(r.get("action_probability", 0.3))
        r["allowed_groups"] = json.loads(r["allowed_groups"]) if r.get("allowed_groups") and r["allowed_groups"] != "NULL" else None
    return jsonify(rows)


@app.route("/api/actions/bindings", methods=["PUT"])
@requires_auth
def api_actions_bindings_update():
    data = request.json
    for item in data:
        mode = item["mode_code"]
        intensity = int(item["max_intensity"])
        prob = float(item["action_probability"])
        allowed = item.get("allowed_groups")
        allowed_sql = f"'{json.dumps(allowed, ensure_ascii=False)}'" if allowed else "NULL"
        sql = f"""INSERT INTO rl_action_mode_bind (mode_code, max_intensity, allowed_groups, action_probability)
            VALUES ('{mode}', {intensity}, {allowed_sql}, {prob})
            ON DUPLICATE KEY UPDATE max_intensity={intensity}, allowed_groups={allowed_sql}, action_probability={prob}"""
        mysql_exec(sql)
    return jsonify({"ok": True})


@app.route("/api/actions/test", methods=["POST"])
@requires_auth
def api_actions_test():
    data = request.json
    group = data.get("group", "idle")
    intensity = int(data.get("intensity", 1))
    rows = mysql_query(f"SELECT sequences FROM rl_action_config WHERE group_code='{group}'")
    if not rows:
        return jsonify({"message": f"未找到动作组: {group}"}), 404
    import random
    sequences = json.loads(rows[0]["sequences"])
    seq = random.choice(sequences) if sequences else []
    if intensity < 2 and len(seq) > 2:
        seq = seq[:2]
    return jsonify({"message": f"将执行序列: {' -> '.join(seq)}", "sequence": seq, "group": group, "intensity": intensity})

# ========== LLM 调用日志 ==========

@app.route("/llm-logs")
@requires_auth
def llm_logs_page():
    return send_from_directory("static", "llm-logs.html")


@app.route("/api/llm-logs")
@requires_auth
def api_llm_logs():
    try:
        rows = mysql_query(
            "SELECT id, agent_id, device_mac, model_name, duration_ms, created_at, "
            "LEFT(response_text, 100) AS response_preview, "
            "CASE WHEN tool_calls_json IS NOT NULL AND tool_calls_json != '' THEN 1 ELSE 0 END AS has_tool_calls "
            "FROM rl_llm_log ORDER BY created_at DESC LIMIT 50"
        )
        for r in rows:
            r["has_tool_calls"] = int(r.get("has_tool_calls", 0))
            r["duration_ms"] = int(r.get("duration_ms", 0)) if r.get("duration_ms") else 0
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm-logs/<int:log_id>")
@requires_auth
def api_llm_log_detail(log_id):
    try:
        rows = mysql_query(
            f"SELECT id, agent_id, device_mac, model_name, duration_ms, created_at, "
            f"messages_json, response_text, tool_calls_json "
            f"FROM rl_llm_log WHERE id={log_id}"
        )
        if not rows:
            return jsonify({"error": "not found"}), 404
        return jsonify(rows[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ========== 系统设置 ==========

@app.route("/settings")
@requires_auth
def settings_page():
    return send_from_directory("static", "settings.html")


@app.route("/api/settings", methods=["GET"])
@requires_auth
def api_settings_get():
    try:
        rows = mysql_query("SELECT config_key, config_value, description, updated_at FROM rl_system_config ORDER BY config_key")
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings/<config_key>", methods=["PUT"])
@requires_auth
def api_settings_put(config_key):
    # Guard: only allow known keys
    ALLOWED_KEYS = {
        "strategy_enabled", "strategy_auto_generate",
        "reminder_enabled", "end_prompt_enabled",
        "asr_max_sentence_silence", "close_connection_timeout",
        "voiceprint_enabled", "voiceprint_threshold", "voiceprint_reject_text",
        "kid_mode_enabled", "kid_default_age_band",
    }
    if config_key not in ALLOWED_KEYS:
        return jsonify({"error": "unknown key"}), 400
    data = request.get_json(silent=True) or {}
    value = str(data.get("value", "")).replace("'", "")
    try:
        mysql_exec(
            f"INSERT INTO rl_system_config (config_key, config_value) VALUES ('{config_key}', '{value}') "
            f"ON DUPLICATE KEY UPDATE config_value='{value}', updated_at=NOW()"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings/apply-config", methods=["PUT"])
@requires_auth
def api_settings_apply_config():
    """Apply config values to config.yaml inside the Docker container."""
    import subprocess, os
    CONTAINER = "xiaozhi-esp32-server"
    CONFIG_PATH = "/opt/xiaozhi-esp32-server/config.yaml"
    try:
        rows = mysql_query(
            "SELECT config_key, config_value FROM rl_system_config "
            "WHERE config_key IN ('asr_max_sentence_silence', 'close_connection_timeout', 'end_prompt_enabled')"
        )
        kv = {r["config_key"]: r["config_value"] for r in rows}
        applied = []

        script_lines = []
        script_lines.append("import re")
        script_lines.append("path = '" + CONFIG_PATH + "'")
        script_lines.append("with open(path, 'r', encoding='utf-8') as f: text = f.read()")

        if "asr_max_sentence_silence" in kv:
            val = max(200, min(6000, int(kv["asr_max_sentence_silence"])))
            script_lines.append(
                "text = re.sub(r'(max_sentence_silence:\s*)\d+', r'\g<1>" + str(val) + "', text)"
            )
            applied.append("asr_max_sentence_silence=" + str(val))

        if "close_connection_timeout" in kv:
            val = max(30, min(600, int(kv["close_connection_timeout"])))
            script_lines.append(
                "text = re.sub(r'(close_connection_no_voice_time:\s*)\d+', r'\g<1>" + str(val) + "', text)"
            )
            applied.append("close_connection_timeout=" + str(val))

        if "end_prompt_enabled" in kv:
            enable_val = "true" if kv["end_prompt_enabled"] == "1" else "false"
            script_lines.append("lines = text.split(chr(10))")
            script_lines.append("fp = False")
            script_lines.append("for i, ln in enumerate(lines):")
            script_lines.append("  if 'end_prompt:' in ln and not ln.strip().startswith('#'): fp = True")
            script_lines.append("  elif fp and 'enable:' in ln:")
            script_lines.append("    lines[i] = re.sub(r'(enable:\s*)(true|false)', r'\g<1>" + enable_val + "', ln)")
            script_lines.append("    break")
            script_lines.append("text = chr(10).join(lines)")
            applied.append("end_prompt_enabled=" + enable_val)

        script_lines.append("with open(path, 'w', encoding='utf-8') as f: f.write(text)")
        script_lines.append("print('ok')")

        script_text = chr(10).join(script_lines)
        tmp_path = "/tmp/_apply_config.py"
        with open(tmp_path, "w") as f:
            f.write(script_text)

        subprocess.run(["docker", "cp", tmp_path, CONTAINER + ":/tmp/_apply_config.py"],
                       capture_output=True, timeout=5)
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "python3", "/tmp/_apply_config.py"],
            capture_output=True, text=True, timeout=10
        )
        os.remove(tmp_path)

        if result.returncode != 0:
            return jsonify({"error": "apply failed: " + result.stderr}), 500

        return jsonify({"ok": True, "applied": applied, "note": "config.yaml updated, restart container to take effect"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices/live", methods=["GET"])
@requires_auth
def api_devices_live():
    def build_database_fallback_response():
        rows = mysql_query(
            "SELECT d.id, d.mac_address, d.alias, d.board, d.app_version, d.agent_id, "
            "d.last_connected_at, d.update_date, a.agent_name "
            "FROM ai_device d "
            "LEFT JOIN ai_agent a ON d.agent_id = a.id "
            "ORDER BY COALESCE(d.last_connected_at, d.update_date) DESC "
            "LIMIT 200"
        )
        items = []
        child_memory_by_device = _load_child_memory_summaries(
            [
                device_key
                for row in rows
                for device_key in (row.get("id"), row.get("mac_address"))
            ]
        )
        for row in rows:
            device_id = str(row.get("id") or "").strip()
            device_mac = str(row.get("mac_address") or "").strip()
            last_connected_at = _parse_db_datetime_to_ts(row.get("last_connected_at"))
            update_date = _parse_db_datetime_to_ts(row.get("update_date"))
            last_ts = last_connected_at or update_date
            child_memory = child_memory_by_device.get(device_id.lower()) or child_memory_by_device.get(device_mac.lower())
            robot_name = (
                str((child_memory or {}).get("robot_name_preference") or "").strip()
                or (_resolve_effective_robot_identity_name(device_id) if device_id else "")
            )
            items.append(
                {
                    "device_id": device_id,
                    "device_mac": device_mac,
                    "agent_id": str(row.get("agent_id") or "").strip(),
                    "agent_name": str(row.get("agent_name") or "").strip(),
                    "robot_name": robot_name,
                    "child_memory": child_memory,
                    "alias": str(row.get("alias") or "").strip(),
                    "board": str(row.get("board") or "").strip(),
                    "app_version": str(row.get("app_version") or "").strip(),
                    "client_id": "",
                    "client_ip": "",
                    "connected_at": last_connected_at,
                    "last_activity_at": last_ts,
                    "last_seen_at": last_ts,
                    "idle_seconds": None,
                    "connection_alive": False,
                    "conn_from_mqtt_gateway": False,
                    "session_id": "",
                    "source": "database_fallback",
                }
            )
        return {
            "ok": True,
            "count": len(items),
            "devices": items,
            "source": "database_fallback",
            "live_supported": False,
        }

    try:
        live_devices = []
        runtime_ok = False
        try:
            response = requests.get(
                f"{XIAOZHI_DEBUG_HTTP_BASE.rstrip('/')}/debug/runtime/live-devices",
                headers={"x-debug-token": XIAOZHI_DEBUG_AUTH_SECRET},
                timeout=5,
            )
            payload = response.json() if response.content else {}
            if response.status_code < 400:
                live_devices = payload.get("devices") or []
                runtime_ok = True
        except Exception:
            runtime_ok = False

        if not runtime_ok:
            return jsonify(build_database_fallback_response())

        sql = (
            "SELECT d.id, d.mac_address, d.alias, d.board, d.app_version, d.agent_id, a.agent_name "
            "FROM ai_device d "
            "LEFT JOIN ai_agent a ON d.agent_id = a.id"
        )
        rows = mysql_query(sql)
        device_meta = {}
        for row in rows:
            device_id = str(row.get("id") or "").strip()
            mac_address = str(row.get("mac_address") or "").strip()
            alias = str(row.get("alias") or "").strip()
            board = str(row.get("board") or "").strip()
            app_version = str(row.get("app_version") or "").strip()
            agent_id = str(row.get("agent_id") or "").strip()
            agent_name = str(row.get("agent_name") or "").strip()
            for key in (device_id.lower(), mac_address.lower()):
                if key:
                    device_meta[key] = {
                        "device_id": device_id,
                        "mac_address": mac_address,
                        "alias": alias,
                        "board": board,
                        "app_version": app_version,
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                    }

        child_memory_by_device = _load_child_memory_summaries(
            [
                device_key
                for meta in device_meta.values()
                for device_key in (meta.get("device_id"), meta.get("mac_address"))
            ]
        )
        items = []
        for entry in live_devices:
            normalized_device_id = str(entry.get("device_id") or "").strip()
            meta = device_meta.get(normalized_device_id.lower(), {})
            resolved_device_id = meta.get("device_id") or normalized_device_id
            resolved_device_mac = meta.get("mac_address") or normalized_device_id
            child_memory = (
                child_memory_by_device.get(resolved_device_id.lower())
                or child_memory_by_device.get(resolved_device_mac.lower())
                or child_memory_by_device.get(normalized_device_id.lower())
            )
            robot_name = (
                str((child_memory or {}).get("robot_name_preference") or "").strip()
                or _resolve_effective_robot_identity_name(resolved_device_id)
            )
            items.append(
                {
                    "device_id": resolved_device_id,
                    "device_mac": resolved_device_mac,
                    "agent_id": meta.get("agent_id") or "",
                    "agent_name": meta.get("agent_name") or "",
                    "robot_name": robot_name,
                    "child_memory": child_memory,
                    "alias": meta.get("alias") or "",
                    "board": meta.get("board") or "",
                    "app_version": meta.get("app_version") or "",
                    "client_id": str(entry.get("client_id") or ""),
                    "client_ip": str(entry.get("client_ip") or ""),
                    "connected_at": entry.get("connected_at"),
                    "last_activity_at": entry.get("last_activity_at"),
                    "last_seen_at": entry.get("last_seen_at"),
                    "idle_seconds": entry.get("idle_seconds"),
                    "connection_alive": bool(entry.get("connection_alive")),
                    "conn_from_mqtt_gateway": bool(entry.get("conn_from_mqtt_gateway")),
                    "session_id": str(entry.get("session_id") or ""),
                    "source": "runtime",
                }
            )

        return jsonify({
            "ok": True,
            "count": len(items),
            "devices": items,
            "source": "runtime",
            "live_supported": True,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/age-profiles", methods=["GET"])
@requires_auth
def api_age_profiles_get():
    try:
        profiles = _load_age_profiles()
        rows = []
        for age_group in ("3-5", "6-8", "9-11"):
            item = dict(profiles.get(age_group) or DEFAULT_AGE_PROFILES[age_group])
            item["age_group"] = age_group
            rows.append(item)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/age-profiles/<age_group>", methods=["PUT"])
@requires_auth
def api_age_profiles_put(age_group):
    if age_group not in DEFAULT_AGE_PROFILES:
        return jsonify({"error": "unknown age_group"}), 400

    data = request.get_json(silent=True) or {}
    allowed_fields = (
        "vocabulary_level",
        "max_new_concepts",
        "abstract_concept_level",
        "question_style",
        "support_level",
    )
    try:
        profiles = _load_age_profiles()
        existing = dict(profiles.get(age_group) or DEFAULT_AGE_PROFILES[age_group])
        for field_name in allowed_fields:
            if field_name not in data:
                continue
            existing[field_name] = _normalize_age_profile_value(field_name, data.get(field_name))
        profiles[age_group] = existing
        _save_age_profiles(profiles)
        response = dict(existing)
        response["age_group"] = age_group
        return jsonify({"ok": True, "profile": response, "config_path": AGE_PROFILE_CONFIG_PATH})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/dingyi-models")
@requires_auth
def page_dingyi_models():
    return send_from_directory("static", "dingyi-models.html")


@app.route("/dingyi-chat")
@requires_auth
def page_dingyi_chat():
    return send_from_directory("static", "dingyi-chat.html")


def _sql_safe(value):
    return str(value).replace("'", "''")


def _load_dingyiguo_llm_binding():
    binding_rows = mysql_query(
        "SELECT a.id AS agent_id, a.agent_name, a.llm_model_id, "
        "m.model_name, m.config_json "
        "FROM ai_agent a "
        "LEFT JOIN ai_model_config m ON a.llm_model_id = m.id "
        f"WHERE a.id='{DINGYIGUO_AGENT_ID}' LIMIT 1"
    )
    if not binding_rows:
        raise RuntimeError("丁一锅 agent 不存在")
    prompt_rows = mysql_query(
        "SELECT HEX(CAST(system_prompt AS BINARY)) AS system_prompt_hex, "
        "HEX(CAST(summary_memory AS BINARY)) AS summary_memory_hex "
        "FROM ai_agent "
        f"WHERE id='{DINGYIGUO_AGENT_ID}' LIMIT 1"
    )
    row = binding_rows[0]
    prompt_row = prompt_rows[0] if prompt_rows else {}
    raw = row.get("config_json") or "{}"
    try:
        cfg = json.loads(raw)
    except Exception:
        cfg = {}

    def _decode_hex(value):
        if not value or value == "NULL":
            return ""
        try:
            return bytes.fromhex(value).decode("utf-8", errors="replace")
        except Exception:
            return ""

    return {
        "agent_id": row.get("agent_id"),
        "agent_name": row.get("agent_name"),
        "llm_model_id": row.get("llm_model_id"),
        "llm_model_name": row.get("model_name"),
        "system_prompt": _decode_hex(prompt_row.get("system_prompt_hex")),
        "summary_memory": _decode_hex(prompt_row.get("summary_memory_hex")),
        "config": cfg,
    }


def _save_dingyiguo_llm_config(binding, cfg):
    safe_cfg = _sql_safe(json.dumps(cfg, ensure_ascii=False))
    safe_model_id = _sql_safe(binding["llm_model_id"])
    mysql_exec(
        "UPDATE ai_model_config "
        f"SET config_json='{safe_cfg}', update_date=NOW() "
        f"WHERE id='{safe_model_id}'"
    )


def _fetch_model_ids(base_url, api_key):
    if not base_url or not api_key:
        return [], "未配置 base_url 或 api_key"

    resp = requests.get(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20,
    )
    body = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {}
    if not resp.ok:
        detail = body or resp.text[:1000]
        return [], f"模型列表请求失败: HTTP {resp.status_code} {detail}"

    model_ids = []
    for item in body.get("data", []):
        model_id = item.get("id")
        if model_id:
            model_ids.append(model_id)
    return model_ids, ""


def _call_dingyiguo_chat(messages):
    binding = _load_dingyiguo_llm_binding()
    cfg = binding["config"]
    base_url = (cfg.get("base_url") or cfg.get("url") or "").strip()
    api_key = (cfg.get("api_key") or "").strip()
    model_name = (cfg.get("model_name") or "").strip()
    if not base_url or not api_key or not model_name:
        raise RuntimeError("丁一锅当前 LLM 配置不完整")

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }

    for key in ("max_tokens", "temperature", "top_p", "frequency_penalty"):
        value = cfg.get(key)
        if value in (None, ""):
            continue
        try:
            payload[key] = int(value) if key == "max_tokens" else float(value)
        except (TypeError, ValueError):
            pass

    resp = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    body = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {}
    if not resp.ok:
        detail = body or resp.text[:1000]
        raise RuntimeError(f"对话请求失败: HTTP {resp.status_code} {detail}")

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("模型返回为空")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return {
        "reply": str(content).strip(),
        "binding": binding,
        "usage": body.get("usage") or {},
        "model": body.get("model") or model_name,
    }


@app.route("/api/dingyi-models", methods=["GET"])
@requires_auth
def api_dingyi_models():
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = binding["config"]
        base_url = (cfg.get("base_url") or cfg.get("url") or "").strip()
        api_key = (cfg.get("api_key") or "").strip()
        current_model_name = (cfg.get("model_name") or "").strip()
        model_ids, models_error = _fetch_model_ids(base_url, api_key)

        return jsonify({
            "binding": binding,
            "source": {
                "base_url": base_url,
                "api_key": api_key,
                "api_key_masked": (api_key[:6] + "..." + api_key[-4:]) if len(api_key) > 12 else api_key,
                "models_url": base_url.rstrip("/") + "/models",
            },
            "models": model_ids,
            "current_model_name": current_model_name,
            "models_error": models_error,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-chat/config", methods=["GET"])
@requires_auth
def api_dingyi_chat_config():
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = binding["config"]
        return jsonify({
            "agent_id": binding["agent_id"],
            "agent_name": binding["agent_name"],
            "llm_model_id": binding["llm_model_id"],
            "llm_model_name": binding["llm_model_name"],
            "model_name": (cfg.get("model_name") or "").strip(),
            "base_url": (cfg.get("base_url") or cfg.get("url") or "").strip(),
            "has_api_key": bool((cfg.get("api_key") or "").strip()),
            "system_prompt": binding.get("system_prompt") or "",
            "summary_memory": binding.get("summary_memory") or "",
            "runtime_mode": "shared_live_or_text_fallback",
            "runtime_ws_base": XIAOZHI_DEBUG_HTTP_BASE,
            "runtime_device_id": XIAOZHI_DEBUG_DEVICE_ID,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-chat/send", methods=["POST"])
@requires_auth
def api_dingyi_chat_send():
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()
    history = data.get("history") or []
    session_key = (data.get("session_key") or "").strip()
    device_id = (data.get("device_id") or "").strip() or XIAOZHI_DEBUG_DEVICE_ID
    if not user_text:
        return jsonify({"error": "text required"}), 400
    if not isinstance(history, list):
        return jsonify({"error": "history must be a list"}), 400
    if not session_key:
        return jsonify({"error": "session_key required"}), 400

    try:
        binding = _load_dingyiguo_llm_binding()
        runtime_session = _get_robot_debug_session(session_key, device_id=device_id)
        try:
            result = runtime_session.send_turn(user_text)
        except Exception as first_error:
            if "上一轮回复仍未完成" not in str(first_error):
                raise
            _reset_robot_debug_session(session_key, device_id=device_id)
            runtime_session = _get_robot_debug_session(session_key, device_id=device_id)
            result = runtime_session.send_turn(user_text)
        runtime_debug = result.get("runtime_debug") or {}
        return jsonify({
            "ok": True,
            "reply": result["reply"],
            "model": "xiaozhi_server_runtime",
            "usage": {},
            "agent_name": binding["agent_name"],
            "scene": runtime_debug.get("scene"),
            "dialogue_state": runtime_debug.get("dialogue_state"),
            "response_plan": runtime_debug.get("response_plan"),
            "response_rewrite": runtime_debug.get("response_rewrite"),
            "daily_greeting": runtime_debug.get("daily_greeting"),
            "conversation_openness": runtime_debug.get("conversation_openness"),
            "long_term_memory": runtime_debug.get("long_term_memory"),
            "debug_source": "runtime",
            "runtime_mode": result.get("mode") or "unknown",
            "runtime_session_key": session_key,
            "runtime_device_id": result.get("device_id") or device_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-chat/reset", methods=["POST"])
@requires_auth
def api_dingyi_chat_reset():
    data = request.get_json(silent=True) or {}
    session_key = (data.get("session_key") or "").strip()
    device_id = (data.get("device_id") or "").strip() or XIAOZHI_DEBUG_DEVICE_ID
    if not session_key:
        return jsonify({"error": "session_key required"}), 400
    _reset_robot_debug_session(session_key, device_id=device_id)
    return jsonify({"ok": True})


@app.route("/api/scene-router/scenes", methods=["GET"])
@requires_auth
def api_scene_router_scenes():
    try:
        return jsonify({
            "ok": True,
            **_load_scene_router_snapshot(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scene-router/interaction-policy/<scene_name>", methods=["PUT"])
@requires_auth
def api_scene_router_interaction_policy_put(scene_name):
    data = request.get_json(silent=True) or {}
    allowed_fields = (
        "information_budget",
        "reasoning_depth",
        "interaction_style",
        "conversation_pacing",
        "emotional_priority",
    )
    try:
        policies = _load_interaction_policies()
        existing = dict(policies.get(scene_name) or _build_default_interaction_policy(scene_name))
        for field_name in allowed_fields:
            if field_name not in data:
                continue
            existing[field_name] = _normalize_interaction_policy_value(field_name, data.get(field_name))
        policies[scene_name] = existing
        _save_interaction_policies(policies)
        return jsonify({
            "ok": True,
            "scene_name": scene_name,
            "interaction_policy": existing,
            "config_path": INTERACTION_POLICY_CONFIG_PATH,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scene-router/scene-interest-config/<scene_name>", methods=["PUT"])
@requires_auth
def api_scene_router_scene_interest_config_put(scene_name):
    data = request.get_json(silent=True) or {}
    allowed_fields = (
        "use_interest_examples",
        "use_interest_story",
        "use_interest_games",
        "use_interest_conversation",
    )
    try:
        configs = _load_scene_interest_configs()
        existing = dict(configs.get(scene_name) or _build_default_scene_interest_config(scene_name))
        for field_name in allowed_fields:
            if field_name not in data:
                continue
            existing[field_name] = _normalize_scene_interest_config_value(field_name, data.get(field_name))
        configs[scene_name] = existing
        _save_scene_interest_configs(configs)
        return jsonify({
            "ok": True,
            "scene_name": scene_name,
            "scene_interest_config": existing,
            "config_path": SCENE_INTEREST_CONFIG_PATH,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interests/config", methods=["GET"])
@requires_auth
def api_interests_config():
    try:
        config = _load_interest_influence_config()
        return jsonify({
            "ok": True,
            **config,
            "config_path": INTERESTS_CONFIG_PATH,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interests/config", methods=["PUT"])
@requires_auth
def api_interests_config_put():
    data = request.get_json(silent=True) or {}
    allowed_fields = (
        "example_bias",
        "story_bias",
        "conversation_bias",
        "game_bias",
        "memory_reference",
    )
    try:
        config = _load_interest_influence_config()
        existing = dict(config.get("interest_influence") or DEFAULT_INTEREST_INFLUENCE_POLICY)
        for field_name in allowed_fields:
            if field_name not in data:
                continue
            existing[field_name] = _normalize_interest_influence_value(field_name, data.get(field_name))
        adapter = json.loads(json.dumps(DEFAULT_INTEREST_ADAPTER, ensure_ascii=False))
        incoming_adapter = data.get("interest_adapter")
        if isinstance(incoming_adapter, dict):
            for topic_key, defaults in DEFAULT_INTEREST_ADAPTER.items():
                incoming_topic = incoming_adapter.get(topic_key)
                if not isinstance(incoming_topic, dict):
                    continue
                merged_topic = dict(defaults)
                for field_name in defaults.keys():
                    if field_name not in incoming_topic:
                        continue
                    merged_topic[field_name] = _normalize_interest_context_list(incoming_topic.get(field_name))
                adapter[topic_key] = merged_topic
        config["interest_influence"] = existing
        config["favorite_topics"] = list(DEFAULT_INTEREST_TOPICS)
        config["interest_adapter"] = adapter
        _save_interest_influence_config(config)
        return jsonify({
            "ok": True,
            "interest_influence": existing,
            "favorite_topics": config["favorite_topics"],
            "interest_adapter": config["interest_adapter"],
            "config_path": INTERESTS_CONFIG_PATH,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/robot-profile", methods=["GET"])
@requires_auth
def api_robot_profile_get():
    try:
        config = _load_robot_profile_config()
        effective_identity_name = _resolve_effective_robot_identity_name()
        payload = json.loads(json.dumps(config, ensure_ascii=False))
        if effective_identity_name:
            payload["identity"]["name"] = effective_identity_name
        return jsonify({
            "ok": True,
            **payload,
            "configured_identity_name": str(config.get("identity", {}).get("name") or "").strip(),
            "effective_identity_name": effective_identity_name,
            "runtime_device_id": XIAOZHI_DEBUG_DEVICE_ID,
            "config_path": ROBOT_PROFILE_CONFIG_PATH,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/robot-profile", methods=["PUT"])
@requires_auth
def api_robot_profile_put():
    data = request.get_json(silent=True) or {}
    try:
        config = _load_robot_profile_config()
        for section_name in ("identity", "personality", "values"):
            incoming = data.get(section_name)
            if not isinstance(incoming, dict):
                continue
            section = dict(config[section_name])
            for key, default_value in section.items():
                if key not in incoming:
                    continue
                if isinstance(default_value, list):
                    normalized = _normalize_robot_profile_list(incoming.get(key))
                    if normalized:
                        section[key] = normalized
                else:
                    text = str(incoming.get(key) or "").strip()
                    if text:
                        section[key] = text
            config[section_name] = section

        _save_robot_profile_config(config)
        return jsonify({
            "ok": True,
            **config,
            "config_path": ROBOT_PROFILE_CONFIG_PATH,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/greeting/config", methods=["GET"])
@requires_auth
def api_greeting_config_get():
    try:
        config = _load_daily_greeting_config()
        return jsonify({
            "ok": True,
            **config,
            "config_path": DAILY_GREETING_CONFIG_PATH,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/greeting-sources/devices", methods=["GET"])
@requires_auth
def api_greeting_sources_devices():
    try:
        target_date, start_ms, end_ms = _date_window_ms(request.args.get("date"))
        devices = []
        for row in _mysql_short_memory_rows():
            topics = list((row.get("memory") or {}).get("topics") or [])
            candidate_count = sum(
                1 for topic in topics
                if _is_daily_followup_candidate(topic, start_ms, end_ms)
            )
            devices.append(
                {
                    "device_id": row.get("device_id"),
                    "updated_at": row.get("updated_at"),
                    "topic_count": len(topics),
                    "candidate_count": candidate_count,
                    "selected": _selected_daily_greeting_for_device(row.get("device_id")),
                }
            )
        return jsonify({
            "ok": True,
            "date": target_date,
            "devices": devices,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/greeting-sources/device/<path:device_id>", methods=["GET"])
@requires_auth
def api_greeting_sources_device(device_id):
    try:
        target_date, start_ms, end_ms = _date_window_ms(request.args.get("date"))
        normalized = str(device_id or "").strip()
        matched = None
        for row in _mysql_short_memory_rows():
            if str(row.get("device_id") or "").strip() == normalized:
                matched = row
                break
        if matched is None:
            return jsonify({"error": "device not found"}), 404
        topics = list((matched.get("memory") or {}).get("topics") or [])
        candidates = [
            _build_greeting_source_candidate(topic)
            for topic in topics
            if _is_daily_followup_candidate(topic, start_ms, end_ms)
        ]
        candidates.sort(
            key=lambda item: (
                float(item.get("greeting_score") or 0),
                int(item.get("greeting_candidate_type_priority") or 0),
                {"health": 5, "emotion": 4, "task": 3, "event": 2}.get(str(item.get("memory_type") or ""), 0),
                float(item.get("importance") or 0),
                int(item.get("last_active_at_ms") or 0),
            ),
            reverse=True,
        )
        selected = _selected_daily_greeting_for_device(normalized)
        selected_source = str(selected.get("source_id") or "")
        for candidate in candidates:
            candidate["selected_by_daily_greeting"] = bool(
                selected_source and selected_source == str(candidate.get("source_id") or "")
            )
        return jsonify({
            "ok": True,
            "date": target_date,
            "device_id": normalized,
            "updated_at": matched.get("updated_at"),
            "selected": selected,
            "candidates": candidates,
            "candidate_count": len(candidates),
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/greeting/config", methods=["PUT"])
@requires_auth
def api_greeting_config_put():
    data = request.get_json(silent=True) or {}
    try:
        config = _load_daily_greeting_config()
        for field_name in (
            "enabled",
            "first_meaningful_interaction_only",
            "mark_delivered_once_per_day",
            "block_on_higher_priority_interruptions",
        ):
            if field_name in data:
                config[field_name] = bool(data.get(field_name))

        if "version" in data:
            try:
                config["version"] = max(1, int(data.get("version")))
            except (TypeError, ValueError):
                pass

        if "goal" in data:
            config["goal"] = str(data.get("goal") or "").strip() or config["goal"]

        for field_name in (
            "trigger_conditions",
            "pipeline",
            "greeting_structure",
            "selection_rules",
            "design_principles",
            "future_extensions",
        ):
            if field_name not in data:
                continue
            normalized = _normalize_daily_text_list(data.get(field_name))
            if normalized:
                config[field_name] = normalized

        incoming_state = data.get("state_example")
        if isinstance(incoming_state, dict):
            state = dict(config["state_example"])
            for key in state.keys():
                if key not in incoming_state:
                    continue
                if key == "delivered":
                    state[key] = bool(incoming_state.get(key))
                else:
                    state[key] = str(incoming_state.get(key) or "").strip() or state[key]
            config["state_example"] = state

        incoming_types = data.get("greeting_types")
        if isinstance(incoming_types, dict):
            normalized_types = {}
            for type_name in DEFAULT_DAILY_GREETING_CONFIG["greeting_types"].keys():
                normalized_types[type_name] = _normalize_daily_greeting_type(
                    type_name,
                    incoming_types.get(type_name),
                )
            config["greeting_types"] = normalized_types

        if "boot_greeting" in data:
            config["boot_greeting"] = _normalize_boot_greeting_config(
                data.get("boot_greeting")
            )

        _save_daily_greeting_config(config)
        return jsonify({
            "ok": True,
            **config,
            "config_path": DAILY_GREETING_CONFIG_PATH,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-models/config", methods=["POST"])
@requires_auth
def api_dingyi_models_config():
    data = request.get_json(silent=True) or {}
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = dict(binding["config"])
        if "base_url" in data:
            cfg["base_url"] = (data.get("base_url") or "").strip()
        if "api_key" in data:
            cfg["api_key"] = (data.get("api_key") or "").strip()
        if "model_name" in data:
            cfg["model_name"] = (data.get("model_name") or "").strip()
        _save_dingyiguo_llm_config(binding, cfg)
        return jsonify({
            "ok": True,
            "agent_id": binding["agent_id"],
            "agent_name": binding["agent_name"],
            "llm_model_id": binding["llm_model_id"],
            "config": {
                "base_url": cfg.get("base_url") or cfg.get("url") or "",
                "api_key": cfg.get("api_key") or "",
                "model_name": cfg.get("model_name") or "",
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-models/switch", methods=["POST"])
@requires_auth
def api_dingyi_models_switch():
    data = request.get_json(silent=True) or {}
    model_name = (data.get("model_name") or "").strip()
    if not model_name:
        return jsonify({"error": "model_name required"}), 400
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = dict(binding["config"])
        cfg["model_name"] = model_name
        _save_dingyiguo_llm_config(binding, cfg)
        return jsonify({
            "ok": True,
            "agent_id": binding["agent_id"],
            "agent_name": binding["agent_name"],
            "llm_model_id": binding["llm_model_id"],
            "model_name": model_name,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not ZHIPU_API_KEY:
        raise SystemExit("env ZHIPU_API_KEY 未设")
    if not ADMIN_PASS:
        raise SystemExit("env KB_ADMIN_PASS 未设")
    app.run(host="0.0.0.0", port=8888)
