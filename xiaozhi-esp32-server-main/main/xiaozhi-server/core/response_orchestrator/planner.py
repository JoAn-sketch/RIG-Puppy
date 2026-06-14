from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List


@dataclass
class ResponsePlan:
    primary_action: str
    content_blocks: List[str] = field(default_factory=list)
    sentence_budget: int = 2
    concept_budget: int = 1
    ask_followup: bool = False
    allow_summary: bool = False
    stop_after_answer: bool = True
    style_tags: List[str] = field(default_factory=list)
    forbidden_patterns: List[str] = field(default_factory=list)
    interaction_protocol: str = "default"
    protocol_mode: str = "freeform"
    protocol_stage: str = "freeform"
    required_blocks: List[str] = field(default_factory=list)
    optional_blocks: List[str] = field(default_factory=list)
    allow_question: bool = True
    must_answer_before_question: bool = False
    question_position: str = "free"
    open_with_ack: bool = False
    pause_after_answer: bool = False

    def to_dict(self):
        return asdict(self)


def build_response_plan(scene_output, dialogue_state_result) -> ResponsePlan:
    control = getattr(dialogue_state_result, "control", None)
    state = getattr(dialogue_state_result, "state", {}) or {}
    if control is None:
        return ResponsePlan(
            primary_action="answer_only",
            content_blocks=["core_answer"],
            sentence_budget=2,
            concept_budget=1,
            ask_followup=False,
            allow_summary=False,
            stop_after_answer=True,
            style_tags=["brief", "child_friendly", "spoken"],
            forbidden_patterns=_default_forbidden_patterns(),
            required_blocks=["micro_answer"],
        )

    current_scene = getattr(control, "current_scene", "") or ""
    current_phase = getattr(control, "current_phase", "") or ""
    interaction_protocol = getattr(control, "interaction_protocol", "default") or "default"
    protocol_mode = getattr(control, "protocol_mode", "freeform") or "freeform"
    protocol_stage = getattr(control, "protocol_stage", "freeform") or "freeform"
    proactive_followup = _should_offer_proactive_followup(
        current_scene,
        current_phase,
        state,
    )
    primary_action = _resolve_primary_action(
        current_scene,
        current_phase,
        proactive_followup=proactive_followup,
    )
    sentence_budget = max(1, min(int(getattr(control, "max_reply_sentences", 2) or 2), 2))
    if current_scene == "safety_risk":
        sentence_budget = min(sentence_budget, 2)
    elif current_scene in {"system_repair", "relationship_building"}:
        sentence_budget = min(sentence_budget, 2)

    ask_followup = primary_action in {
        "ask_one_clarify",
        "offer_choice",
        "answer_then_invite",
    } and bool(
        getattr(control, "should_ask_followup", False) or proactive_followup
    )

    if interaction_protocol == "child_explore_v1":
        return _build_child_explore_plan(
            current_scene=current_scene,
            current_phase=current_phase,
            protocol_mode=protocol_mode,
            protocol_stage=protocol_stage,
            state=state,
        )

    return ResponsePlan(
        primary_action=primary_action,
        content_blocks=_resolve_content_blocks(primary_action),
        sentence_budget=sentence_budget,
        concept_budget=1,
        ask_followup=ask_followup,
        allow_summary=_allow_summary(primary_action, current_scene),
        stop_after_answer=primary_action not in {
            "ask_one_clarify",
            "offer_choice",
            "answer_then_invite",
        },
        style_tags=_resolve_style_tags(current_scene, primary_action),
        forbidden_patterns=_default_forbidden_patterns(primary_action),
        interaction_protocol=interaction_protocol,
        protocol_mode=protocol_mode,
        protocol_stage=protocol_stage,
        required_blocks=["core_answer"],
    )


def build_response_plan_prompt_patch(plan: ResponsePlan) -> str:
    lines = [
        "<response_plan>",
        f"action={plan.primary_action}",
        f"sentences={plan.sentence_budget}",
        f"concepts={plan.concept_budget}",
        f"ask_followup={str(plan.ask_followup).lower()}",
        f"summary={str(plan.allow_summary).lower()}",
        f"stop_after={str(plan.stop_after_answer).lower()}",
        f"style={','.join(plan.style_tags)}",
        f"avoid={','.join(plan.forbidden_patterns)}",
        f"protocol={plan.interaction_protocol}",
        f"mode={plan.protocol_mode}",
        f"stage={plan.protocol_stage}",
        f"allow_question={str(plan.allow_question).lower()}",
        f"answer_before_question={str(plan.must_answer_before_question).lower()}",
        f"required={','.join(plan.required_blocks)}",
        f"optional={','.join(plan.optional_blocks)}",
        "rule=本轮只完成一个主动作",
        "</response_plan>",
    ]
    return "\n".join(lines)


def _build_child_explore_plan(
    current_scene: str,
    current_phase: str,
    protocol_mode: str,
    protocol_stage: str,
    state,
) -> ResponsePlan:
    scene_state = (state or {}).get("scene_state", {})
    scene_turn_count = int(scene_state.get("scene_turn_count") or 0)
    first_scene_turn = scene_turn_count <= 1

    primary_action = "micro_answer_only"
    required_blocks = ["micro_answer"]
    optional_blocks: List[str] = []
    allow_question = False
    ask_followup = False
    sentence_budget = 2
    style_tags = ["child_friendly", "spoken", "brief", "explore_protocol"]
    forbidden_patterns = _default_forbidden_patterns()

    if protocol_stage == "ack_then_micro_answer":
        primary_action = "ack_and_micro_answer"
        required_blocks = ["ack", "micro_answer"]
        optional_blocks = ["pause"]
    elif protocol_stage == "invite_optional":
        primary_action = "micro_answer_then_invite"
        required_blocks = ["micro_answer"]
        optional_blocks = ["pause", "invite_optional"]
        allow_question = current_scene in {"curiosity", "learning_support", "play_interaction"}
        ask_followup = allow_question
    elif protocol_stage == "micro_answer":
        primary_action = "micro_answer_only"
        required_blocks = ["micro_answer"]
        optional_blocks = ["pause"]

    if current_scene == "learning_support":
        style_tags.append("coach_like")
        if current_phase in {"child_try", "next_step_or_close"}:
            primary_action = "micro_answer_then_invite"
            required_blocks = ["ack", "micro_answer"]
            optional_blocks = ["pause", "invite_optional"]
            allow_question = True
            ask_followup = True
    elif current_scene == "emotion_support":
        style_tags.append("gentle")
        allow_question = False if first_scene_turn else allow_question
    elif current_scene == "play_interaction":
        style_tags.append("playful")
        sentence_budget = 2

    return ResponsePlan(
        primary_action=primary_action,
        content_blocks=_resolve_content_blocks(primary_action),
        sentence_budget=sentence_budget,
        concept_budget=1,
        ask_followup=ask_followup,
        allow_summary=False,
        stop_after_answer=not allow_question,
        style_tags=style_tags,
        forbidden_patterns=forbidden_patterns,
        interaction_protocol="child_explore_v1",
        protocol_mode=protocol_mode,
        protocol_stage=protocol_stage,
        required_blocks=required_blocks,
        optional_blocks=optional_blocks,
        allow_question=allow_question and not first_scene_turn,
        must_answer_before_question=True,
        question_position="after_answer_only",
        open_with_ack="ack" in required_blocks,
        pause_after_answer=True,
    )


def _resolve_primary_action(
    current_scene: str,
    current_phase: str,
    proactive_followup: bool = False,
) -> str:
    if current_scene == "safety_risk":
        return "safe_direct"
    if current_scene == "emotion_support":
        if current_phase == "clarify_event":
            return "ask_one_clarify"
        if current_phase == "small_action":
            return "guide_one_step"
        return "emotion_validate"
    if current_scene == "curiosity":
        if current_phase == "short_answer":
            return "answer_then_invite" if proactive_followup else "answer_only"
        if current_phase == "analogy_or_example":
            return "answer_with_example"
        if current_phase == "check_understanding":
            return "ask_one_clarify"
        if current_phase == "optional_followup":
            return "answer_only"
        return "answer_only"
    if current_scene == "learning_support":
        if current_phase == "find_block":
            return "ask_one_clarify"
        if current_phase in {"split_step", "feedback", "next_step_or_close"}:
            return "guide_one_step"
        if current_phase == "child_try":
            return "ask_one_clarify"
        return "guide_one_step"
    if current_scene == "play_interaction":
        if current_phase == "branch_choice":
            return "offer_choice"
        return "play_one_turn"
    if current_scene == "system_repair":
        if current_phase == "offer_choice":
            return "offer_choice"
        return "repair_and_reset"
    if current_scene == "relationship_building":
        if current_phase == "light_followup":
            return "ask_one_clarify"
        if current_phase == "warm_opening" and proactive_followup:
            return "answer_then_invite"
        return "answer_only"
    return "answer_only"


def _resolve_content_blocks(primary_action: str) -> List[str]:
    return {
        "answer_only": ["core_answer"],
        "answer_then_invite": ["core_answer", "one_light_question"],
        "answer_with_example": ["core_answer", "one_example"],
        "ack_and_micro_answer": ["ack", "micro_answer"],
        "micro_answer_only": ["micro_answer"],
        "micro_answer_then_invite": ["micro_answer", "invite_optional"],
        "emotion_validate": ["emotion_ack"],
        "ask_one_clarify": ["one_question"],
        "guide_one_step": ["one_step"],
        "offer_choice": ["choice_prompt"],
        "safe_direct": ["safety_action"],
        "repair_and_reset": ["repair_ack"],
        "play_one_turn": ["play_turn"],
    }.get(primary_action, ["core_answer"])


def _allow_summary(primary_action: str, current_scene: str) -> bool:
    return primary_action == "safe_direct" and current_scene == "safety_risk"


def _resolve_style_tags(current_scene: str, primary_action: str) -> List[str]:
    tags = ["child_friendly", "spoken", "brief"]
    if current_scene == "emotion_support":
        tags.append("gentle")
    if current_scene == "play_interaction":
        tags.append("playful")
    if primary_action in {"safe_direct", "repair_and_reset"}:
        tags.append("clear")
    return tags


def _default_forbidden_patterns(primary_action: str | None = None) -> List[str]:
    patterns = [
        "adult_summary",
        "teacher_checking",
        "encyclopedia_explaining",
        "multi_question",
        "multi_concept",
        "leading_question",
    ]
    if primary_action not in {"ask_one_clarify", "offer_choice"}:
        patterns.append("extra_followup")
    return patterns


def _should_offer_proactive_followup(
    current_scene: str,
    current_phase: str,
    state,
) -> bool:
    scene_state = (state or {}).get("scene_state", {})
    scene_turn_count = int(scene_state.get("scene_turn_count") or 0)
    if current_scene == "curiosity" and current_phase == "short_answer":
        return scene_turn_count <= 1
    if current_scene == "relationship_building" and current_phase == "warm_opening":
        return scene_turn_count <= 1
    return False
