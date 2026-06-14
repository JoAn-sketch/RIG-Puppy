from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChildProfile:
    age_band: str = "6-8"


@dataclass
class DialogState:
    current_scene: Optional[str] = None
    current_subscene: Optional[str] = None
    turn_index: int = 0
    question_count_in_current_topic: int = 0
    last_policy: Optional[str] = None


@dataclass
class SignalState:
    emotion_hint: str = "neutral"
    interruption: bool = False
    silence_ms: int = 0
    vlm_tags: List[str] = field(default_factory=list)


@dataclass
class SceneRouterInput:
    text: str
    asr_confidence: float = 1.0
    child_profile: ChildProfile = field(default_factory=ChildProfile)
    dialog_state: DialogState = field(default_factory=DialogState)
    signals: SignalState = field(default_factory=SignalState)


@dataclass
class SceneRouterOutput:
    primary_scene: str
    secondary_scene: Optional[str]
    subscene: str
    risk_level: str
    emotion_state: str
    age_band: str
    policy_profile: str
    should_use_rag: bool
    should_use_memory: bool
    should_use_vlm: bool
    should_escalate_parent: bool
    should_force_safe_template: bool
    interaction_protocol: str
    protocol_mode: str
    confidence: float
    reason_codes: List[str] = field(default_factory=list)
