from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Tuple

from .rules import (
    ADVICE_MARKERS,
    ATTEMPT_MARKERS,
    CHOICE_MARKERS,
    CLOSE_MARKERS,
    DEFAULT_PHASES,
    EMOTION_CAUSE_MARKERS,
    GREETING_MARKERS,
    MAX_SENTENCES_BY_SCENE,
    PHASE_POLICY_HINTS,
    REPAIR_MARKERS,
    REPLY_STYLE_BY_SCENE,
    TOPIC_SWITCH_MARKERS,
    contains_any,
    normalize_text,
    reply_length_bucket,
)
from .schema import (
    DialogueControlOutput,
    DialogueDebugOutput,
    DialogueStateManagerInput,
    DialogueStateManagerResult,
)


RUNTIME_SECTION_TAGS = (
    "scene_router",
    "scene_policy",
    "dialogue_state",
    "phase_policy",
)


def strip_runtime_prompt_sections(prompt: str) -> str:
    cleaned = prompt or ""
    for tag in RUNTIME_SECTION_TAGS:
        start_token = f"<{tag}>"
        end_token = f"</{tag}>"
        while start_token in cleaned and end_token in cleaned:
            start_index = cleaned.index(start_token)
            end_index = cleaned.index(end_token) + len(end_token)
            prefix = cleaned[:start_index].rstrip()
            suffix = cleaned[end_index:].lstrip("\n")
            cleaned = prefix if not suffix else f"{prefix}\n{suffix}"
    return cleaned.strip()


def build_dialogue_state_prompt_patch(result: DialogueStateManagerResult) -> str:
    state = result.state
    control = result.control
    dialogue_state_lines = [
        "<dialogue_state>",
        f"current_scene={control.current_scene}",
        f"current_subscene={control.current_subscene}",
        f"current_phase={control.current_phase}",
        f"scene_turn_count={state['scene_state']['scene_turn_count']}",
        f"phase_turn_count={state['phase_state']['phase_turn_count']}",
        f"followup_count={state['turn_state']['followup_count']}",
        f"next_action={control.next_action}",
        f"reply_style={control.reply_style}",
        f"max_reply_sentences={control.max_reply_sentences}",
        f"should_close_scene={str(control.should_close_scene).lower()}",
        "</dialogue_state>",
        "<phase_policy>",
        f"当前 phase 是 {control.current_phase}，本轮 next_action 是 {control.next_action}。",
        f"回复风格使用 {control.reply_style}，最多 {control.max_reply_sentences} 句。",
    ]
    phase_hints = PHASE_POLICY_HINTS.get(
        (control.current_scene, control.current_phase),
        ["一轮只推进一件事，尽量短句、具体、儿童可懂。"],
    )
    dialogue_state_lines.extend(phase_hints)
    if control.should_ask_followup:
        dialogue_state_lines.append("如果要追问，只问一个轻量问题。")
    else:
        dialogue_state_lines.append("本轮优先直接推进，不额外连续追问。")
    dialogue_state_lines.append("</phase_policy>")
    return "\n".join(dialogue_state_lines)


class DialogueStateManager:
    def update(self, manager_input: DialogueStateManagerInput) -> DialogueStateManagerResult:
        timestamp_ms = manager_input.timestamp_ms or int(time.time() * 1000)
        scene_output = manager_input.scene_router_output
        state = self._build_initial_state(manager_input.dialogue_state, timestamp_ms)
        previous_scene = state["scene_state"]["current_scene"]
        previous_phase = state["phase_state"]["current_phase"]
        current_scene = scene_output.primary_scene
        current_subscene = scene_output.subscene
        scene_changed = current_scene != previous_scene
        phase_changed = False
        matched_rule = "G4" if scene_changed else "G3"
        transition_reason = "scene_switch" if scene_changed else "scene_continue"
        notes: List[str] = []

        state["scene_state"]["previous_scene"] = previous_scene
        state["scene_state"]["current_scene"] = current_scene
        state["scene_state"]["current_subscene"] = current_subscene
        state["scene_state"]["scene_changed"] = scene_changed
        state["scene_state"]["scene_turn_count"] = (
            1 if scene_changed else state["scene_state"]["scene_turn_count"] + 1
        )

        state["turn_state"]["turn_index"] += 1
        state["turn_state"]["last_user_move"] = self._detect_user_move(
            current_scene, manager_input.text
        )
        if scene_changed:
            state["turn_state"]["followup_count"] = 0
            if current_scene == "system_repair":
                state["turn_state"]["repair_count"] += 1
            else:
                state["turn_state"]["repair_count"] = 0

        state["user_state"]["emotion_state"] = scene_output.emotion_state
        state["user_state"]["frustration_level"] = manager_input.signals.frustration_signal
        state["meta"]["updated_at_ms"] = timestamp_ms

        if current_scene == "safety_risk":
            current_phase = DEFAULT_PHASES["safety_risk"]
            next_action = "direct_safe_response"
            matched_rule = "G1"
            transition_reason = "safety_override"
            phase_changed = current_phase != previous_phase
            state["task_state"]["task_type"] = "safety"
        else:
            current_phase, next_action, phase_changed, matched_rule, transition_reason, notes = self._resolve_scene_phase(
                state=state,
                manager_input=manager_input,
                scene_changed=scene_changed,
                previous_phase=previous_phase,
            )

        state["phase_state"]["current_phase"] = current_phase
        state["phase_state"]["phase_changed"] = phase_changed
        state["phase_state"]["phase_turn_count"] = (
            1 if scene_changed or phase_changed else state["phase_state"]["phase_turn_count"] + 1
        )
        state["phase_state"]["next_action"] = next_action
        state["task_state"]["task_type"] = self._resolve_task_type(current_scene)
        state["task_state"]["task_completed"] = self._should_mark_task_complete(
            manager_input.text, current_scene, current_phase, state
        )
        state["phase_state"]["should_close_scene"] = (
            current_phase == "close" or state["task_state"]["task_completed"]
        )
        state["meta"]["last_manager_result"] = transition_reason
        state["meta"]["last_transition_reason"] = transition_reason

        control = DialogueControlOutput(
            current_scene=current_scene,
            current_subscene=current_subscene,
            current_phase=current_phase,
            next_action=next_action,
            reply_style=REPLY_STYLE_BY_SCENE.get(current_scene, "warm_brief"),
            max_reply_sentences=MAX_SENTENCES_BY_SCENE.get(current_scene, 3),
            should_ask_followup=current_phase in {
                "check_understanding",
                "child_try",
                "offer_choice",
                "branch_choice",
                "light_followup",
            },
            should_close_scene=state["phase_state"]["should_close_scene"],
            should_switch_scene=scene_changed,
            should_use_memory=scene_output.should_use_memory,
            should_use_rag=scene_output.should_use_rag,
            should_force_safe_template=scene_output.should_force_safe_template,
        )
        debug = DialogueDebugOutput(
            transition_reason=transition_reason,
            scene_changed=scene_changed,
            phase_changed=phase_changed,
            matched_rule=matched_rule,
            router_confidence=scene_output.confidence,
            notes=notes,
        )
        return DialogueStateManagerResult(state=state, control=control, debug=debug)

    def post_reply_update(
        self,
        runtime_state: Dict[str, Any] | None,
        reply_text: str,
        next_action: str | None = None,
    ) -> Dict[str, Any] | None:
        if not runtime_state:
            return runtime_state
        updated_state = copy.deepcopy(runtime_state)
        updated_state["turn_state"]["last_bot_action"] = next_action or updated_state["phase_state"].get("next_action")
        updated_state["turn_state"]["last_reply_length_bucket"] = reply_length_bucket(reply_text)
        if updated_state["phase_state"].get("current_phase") == "close":
            updated_state["task_state"]["task_completed"] = True
        updated_state["meta"]["updated_at_ms"] = int(time.time() * 1000)
        updated_state["meta"]["state_source"] = "post_reply"
        return updated_state

    def _build_initial_state(self, existing_state: Dict[str, Any] | None, timestamp_ms: int) -> Dict[str, Any]:
        if existing_state:
            return copy.deepcopy(existing_state)
        return {
            "scene_state": {
                "current_scene": None,
                "current_subscene": None,
                "previous_scene": None,
                "scene_turn_count": 0,
                "scene_changed": False,
            },
            "phase_state": {
                "current_phase": None,
                "phase_turn_count": 0,
                "phase_changed": False,
                "next_action": None,
                "should_close_scene": False,
            },
            "turn_state": {
                "turn_index": 0,
                "followup_count": 0,
                "repair_count": 0,
                "last_bot_action": None,
                "last_reply_length_bucket": None,
                "last_user_move": "unknown",
            },
            "user_state": {
                "emotion_state": "neutral",
                "understanding_state": "unknown",
                "frustration_level": 0,
            },
            "task_state": {
                "task_type": "unknown",
                "task_completed": False,
                "completion_signal": None,
            },
            "meta": {
                "version": "v1",
                "updated_at_ms": timestamp_ms,
                "state_source": "runtime",
                "last_manager_result": "init",
                "last_transition_reason": "init",
            },
        }

    def _resolve_scene_phase(
        self,
        state: Dict[str, Any],
        manager_input: DialogueStateManagerInput,
        scene_changed: bool,
        previous_phase: str | None,
    ) -> Tuple[str, str, bool, str, str, List[str]]:
        current_scene = state["scene_state"]["current_scene"]
        text = manager_input.text or ""
        normalized = normalize_text(text)
        notes: List[str] = []

        if contains_any(text, TOPIC_SWITCH_MARKERS):
            notes.append("manual_topic_switch")

        if current_scene == "emotion_support":
            if scene_changed:
                return "empathize", "validate_feeling", True, "E1", "scene_switch", notes
            if contains_any(text, ADVICE_MARKERS):
                return "small_action", "suggest_one_small_step", previous_phase != "small_action", "E4", "phase_advance", notes
            if previous_phase == "empathize" and (
                state["scene_state"]["scene_turn_count"] > 1 or contains_any(text, EMOTION_CAUSE_MARKERS)
            ):
                return "clarify_event", "ask_gentle_clarify", True, "E2", "phase_advance", notes
            if previous_phase == "clarify_event":
                return "normalize_feeling", "normalize_and_support", True, "E3", "phase_advance", notes
            if previous_phase == "small_action" and contains_any(text, CLOSE_MARKERS):
                return "close", "close_current_scene", True, "E5", "close_scene", notes
            return previous_phase or "empathize", "validate_feeling", False, "E1", "phase_repeat", notes

        if current_scene == "curiosity":
            if scene_changed:
                return "short_answer", "give_short_answer", True, "C2", "scene_switch", notes
            if contains_any(text, CLOSE_MARKERS):
                return "close", "close_current_scene", previous_phase != "close", "C6", "close_scene", notes
            if previous_phase == "short_answer":
                return "analogy_or_example", "give_example_then_check", True, "C3", "phase_advance", notes
            if previous_phase == "analogy_or_example":
                return "check_understanding", "check_understanding", True, "C4", "phase_advance", notes
            if previous_phase == "check_understanding" and state["turn_state"]["followup_count"] < 1:
                state["turn_state"]["followup_count"] += 1
                return "optional_followup", "answer_followup_once", True, "C5", "phase_advance", notes
            if previous_phase == "optional_followup":
                return "close", "close_current_scene", True, "C6", "close_scene", notes
            return previous_phase or "short_answer", "give_short_answer", False, "C2", "phase_repeat", notes

        if current_scene == "learning_support":
            if scene_changed:
                return "find_block", "find_where_child_stuck", True, "L1", "scene_switch", notes
            if previous_phase == "find_block":
                return "split_step", "give_one_step_hint", True, "L2", "phase_advance", notes
            if previous_phase == "split_step":
                return "child_try", "invite_child_try", True, "L3", "phase_advance", notes
            if previous_phase == "child_try" and (
                contains_any(text, ATTEMPT_MARKERS) or bool(normalized)
            ):
                return "feedback", "give_feedback", True, "L4", "phase_advance", notes
            if previous_phase == "feedback":
                return "next_step_or_close", "advance_or_close", True, "L5", "phase_advance", notes
            if previous_phase == "next_step_or_close" and contains_any(text, CLOSE_MARKERS):
                return "close", "close_current_scene", True, "L5", "close_scene", notes
            return previous_phase or "find_block", "find_where_child_stuck", False, "L1", "phase_repeat", notes

        if current_scene == "play_interaction":
            if scene_changed:
                return "open_round", "start_game_quickly", True, "P1", "scene_switch", notes
            if contains_any(text, CLOSE_MARKERS):
                return "close", "close_current_scene", previous_phase != "close", "P5", "close_scene", notes
            if contains_any(text, CHOICE_MARKERS):
                return "branch_choice", "offer_choice", previous_phase != "branch_choice", "P3", "phase_advance", notes
            if previous_phase in {"open_round", "branch_choice"}:
                return "play_round", "continue_play_turn", True, "P2", "phase_advance", notes
            return previous_phase or "play_round", "continue_play_turn", False, "P2", "phase_repeat", notes

        if current_scene == "system_repair":
            if scene_changed:
                return "recognize_mismatch", "acknowledge_mismatch", True, "R1", "scene_switch", notes
            if previous_phase == "recognize_mismatch":
                return "offer_choice", "offer_repair_choice", True, "R2", "phase_advance", notes
            if previous_phase == "offer_choice":
                return "re_anchor_topic", "re_anchor_and_switch", True, "R3", "phase_advance", notes
            if previous_phase == "re_anchor_topic":
                return "close", "close_current_scene", True, "R4", "close_scene", notes
            if state["turn_state"]["repair_count"] >= 2:
                notes.append("repair_timeout")
            return previous_phase or "recognize_mismatch", "acknowledge_mismatch", False, "R1", "phase_repeat", notes

        if current_scene == "relationship_building":
            if scene_changed:
                return "warm_opening", "greet_warmly", True, "B1", "scene_switch", notes
            if contains_any(text, GREETING_MARKERS) or len(normalized) <= 8:
                return "light_followup", "invite_more", previous_phase != "light_followup", "B2", "phase_advance", notes
            return previous_phase or "warm_opening", "greet_warmly", False, "B1", "phase_repeat", notes

        default_phase = DEFAULT_PHASES.get(current_scene, "warm_opening")
        default_action = {
            "warm_opening": "greet_warmly",
            "acknowledge": "acknowledge_question",
            "find_block": "find_where_child_stuck",
        }.get(default_phase, "greet_warmly")
        return default_phase, default_action, scene_changed, "G4" if scene_changed else "G3", "scene_switch" if scene_changed else "scene_continue", notes

    def _resolve_task_type(self, current_scene: str) -> str:
        return {
            "safety_risk": "safety",
            "emotion_support": "emotion_regulation",
            "curiosity": "explain_question",
            "learning_support": "guided_learning",
            "play_interaction": "play_round",
            "system_repair": "repair_alignment",
            "relationship_building": "warm_opening",
        }.get(current_scene, "unknown")

    def _should_mark_task_complete(
        self,
        text: str,
        current_scene: str,
        current_phase: str,
        state: Dict[str, Any],
    ) -> bool:
        if current_phase == "close":
            return True
        if contains_any(text, CLOSE_MARKERS):
            state["task_state"]["completion_signal"] = "user_close_signal"
            return True
        if current_scene == "system_repair" and current_phase == "re_anchor_topic":
            return False
        return bool(state["task_state"].get("task_completed"))

    def _detect_user_move(self, current_scene: str, text: str) -> str:
        if contains_any(text, REPAIR_MARKERS):
            return "repair_request"
        if contains_any(text, ADVICE_MARKERS):
            return "ask_help"
        if current_scene == "curiosity":
            return "ask_why"
        if current_scene == "learning_support":
            return "solve_problem"
        if current_scene == "play_interaction":
            return "play_turn"
        if current_scene == "emotion_support":
            return "emotion_disclosure"
        if current_scene == "relationship_building":
            return "social_opening"
        return "unknown"
