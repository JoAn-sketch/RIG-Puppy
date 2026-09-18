from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, Optional


LIFECYCLE_LISTENING = "LISTENING"
LIFECYCLE_IDLE = "IDLE"

INTERACTION_CONTINUATION = "CONTINUATION"
INTERACTION_NEW = "NEW_INTERACTION"


@dataclass
class ConversationContext:
    """Current conversation context for a runtime session.

    The context is a pure state container. It does not call LLM, memory,
    scene routing, tools, TTS, or make dialogue policy decisions.
    """

    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4().hex))
    lifecycle_state: str = LIFECYCLE_IDLE
    interaction_mode: str = INTERACTION_NEW
    current_topic: Any = None
    dialogue_state: Any = None
    short_term_memory: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.metadata.setdefault("started_at", 0.0)
        self.metadata.setdefault("last_interaction_at", 0.0)
        self.metadata.setdefault("transition_reason", "initial")

    @property
    def last_interaction_at(self) -> float:
        return float(self.metadata.get("last_interaction_at") or 0.0)

    @property
    def transition_reason(self) -> str:
        return str(self.metadata.get("transition_reason") or "")

    def start_interaction(self, timestamp: Optional[float] = None, reason: str = "user_input") -> str:
        timestamp = float(timestamp or time.time())
        interaction_mode = (
            INTERACTION_CONTINUATION
            if self.lifecycle_state == LIFECYCLE_LISTENING
            else INTERACTION_NEW
        )
        if interaction_mode == INTERACTION_NEW:
            self.conversation_id = str(uuid.uuid4().hex)
            self.current_topic = None
            self.dialogue_state = None
            self.metadata["started_at"] = timestamp
        self.lifecycle_state = LIFECYCLE_LISTENING
        self.interaction_mode = interaction_mode
        self.metadata["last_interaction_at"] = timestamp
        self.metadata["transition_reason"] = reason
        return interaction_mode

    def mark_idle(self, reason: str = "idle") -> None:
        self.lifecycle_state = LIFECYCLE_IDLE
        self.interaction_mode = INTERACTION_NEW
        self.metadata["transition_reason"] = reason

    def update_after_turn(
        self,
        *,
        current_topic: Any = None,
        dialogue_state: Any = None,
        short_term_memory: Any = None,
        last_interaction_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if current_topic is not None:
            self.current_topic = current_topic
        if dialogue_state is not None:
            self.dialogue_state = dialogue_state
        if short_term_memory is not None:
            self.short_term_memory = short_term_memory
        if last_interaction_at is not None:
            self.metadata["last_interaction_at"] = float(last_interaction_at)
        if metadata:
            self.metadata.update(dict(metadata))

    def reset(self, reason: str = "reset") -> None:
        self.conversation_id = str(uuid.uuid4().hex)
        self.lifecycle_state = LIFECYCLE_IDLE
        self.interaction_mode = INTERACTION_NEW
        self.current_topic = None
        self.dialogue_state = None
        self.short_term_memory = None
        self.metadata = {
            "started_at": 0.0,
            "last_interaction_at": 0.0,
            "transition_reason": reason,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "lifecycle_state": self.lifecycle_state,
            "interaction_mode": self.interaction_mode,
            "current_topic": _debug_value(self.current_topic),
            "dialogue_state": _debug_value(self.dialogue_state),
            "short_term_memory": _debug_value(self.short_term_memory),
            "metadata": _debug_value(self.metadata),
        }


def _debug_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _debug_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_debug_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
