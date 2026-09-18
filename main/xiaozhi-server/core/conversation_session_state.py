from __future__ import annotations

import threading
import time

from core.conversation_context import (
    ConversationContext,
    LIFECYCLE_IDLE,
)
from core.utils.dialogue import Dialogue


class ConversationSessionState:
    """Shared conversation state container for one runtime session.

    This separates core dialogue/runtime state from transport concerns
    so websocket and text-debug entries can align on the same state shape.
    """

    def __init__(self):
        self.dialogue = Dialogue()
        self.sentence_id = None
        self.last_scene_output = None
        self.last_dialogue_state_result = None
        self.dialogue_state_runtime = None
        self.base_prompt = None
        self.robot_profile_prompt_patch = ""
        self.scene_prompt_patch = ""
        self.long_term_memory_prompt_patch = ""
        self.short_term_memory_prompt_patch = ""
        self.dialogue_state_prompt_patch = ""
        self.response_plan_prompt_patch = ""
        self.last_response_plan = None
        self.last_response_rewrite = None
        self.long_term_memory = None
        self.short_term_memory = None
        self.last_user_text = ""
        self.pending_daily_greeting = None
        self.last_applied_daily_greeting = None
        self.conversation_context = ConversationContext()
        self._sync_lifecycle_fields_from_context()
        self.last_conversation_request = None
        self.last_conversation_result = None

    def reset(self):
        self.dialogue = Dialogue()
        self.sentence_id = None
        self.last_scene_output = None
        self.last_dialogue_state_result = None
        self.dialogue_state_runtime = None
        self.base_prompt = None
        self.robot_profile_prompt_patch = ""
        self.scene_prompt_patch = ""
        self.long_term_memory_prompt_patch = ""
        self.short_term_memory_prompt_patch = ""
        self.dialogue_state_prompt_patch = ""
        self.response_plan_prompt_patch = ""
        self.last_response_plan = None
        self.last_response_rewrite = None
        self.long_term_memory = None
        self.short_term_memory = None
        self.last_user_text = ""
        self.pending_daily_greeting = None
        self.last_applied_daily_greeting = None
        self.conversation_context.reset("reset")
        self._sync_lifecycle_fields_from_context()
        self.last_conversation_request = None
        self.last_conversation_result = None

    def begin_interaction(self, timestamp: float, reason: str = "user_input") -> str:
        interaction_mode = self.conversation_context.start_interaction(
            timestamp,
            reason=reason,
        )
        self._sync_lifecycle_fields_from_context()
        return interaction_mode

    def mark_idle(self, reason: str = "idle") -> None:
        self.conversation_context.mark_idle(reason)
        self._sync_lifecycle_fields_from_context()

    def update_conversation_context(
        self,
        *,
        current_topic=None,
        dialogue_state=None,
        short_term_memory=None,
        last_interaction_at=None,
        metadata=None,
    ) -> None:
        self.conversation_context.update_after_turn(
            current_topic=current_topic,
            dialogue_state=dialogue_state,
            short_term_memory=short_term_memory,
            last_interaction_at=last_interaction_at,
            metadata=metadata,
        )
        self._sync_lifecycle_fields_from_context()

    def _sync_lifecycle_fields_from_context(self) -> None:
        self.conversation_lifecycle_state = self.conversation_context.lifecycle_state
        self.last_valid_interaction_at = self.conversation_context.last_interaction_at
        self.lifecycle_transition_reason = self.conversation_context.transition_reason


class ConversationSessionStateRegistry:
    """Thread-safe registry for shared conversation state objects."""

    def __init__(self):
        self._states: dict[str, tuple[ConversationSessionState, float]] = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str) -> ConversationSessionState:
        normalized_key = str(key or "").strip() or "default"
        now = time.time()
        with self._lock:
            state, _ = self._states.get(normalized_key, (None, 0.0))
            if state is None:
                state = ConversationSessionState()
            self._states[normalized_key] = (state, now)
            return state

    def reset(self, key: str) -> None:
        normalized_key = str(key or "").strip() or "default"
        with self._lock:
            self._states.pop(normalized_key, None)

    def clear_in_place(self, key: str) -> bool:
        normalized_key = str(key or "").strip() or "default"
        with self._lock:
            state, last_seen = self._states.get(normalized_key, (None, 0.0))
            if state is None:
                return False
            state.reset()
            self._states[normalized_key] = (state, last_seen or time.time())
            return True

    def cleanup_stale(self, ttl_seconds: int = 1800) -> None:
        cutoff = time.time() - ttl_seconds
        with self._lock:
            stale_keys = [
                key for key, (_, last_seen) in self._states.items()
                if last_seen < cutoff
            ]
            for key in stale_keys:
                self._states.pop(key, None)
