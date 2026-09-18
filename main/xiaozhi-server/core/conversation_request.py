from dataclasses import dataclass, field
from typing import Any, Dict, Optional

INTERACTION_NEW = "NEW_INTERACTION"
INTERACTION_CONTINUATION = "CONTINUATION"
LIFECYCLE_IDLE = "IDLE"
LIFECYCLE_LISTENING = "LISTENING"


@dataclass
class ConversationRequest:
    """Prepared conversation turn passed from orchestration to execution."""

    user_input: str
    speaker: Optional[str] = None
    language: Optional[str] = None
    lifecycle_state: str = "IDLE"
    interaction_mode: str = "NEW_INTERACTION"
    conversation_state: Dict[str, Any] = field(default_factory=dict)
    scene: Any = None
    dialogue_state: Any = None
    memory_context: Any = None
    response_plan: Any = None
    intent: Dict[str, Any] = field(default_factory=dict)
    policy_context: Dict[str, Any] = field(default_factory=dict)

    @property
    def memory_text(self):
        return getattr(self.memory_context, "text", None) if self.memory_context else None

    @property
    def intent_type(self):
        return str(self.intent.get("type") or "conversation")


@dataclass
class MemoryContext:
    policy: str = "NONE"
    query: str = ""
    text: Optional[str] = None


def should_query_memory(query: str) -> bool:
    return bool(str(query or "").strip())


def enrich_response_plan(response_plan, lifecycle_state, interaction_mode):
    if response_plan is not None:
        response_plan.lifecycle_state = lifecycle_state
        response_plan.interaction_mode = interaction_mode
    return response_plan
