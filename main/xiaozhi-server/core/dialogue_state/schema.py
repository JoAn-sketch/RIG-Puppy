from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from core.scene_router.schema import SceneRouterOutput


@dataclass
class RuntimeSignals:
    emotion_hint: str = "neutral"
    interruption: bool = False
    silence_ms: int = 0
    user_move: str = "unknown"
    understanding_signal: str = "unknown"
    topic_switch_signal: bool = False
    frustration_signal: int = 0
    conversation_openness_level: int = 3
    conversation_openness_reason: str = "neutral_default"


@dataclass
class ChildProfileSnapshot:
    nickname: str = ""
    age: Optional[int] = None
    age_group: str = "6-8"
    age_band: str = "6-8"
    language_level: str = "child_basic"
    interests: List[str] = field(default_factory=list)


@dataclass
class DialogueStateManagerInput:
    text: str
    scene_router_output: SceneRouterOutput
    timestamp_ms: int = 0
    dialogue_state: Optional[Dict[str, Any]] = None
    signals: RuntimeSignals = field(default_factory=RuntimeSignals)
    child_profile: ChildProfileSnapshot = field(default_factory=ChildProfileSnapshot)


@dataclass
class DialogueControlOutput:
    current_scene: str
    current_subscene: str
    current_phase: str
    next_action: str
    interaction_protocol: str
    protocol_mode: str
    protocol_stage: str
    reply_style: str
    max_reply_sentences: int
    should_ask_followup: bool
    should_close_scene: bool
    should_switch_scene: bool
    should_use_memory: bool
    should_use_rag: bool
    should_force_safe_template: bool
    conversation_openness_level: int
    conversation_openness_reason: str
    turn_contract: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DialogueDebugOutput:
    transition_reason: str
    scene_changed: bool
    phase_changed: bool
    matched_rule: str
    router_confidence: float
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DialogueStateManagerResult:
    state: Dict[str, Any]
    control: DialogueControlOutput
    debug: DialogueDebugOutput

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "control": self.control.to_dict(),
            "debug": self.debug.to_dict(),
        }
