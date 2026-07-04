from __future__ import annotations

import threading
import time

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

    def reset(self):
        self.dialogue = Dialogue()
        self.sentence_id = None
        self.last_scene_output = None
        self.last_dialogue_state_result = None
        self.dialogue_state_runtime = None
        self.base_prompt = None
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
