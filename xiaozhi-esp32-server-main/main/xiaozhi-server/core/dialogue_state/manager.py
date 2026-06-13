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
    FOLLOWUP_CLARIFY_MARKERS,
    GREETING_MARKERS,
    MAX_SENTENCES_BY_SCENE,
    PHASE_POLICY_HINTS,
    REPAIR_MARKERS,
    REPLY_STYLE_BY_SCENE,
    TOPIC_SWITCH_MARKERS,
    contains_any,
    extract_time_greeting_slot,
    get_recommended_greeting,
    get_time_slot_label,
    normalize_text,
    reply_length_bucket,
    resolve_time_slot_from_timestamp,
    time_greeting_matches_current_slot,
)
from .schema import (
    DialogueControlOutput,
    DialogueDebugOutput,
    DialogueStateManagerInput,
    DialogueStateManagerResult,
)
from core.response_orchestrator.planner import build_response_plan


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
    social_state = state.get("social_state", {})
    turn_contract = control.turn_contract or {}
    phase_hints = PHASE_POLICY_HINTS.get(
        (control.current_scene, control.current_phase),
        ["一轮只推进一件事，尽量短句、具体、儿童可懂。"],
    )
    dialogue_state_lines = [
        "<dialogue_state>",
        f"scene={control.current_scene}",
        f"subscene={control.current_subscene}",
        f"phase={control.current_phase}",
        f"scene_turn={state['scene_state']['scene_turn_count']}",
        f"phase_turn={state['phase_state']['phase_turn_count']}",
        f"next={control.next_action}",
        f"style={control.reply_style}",
        f"max_sentences={turn_contract.get('sentence_budget', control.max_reply_sentences)}",
        f"concepts={turn_contract.get('concept_budget', 1)}",
        f"ask_followup={str(bool(turn_contract.get('ask_followup', False))).lower()}",
        f"allow_summary={str(bool(turn_contract.get('allow_summary', False))).lower()}",
        f"close={str(control.should_close_scene).lower()}",
        f"time_slot={social_state.get('current_time_slot') or 'unknown'}",
        f"greeting_conflict={str(bool(social_state.get('greeting_conflict_with_time'))).lower()}",
        "</dialogue_state>",
        "<phase_policy>",
        f"action={turn_contract.get('primary_action', 'answer_only')}",
        f"hint={phase_hints[0]}",
    ]
    if turn_contract.get("ask_followup"):
        dialogue_state_lines.append("followup=只问一个轻量问题")
    else:
        dialogue_state_lines.append("followup=不额外连续追问")
    if not turn_contract.get("allow_summary", False):
        dialogue_state_lines.append("summary=不要总结")
    dialogue_state_lines.append("rule=不要同时解释、总结、追问")
    if social_state.get("greeting_conflict_with_previous"):
        dialogue_state_lines.append("greeting=同一轮寒暄修正,不要重新完整开场")
    if social_state.get("greeting_conflict_with_time"):
        expected_label = social_state.get("current_time_label") or "当前时段"
        recommended = social_state.get("recommended_greeting") or "你好"
        dialogue_state_lines.append(
            f"greeting=当前更接近{expected_label},可说{recommended},轻轻纠偏"
        )
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
        self._update_greeting_context(state, manager_input.text, timestamp_ms)

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
        response_plan = build_response_plan(scene_output, type("ResultView", (), {"control": control})())
        control.turn_contract = response_plan.to_dict()
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
            "social_state": {
                "is_greeting_turn": False,
                "last_turn_was_greeting": False,
                "last_greeting_slot": None,
                "last_greeting_text": None,
                "greeting_turn_streak": 0,
                "current_time_slot": None,
                "current_time_label": None,
                "greeting_conflict_with_time": False,
                "greeting_conflict_with_previous": False,
                "recommended_greeting": None,
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
            if self._is_context_followup_clarification(text):
                notes.append("context_followup")
                if previous_phase in {None, "short_answer"}:
                    return "short_answer", "give_short_answer", False, "C2F", "phase_repeat", notes
                if previous_phase in {"analogy_or_example", "check_understanding", "optional_followup"}:
                    state["turn_state"]["followup_count"] += 1
                    return "optional_followup", "answer_followup_once", previous_phase != "optional_followup", "C5F", "phase_advance", notes
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
            if self._is_context_followup_clarification(text):
                notes.append("context_followup")
                if previous_phase in {"find_block", "split_step", None}:
                    return "split_step", "give_one_step_hint", previous_phase != "split_step", "L2F", "phase_repeat" if previous_phase == "split_step" else "phase_advance", notes
                if previous_phase in {"child_try", "feedback", "next_step_or_close"}:
                    return "split_step", "give_one_step_hint", True, "L2F", "phase_adjust", notes
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
            social_state = state.get("social_state", {})
            if social_state.get("greeting_conflict_with_previous"):
                notes.append("greeting_revision")
                return "light_followup", "acknowledge_greeting_revision", previous_phase != "light_followup", "B2T", "greeting_revision", notes
            if social_state.get("greeting_conflict_with_time"):
                notes.append("time_grounded_greeting")
                return "warm_opening", "soft_correct_greeting", previous_phase != "warm_opening", "B1T", "time_grounded_greeting", notes
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
        if contains_any(text, GREETING_MARKERS):
            return "social_opening"
        if contains_any(text, REPAIR_MARKERS):
            return "repair_request"
        if contains_any(text, ADVICE_MARKERS):
            return "ask_help"
        if self._is_context_followup_clarification(text):
            return "ask_followup"
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

    def _is_context_followup_clarification(self, text: str) -> bool:
        normalized = normalize_text(text)
        if not normalized or len(normalized) > 18:
            return False
        if contains_any(text, REPAIR_MARKERS) or contains_any(text, TOPIC_SWITCH_MARKERS):
            return False
        if contains_any(text, FOLLOWUP_CLARIFY_MARKERS):
            return True
        if any(normalized.startswith(prefix) for prefix in ("那", "这个", "这", "它")):
            return any(marker in normalized for marker in ("什么", "怎么", "为什么", "哪", "哪里", "是不是", "能不能"))
        return False

    def _update_greeting_context(
        self,
        state: Dict[str, Any],
        text: str,
        timestamp_ms: int,
    ) -> None:
        social_state = state.setdefault("social_state", {})
        previous_greeting_slot = social_state.get("last_greeting_slot")
        previous_turn_was_greeting = bool(social_state.get("last_turn_was_greeting"))
        previous_streak = int(social_state.get("greeting_turn_streak") or 0)

        current_time_slot = resolve_time_slot_from_timestamp(timestamp_ms)
        greeting_slot = extract_time_greeting_slot(text)
        is_greeting_turn = contains_any(text, GREETING_MARKERS)
        conflict_with_time = is_greeting_turn and not time_greeting_matches_current_slot(
            greeting_slot, current_time_slot
        )
        conflict_with_previous = (
            is_greeting_turn
            and previous_turn_was_greeting
            and bool(greeting_slot)
            and bool(previous_greeting_slot)
            and greeting_slot != previous_greeting_slot
        )

        social_state["is_greeting_turn"] = is_greeting_turn
        social_state["current_time_slot"] = current_time_slot
        social_state["current_time_label"] = get_time_slot_label(current_time_slot)
        social_state["greeting_conflict_with_time"] = conflict_with_time
        social_state["greeting_conflict_with_previous"] = conflict_with_previous
        social_state["recommended_greeting"] = get_recommended_greeting(current_time_slot)

        if is_greeting_turn:
            social_state["greeting_turn_streak"] = previous_streak + 1 if previous_turn_was_greeting else 1
            social_state["last_turn_was_greeting"] = True
            social_state["last_greeting_slot"] = greeting_slot
            social_state["last_greeting_text"] = text
            return

        social_state["greeting_turn_streak"] = 0
        social_state["last_turn_was_greeting"] = False
