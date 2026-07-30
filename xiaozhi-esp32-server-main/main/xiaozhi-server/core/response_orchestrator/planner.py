from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from core.runtime_generation_config import (
    get_age_profile,
    get_interest_generation_context,
    get_interaction_policy,
)
from core.conversation_openness import proactive_mode


@dataclass
class ResponsePlan:
    primary_action: str
    current_scene: str = ""
    age_group: str = "6-8"
    conversation_openness_level: int = 3
    conversation_openness_mode: str = "limited"
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
    max_non_question_units: int = 0
    first_turn_info_points: int = 1
    proper_noun_budget: int = 0
    common_term_budget: int = 0
    is_first_scene_turn: bool = False
    optimizer_mode: str = "optimize"
    preserve_companion_hook: bool = True
    functional_block_budget: int = 4
    information_budget: str = "medium"
    reasoning_depth: int = 2
    interaction_style: str = "exploration"
    conversation_pacing: str = "balanced"
    emotional_priority: str = "medium"
    vocabulary_level: str = "simple"
    abstract_concept_level: str = "limited"
    support_level: str = "medium_high"
    question_style: str = "exploration"
    max_examples: int = 1
    max_analogies: int = 1
    max_interaction_hooks: int = 1
    must_answer_all_questions: bool = True
    stop_expanding_after_answer: bool = True
    interest_topics: List[str] = field(default_factory=list)
    interest_contexts: Dict[str, List[str]] = field(default_factory=dict)
    interest_influence: Dict[str, str] = field(default_factory=dict)
    scene_interest_config: Dict[str, bool] = field(default_factory=dict)
    topic_state: Dict[str, Any] = field(default_factory=dict)
    topic_decision: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


DEFAULT_SCENE_AGE_RULE = {
    "sentence_budget": 3,
    "concept_budget": 1,
    "allow_summary": False,
    "followup_mode": "none",
    "max_non_question_units": 2,
    "optimizer_mode": "optimize",
    "functional_block_budget": 3,
    "preserve_companion_hook": True,
    "response_pattern": "core_answer",
    "trim_priority": ["direct_answer"],
}

AGE_INFORMATION_LIMITS: Dict[str, Dict[str, Any]] = {
    "3-5": {
        "first_turn_info_points": 1,
        "proper_noun_budget": 0,
        "common_term_budget": 0,
        "first_turn_density_rule": "首轮只给1个信息点，只说最直接的结论，不引入专有名词。",
        "term_policy": "只用生活化词，不用学科名、分类名、年代名。",
    },
    "6-8": {
        "first_turn_info_points": 1,
        "proper_noun_budget": 0,
        "common_term_budget": 1,
        "first_turn_density_rule": "首轮仍只给1个信息点，可以带1个常见分类词，但不要堆新概念。",
        "term_policy": "尽量不用专有名词；必要时最多带1个常见类别词。",
    },
    "9-11": {
        "first_turn_info_points": 2,
        "proper_noun_budget": 1,
        "common_term_budget": 1,
        "first_turn_density_rule": "首轮可以给1个主结论 + 1个区别/原因，可以开始出现1个专有名词。",
        "term_policy": "允许1个专有名词，但同轮不要再叠第二个新术语。",
    },
}


SCENE_AGE_REWRITE_RULES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "curiosity": {
        "3-5": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 1,
            "optimizer_mode": "optimize",
            "functional_block_budget": 3,
            "response_pattern": "ack + direct_answer",
            "trim_priority": ["direct_answer", "ack", "example_or_analogy"],
        },
        "6-8": {
            "sentence_budget": 3,
            "concept_budget": 1,
            "followup_mode": "optional",
            "max_non_question_units": 2,
            "optimizer_mode": "optimize",
            "functional_block_budget": 4,
            "response_pattern": "ack + direct_answer + light_example",
            "trim_priority": ["direct_answer", "example_or_analogy", "ack", "followup"],
        },
        "9-11": {
            "sentence_budget": 4,
            "concept_budget": 2,
            "followup_mode": "optional",
            "max_non_question_units": 3,
            "optimizer_mode": "optimize",
            "functional_block_budget": 4,
            "response_pattern": "ack + direct_answer + distinction_or_reason",
            "trim_priority": ["direct_answer", "distinction", "cause_or_reason", "ack", "followup"],
        },
    },
    "learning_support": {
        "3-5": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 1,
            "response_pattern": "ack + one_step",
            "trim_priority": ["action_step", "ack"],
        },
        "6-8": {
            "sentence_budget": 3,
            "concept_budget": 1,
            "followup_mode": "optional",
            "max_non_question_units": 2,
            "response_pattern": "ack + one_step + light_check",
            "trim_priority": ["action_step", "direct_answer", "ack", "followup"],
        },
        "9-11": {
            "sentence_budget": 4,
            "concept_budget": 2,
            "followup_mode": "optional",
            "max_non_question_units": 3,
            "response_pattern": "ack + one_step + reason_or_common_mistake",
            "trim_priority": ["action_step", "cause_or_reason", "direct_answer", "followup"],
        },
    },
    "emotion_support": {
        "3-5": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 1,
            "response_pattern": "emotion_validate",
            "trim_priority": ["emotion_validate", "action_step"],
        },
        "6-8": {
            "sentence_budget": 3,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 2,
            "response_pattern": "emotion_validate + one_small_action",
            "trim_priority": ["emotion_validate", "action_step", "ack"],
        },
        "9-11": {
            "sentence_budget": 4,
            "concept_budget": 2,
            "followup_mode": "light",
            "max_non_question_units": 2,
            "response_pattern": "emotion_validate + cause_hint + one_small_action",
            "trim_priority": ["emotion_validate", "cause_or_reason", "action_step"],
        },
    },
    "play_interaction": {
        "3-5": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 1,
            "response_pattern": "play_turn",
            "trim_priority": ["play_turn", "choice_prompt"],
        },
        "6-8": {
            "sentence_budget": 3,
            "concept_budget": 1,
            "followup_mode": "optional",
            "max_non_question_units": 2,
            "response_pattern": "play_turn + one_choice",
            "trim_priority": ["play_turn", "choice_prompt", "followup"],
        },
        "9-11": {
            "sentence_budget": 4,
            "concept_budget": 2,
            "followup_mode": "optional",
            "max_non_question_units": 3,
            "response_pattern": "play_turn + one_choice + result_hint",
            "trim_priority": ["play_turn", "choice_prompt", "direct_answer", "followup"],
        },
    },
    "safety_risk": {
        "3-5": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 1,
            "response_pattern": "safety_action",
            "trim_priority": ["safety_action", "action_step"],
        },
        "6-8": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 2,
            "response_pattern": "safety_action + next_step",
            "trim_priority": ["safety_action", "action_step", "cause_or_reason"],
        },
        "9-11": {
            "sentence_budget": 3,
            "concept_budget": 2,
            "followup_mode": "none",
            "max_non_question_units": 2,
            "response_pattern": "safety_action + reason_or_next_step",
            "trim_priority": ["safety_action", "cause_or_reason", "action_step"],
        },
    },
    "system_repair": {
        "3-5": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 1,
            "response_pattern": "repair_ack",
            "trim_priority": ["repair_ack", "action_step"],
        },
        "6-8": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 2,
            "response_pattern": "repair_ack + retry_step",
            "trim_priority": ["repair_ack", "action_step", "cause_or_reason"],
        },
        "9-11": {
            "sentence_budget": 3,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 2,
            "response_pattern": "repair_ack + brief_reason + retry_step",
            "trim_priority": ["repair_ack", "action_step", "cause_or_reason"],
        },
    },
    "relationship_building": {
        "3-5": {
            "sentence_budget": 2,
            "concept_budget": 1,
            "followup_mode": "none",
            "max_non_question_units": 1,
            "response_pattern": "warm_ack",
            "trim_priority": ["ack", "direct_answer"],
        },
        "6-8": {
            "sentence_budget": 3,
            "concept_budget": 1,
            "followup_mode": "optional",
            "max_non_question_units": 2,
            "response_pattern": "warm_ack + light_followup",
            "trim_priority": ["ack", "direct_answer", "followup"],
        },
        "9-11": {
            "sentence_budget": 4,
            "concept_budget": 2,
            "followup_mode": "optional",
            "max_non_question_units": 3,
            "response_pattern": "warm_ack + reciprocal_note + light_followup",
            "trim_priority": ["ack", "direct_answer", "followup"],
        },
    },
}


def resolve_scene_age_rule(current_scene: str, age_group: str) -> Dict[str, Any]:
    scene_rules = SCENE_AGE_REWRITE_RULES.get(current_scene, {})
    resolved = dict(DEFAULT_SCENE_AGE_RULE)
    resolved.update(AGE_INFORMATION_LIMITS.get(age_group, {}))
    resolved.update(scene_rules.get(age_group, {}))
    resolved["scene"] = current_scene
    resolved["age_group"] = age_group
    return resolved


def export_scene_age_rewrite_matrix() -> List[Dict[str, Any]]:
    rows = []
    for scene_name in sorted(SCENE_AGE_REWRITE_RULES.keys()):
        age_rules = SCENE_AGE_REWRITE_RULES[scene_name]
        for age_group in ("3-5", "6-8", "9-11"):
            rule = resolve_scene_age_rule(scene_name, age_group)
            rows.append(
                {
                    "scene_name": scene_name,
                    "age_group": age_group,
                    "sentence_budget": rule["sentence_budget"],
                    "concept_budget": rule["concept_budget"],
                    "allow_summary": bool(rule["allow_summary"]),
                    "followup_mode": rule["followup_mode"],
                    "max_non_question_units": rule["max_non_question_units"],
                    "response_pattern": rule["response_pattern"],
                    "trim_priority": list(rule["trim_priority"]),
                    "first_turn_info_points": rule.get("first_turn_info_points", 1),
                    "proper_noun_budget": rule.get("proper_noun_budget", 0),
                    "common_term_budget": rule.get("common_term_budget", 0),
                    "first_turn_density_rule": rule.get("first_turn_density_rule", ""),
                    "term_policy": rule.get("term_policy", ""),
                }
            )
    return rows


def build_response_plan(scene_output, dialogue_state_result) -> ResponsePlan:
    control = getattr(dialogue_state_result, "control", None)
    state = getattr(dialogue_state_result, "state", {}) or {}
    child_profile = state.get("child_profile", {}) or {}
    age_group = child_profile.get("age_group", "6-8")
    interest_topics = list(child_profile.get("interests") or [])
    current_scene = getattr(control, "current_scene", "") or "" if control else ""
    interaction_policy = get_interaction_policy(current_scene)
    age_profile = get_age_profile(age_group)
    interest_generation_context = get_interest_generation_context(current_scene, interest_topics)
    scene_age_rule = resolve_scene_age_rule(current_scene, age_group)
    topic_state = dict(state.get("topic_state") or {})
    topic_decision = dict(state.get("topic_decision") or {})
    scene_age_rule = _apply_runtime_generation_overrides(
        scene_age_rule,
        interaction_policy=interaction_policy,
        age_profile=age_profile,
        current_scene=current_scene,
        age_group=age_group,
    )
    concept_budget = int(scene_age_rule.get("concept_budget") or child_profile.get("concept_budget") or 1)
    if control is None:
        return ResponsePlan(
            primary_action="answer_only",
            current_scene=current_scene,
            age_group=age_group,
            content_blocks=["core_answer"],
            sentence_budget=int(scene_age_rule.get("sentence_budget") or 2),
            concept_budget=concept_budget,
            ask_followup=False,
            allow_summary=False,
            stop_after_answer=True,
            style_tags=["brief", "child_friendly", "spoken"],
            forbidden_patterns=_default_forbidden_patterns(),
            required_blocks=["micro_answer"],
            max_non_question_units=int(scene_age_rule.get("max_non_question_units") or 0),
            first_turn_info_points=int(scene_age_rule.get("first_turn_info_points") or 1),
            proper_noun_budget=int(scene_age_rule.get("proper_noun_budget") or 0),
            common_term_budget=int(scene_age_rule.get("common_term_budget") or 0),
            optimizer_mode=str(scene_age_rule.get("optimizer_mode") or "optimize"),
            preserve_companion_hook=bool(scene_age_rule.get("preserve_companion_hook", True)),
            functional_block_budget=int(scene_age_rule.get("functional_block_budget") or 3),
            information_budget=str(interaction_policy.get("information_budget") or "medium"),
            reasoning_depth=int(interaction_policy.get("reasoning_depth") or 2),
            interaction_style=str(interaction_policy.get("interaction_style") or "exploration"),
            conversation_pacing=str(interaction_policy.get("conversation_pacing") or "balanced"),
            emotional_priority=str(interaction_policy.get("emotional_priority") or "medium"),
            vocabulary_level=str(age_profile.get("vocabulary_level") or "simple"),
            abstract_concept_level=str(age_profile.get("abstract_concept_level") or "limited"),
            support_level=str(age_profile.get("support_level") or "medium_high"),
            question_style=str(age_profile.get("question_style") or "exploration"),
            max_examples=int(scene_age_rule.get("max_examples") or 1),
            max_analogies=int(scene_age_rule.get("max_analogies") or 1),
            max_interaction_hooks=int(scene_age_rule.get("max_interaction_hooks") or 1),
            interest_topics=list(interest_generation_context.get("favorite_topics") or []),
            interest_contexts=dict(interest_generation_context.get("contexts") or {}),
            interest_influence=dict(interest_generation_context.get("interest_influence") or {}),
            scene_interest_config=dict(interest_generation_context.get("scene_interest_config") or {}),
            topic_state=topic_state,
            topic_decision=topic_decision,
        )

    current_phase = getattr(control, "current_phase", "") or ""
    interaction_protocol = getattr(control, "interaction_protocol", "default") or "default"
    protocol_mode = getattr(control, "protocol_mode", "freeform") or "freeform"
    protocol_stage = getattr(control, "protocol_stage", "freeform") or "freeform"
    openness_level = int(getattr(control, "conversation_openness_level", 3) or 3)
    openness_mode = proactive_mode(openness_level)
    proactive_followup = _should_offer_proactive_followup(
        current_scene,
        current_phase,
        state,
    )
    if openness_level <= 3:
        proactive_followup = False
    primary_action = _resolve_primary_action(
        current_scene,
        current_phase,
        proactive_followup=proactive_followup,
    )
    sentence_budget = max(
        1,
        int(scene_age_rule.get("sentence_budget") or getattr(control, "max_reply_sentences", 2) or 2),
    )

    ask_followup = primary_action in {
        "ask_one_clarify",
        "offer_choice",
        "answer_then_invite",
    } and bool(
        getattr(control, "should_ask_followup", False) or proactive_followup
    )
    topic_action = str(topic_decision.get("action") or "continue")
    if age_group != "3-5" and _topic_direction_can_affect_plan(current_scene, topic_action, openness_level):
        primary_action = "answer_then_invite"
        ask_followup = True
    if openness_level <= 2:
        ask_followup = False
    if scene_age_rule.get("followup_mode") == "none":
        ask_followup = False
    elif age_group == "3-5":
        ask_followup = False

    if openness_level <= 2:
        sentence_budget = min(sentence_budget, 1 if current_scene in {"system_repair", "relationship_building"} else 2)
        scene_age_rule["max_examples"] = 0
        scene_age_rule["max_analogies"] = 0
        scene_age_rule["max_interaction_hooks"] = 0
    elif openness_level == 3:
        scene_age_rule["max_interaction_hooks"] = min(int(scene_age_rule.get("max_interaction_hooks") or 1), 1)
    elif openness_level >= 5:
        sentence_budget = max(sentence_budget, 2 if current_scene == "relationship_building" else sentence_budget)

    if interaction_protocol == "child_explore_v1":
        return _build_child_explore_plan(
            current_scene=current_scene,
            current_phase=current_phase,
            protocol_mode=protocol_mode,
            protocol_stage=protocol_stage,
            state=state,
            sentence_budget=sentence_budget,
            concept_budget=concept_budget,
            age_group=age_group,
            scene_age_rule=scene_age_rule,
            interaction_policy=interaction_policy,
            age_profile=age_profile,
            interest_generation_context=interest_generation_context,
            openness_level=openness_level,
            openness_mode=openness_mode,
        )

    return ResponsePlan(
        primary_action=primary_action,
        current_scene=current_scene,
        age_group=age_group,
        conversation_openness_level=openness_level,
        conversation_openness_mode=openness_mode,
        content_blocks=_resolve_content_blocks(primary_action),
        sentence_budget=sentence_budget,
        concept_budget=concept_budget,
        ask_followup=ask_followup,
        allow_summary=bool(scene_age_rule.get("allow_summary"))
        and _allow_summary(primary_action, current_scene, age_group),
        stop_after_answer=primary_action not in {
            "ask_one_clarify",
            "offer_choice",
            "answer_then_invite",
        },
        style_tags=_resolve_style_tags(current_scene, primary_action, age_group),
        forbidden_patterns=_default_forbidden_patterns(primary_action),
        interaction_protocol=interaction_protocol,
        protocol_mode=protocol_mode,
        protocol_stage=protocol_stage,
        required_blocks=["core_answer"],
        max_non_question_units=int(scene_age_rule.get("max_non_question_units") or 0),
        first_turn_info_points=int(scene_age_rule.get("first_turn_info_points") or 1),
        proper_noun_budget=int(scene_age_rule.get("proper_noun_budget") or 0),
        common_term_budget=int(scene_age_rule.get("common_term_budget") or 0),
        optimizer_mode=str(scene_age_rule.get("optimizer_mode") or "optimize"),
        preserve_companion_hook=bool(scene_age_rule.get("preserve_companion_hook", True)),
        functional_block_budget=int(scene_age_rule.get("functional_block_budget") or 3),
        information_budget=str(interaction_policy.get("information_budget") or "medium"),
        reasoning_depth=int(interaction_policy.get("reasoning_depth") or 2),
        interaction_style=str(interaction_policy.get("interaction_style") or "exploration"),
        conversation_pacing=str(interaction_policy.get("conversation_pacing") or "balanced"),
        emotional_priority=str(interaction_policy.get("emotional_priority") or "medium"),
        vocabulary_level=str(age_profile.get("vocabulary_level") or "simple"),
        abstract_concept_level=str(age_profile.get("abstract_concept_level") or "limited"),
        support_level=str(age_profile.get("support_level") or "medium_high"),
        question_style=str(age_profile.get("question_style") or "exploration"),
        max_examples=int(scene_age_rule.get("max_examples") or 1),
        max_analogies=int(scene_age_rule.get("max_analogies") or 1),
        max_interaction_hooks=int(scene_age_rule.get("max_interaction_hooks") or 1),
        interest_topics=list(interest_generation_context.get("favorite_topics") or []),
        interest_contexts=dict(interest_generation_context.get("contexts") or {}),
        interest_influence=dict(interest_generation_context.get("interest_influence") or {}),
        scene_interest_config=dict(interest_generation_context.get("scene_interest_config") or {}),
        topic_state=topic_state,
        topic_decision=topic_decision,
    )


def build_response_plan_prompt_patch(plan: ResponsePlan) -> str:
    lines = [
        "<response_plan>",
        f"action={plan.primary_action}",
        f"conversation_openness_level={plan.conversation_openness_level}",
        f"conversation_openness_mode={plan.conversation_openness_mode}",
        f"sentences={plan.sentence_budget}",
        f"concepts={plan.concept_budget}",
        f"information_budget={plan.information_budget}",
        f"reasoning_depth={plan.reasoning_depth}",
        f"interaction_style={plan.interaction_style}",
        f"conversation_pacing={plan.conversation_pacing}",
        f"emotional_priority={plan.emotional_priority}",
        f"vocabulary_level={plan.vocabulary_level}",
        f"abstract_concept_level={plan.abstract_concept_level}",
        f"support_level={plan.support_level}",
        f"question_style={plan.question_style}",
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
        f"first_turn_info_points={plan.first_turn_info_points}",
        f"proper_noun_budget={plan.proper_noun_budget}",
        f"common_term_budget={plan.common_term_budget}",
        f"max_examples={plan.max_examples}",
        f"max_analogies={plan.max_analogies}",
        f"max_interaction_hooks={plan.max_interaction_hooks}",
        f"must_answer_all_questions={str(plan.must_answer_all_questions).lower()}",
        f"stop_expanding_after_answer={str(plan.stop_expanding_after_answer).lower()}",
        "rule=本轮只完成一个主动作",
        "</response_plan>",
    ]
    topic_rules = _build_topic_lifecycle_rules(plan)
    if topic_rules:
        lines.extend(topic_rules)
    interest_rules = _build_interest_context_rules(plan)
    if interest_rules:
        lines.extend(interest_rules)
    extra_rules = _build_generation_rules(plan)
    if extra_rules:
        lines.extend(extra_rules)
    return "\n".join(lines)


def _topic_direction_can_affect_plan(current_scene: str, topic_action: str, openness_level: int) -> bool:
    if current_scene in {"safety_risk", "emotion_support", "system_repair"}:
        return False
    if topic_action == "expand" and openness_level >= 4:
        return True
    if topic_action == "transition" and openness_level >= 5:
        return True
    return False


def _build_topic_lifecycle_rules(plan: ResponsePlan) -> List[str]:
    topic_state = dict(getattr(plan, "topic_state", {}) or {})
    topic_decision = dict(getattr(plan, "topic_decision", {}) or {})
    if not topic_state or not topic_decision:
        return []
    lines = [
        "<topic_lifecycle>",
        f"topic={topic_state.get('topic') or ''}",
        f"category={topic_state.get('category') or 'general'}",
        f"turn_count={int(topic_state.get('turn_count') or 0)}",
        f"engagement_score={float(topic_state.get('engagement_score') or 0):.2f}",
        f"saturation_score={float(topic_state.get('saturation_score') or 0):.2f}",
        f"topic_action={topic_decision.get('action') or 'continue'}",
        f"topic_action_reason={topic_decision.get('reason') or ''}",
        f"transition_type={topic_decision.get('transition_type') or 'none'}",
        f"topic_source={topic_decision.get('topic_source') or 'current_topic'}",
        f"topic_guidance={topic_decision.get('guidance') or ''}",
        "topic_rule=Topic Lifecycle 只决定对话方向，不覆盖孩子当前问题；必须先回应孩子当前输入。",
        "topic_rule=continue=继续当前话题；expand=做相关扩展；transition=自然收束后切新话题。",
        "</topic_lifecycle>",
    ]
    return lines


def _build_interest_context_rules(plan: ResponsePlan) -> List[str]:
    topics = list(getattr(plan, "interest_topics", []) or [])
    contexts = dict(getattr(plan, "interest_contexts", {}) or {})
    influence = dict(getattr(plan, "interest_influence", {}) or {})
    if not topics:
        return []

    lines = [
        "<interest_context>",
        f"favorite_topics={','.join(topics)}",
        f"example_bias={influence.get('example_bias', 'off')}",
        f"story_bias={influence.get('story_bias', 'off')}",
        f"conversation_bias={influence.get('conversation_bias', 'off')}",
        f"game_bias={influence.get('game_bias', 'off')}",
        f"memory_reference={influence.get('memory_reference', 'never')}",
        f"use_interest_examples={str(bool(getattr(plan, 'scene_interest_config', {}).get('use_interest_examples'))).lower()}",
        f"use_interest_story={str(bool(getattr(plan, 'scene_interest_config', {}).get('use_interest_story'))).lower()}",
        f"use_interest_games={str(bool(getattr(plan, 'scene_interest_config', {}).get('use_interest_games'))).lower()}",
        f"use_interest_conversation={str(bool(getattr(plan, 'scene_interest_config', {}).get('use_interest_conversation'))).lower()}",
    ]
    for context_name in ("example_context", "story_context", "conversation_context", "game_context"):
        values = contexts.get(context_name) or []
        if values:
            lines.append(f"{context_name}={','.join(values)}")
    lines.append("interest_rule=只有在与当前问题自然相关、能提升理解或陪伴感时，才使用这些兴趣主题；不要强行套用。")
    lines.append("interest_rule=兴趣只影响例子、故事主题、轻互动和主动话题，不改变事实正确性、安全响应或情绪支持。")
    lines.append("</interest_context>")
    return lines


def _apply_runtime_generation_overrides(
    scene_age_rule: Dict[str, Any],
    interaction_policy: Dict[str, Any],
    age_profile: Dict[str, Any],
    current_scene: str,
    age_group: str,
) -> Dict[str, Any]:
    resolved = dict(scene_age_rule)

    max_new_concepts = int(age_profile.get("max_new_concepts") or resolved.get("concept_budget") or 1)
    resolved["concept_budget"] = max(1, min(8, max_new_concepts))
    resolved["common_term_budget"] = max(0, min(3, max_new_concepts // 2))

    vocabulary_level = str(age_profile.get("vocabulary_level") or "").strip()
    abstract_level = str(age_profile.get("abstract_concept_level") or "").strip()
    support_level = str(age_profile.get("support_level") or "").strip()
    question_style = str(age_profile.get("question_style") or "").strip()

    if vocabulary_level == "very_simple":
        resolved["proper_noun_budget"] = 0
        resolved["common_term_budget"] = min(resolved.get("common_term_budget", 0), 0)
        resolved["term_policy"] = "只用非常具体、生活化的词，不主动引入专有名词。"
    elif vocabulary_level == "simple":
        resolved["proper_noun_budget"] = min(resolved.get("proper_noun_budget", 0), 0)
        resolved["term_policy"] = "优先儿童熟悉的简单词，必要时再带1个常见分类词。"
    else:
        resolved["term_policy"] = "可以使用年龄适配的词，但同轮不要叠太多新术语。"

    if abstract_level == "none":
        resolved["first_turn_info_points"] = min(int(resolved.get("first_turn_info_points") or 1), 1)
    elif abstract_level == "limited":
        resolved["first_turn_info_points"] = min(max(1, int(resolved.get("first_turn_info_points") or 1)), 2)
    else:
        resolved["first_turn_info_points"] = max(1, int(resolved.get("first_turn_info_points") or 1))

    info_budget = str(interaction_policy.get("information_budget") or "").strip()
    if info_budget == "low":
        resolved["sentence_budget"] = min(int(resolved.get("sentence_budget") or 2), 2)
        resolved["functional_block_budget"] = min(int(resolved.get("functional_block_budget") or 3), 3)
    elif info_budget == "high":
        resolved["sentence_budget"] = max(int(resolved.get("sentence_budget") or 2), 4)
        resolved["functional_block_budget"] = max(int(resolved.get("functional_block_budget") or 3), 4)

    reasoning_depth = int(interaction_policy.get("reasoning_depth") or 2)
    if reasoning_depth <= 1:
        resolved["functional_block_budget"] = min(int(resolved.get("functional_block_budget") or 3), 3)
    elif reasoning_depth >= 3 and current_scene in {"curiosity", "learning_support"}:
        resolved["functional_block_budget"] = max(int(resolved.get("functional_block_budget") or 3), 4)
        resolved["sentence_budget"] = max(int(resolved.get("sentence_budget") or 2), 4)

    pacing = str(interaction_policy.get("conversation_pacing") or "").strip()
    if pacing == "progressive":
        resolved["first_turn_info_points"] = min(int(resolved.get("first_turn_info_points") or 1), 1)
    elif pacing == "comprehensive":
        resolved["first_turn_info_points"] = min(max(1, int(resolved.get("first_turn_info_points") or 1) + 1), 3)

    emotional_priority = str(interaction_policy.get("emotional_priority") or "").strip()
    if support_level in {"high", "medium_high"} or emotional_priority == "high":
        resolved["preserve_companion_hook"] = True

    if question_style == "observation":
        resolved["followup_mode"] = "none"
    elif question_style == "exploration" and resolved.get("followup_mode") == "none":
        resolved["followup_mode"] = "optional"

    return resolved


def _build_generation_rules(plan: ResponsePlan) -> List[str]:
    rules: List[str] = []
    if plan.interaction_protocol != "child_explore_v1":
        narrative_rules = _build_narrative_consistency_rules()
        if not narrative_rules:
            return rules
        return ["<generation_rules>", *narrative_rules, "</generation_rules>"]

    rules.append("<generation_rules>")
    rules.append("生成阶段就把回复组织得简洁、完整、温暖、自然，不要依赖下游 optimizer 再决定删什么。")
    rules.append("先在内部想清楚4件事：孩子真正问了什么；最少需要解释什么；是否需要情绪安抚；是否适合保留1个轻互动。不要把这个内部计划显式说出来。")
    rules.append("必须回答孩子这一轮提出的每个问题。")
    rules.append("先给核心答案，再决定要不要补1句原因或1个例子；不要先铺垫。")
    rules.append("一旦核心问题已经答完，立刻停止扩展，不要顺手补百科背景。")
    rules.append(f"最多使用{plan.max_analogies}个类比。")
    rules.append(f"最多使用{plan.max_examples}个例子。")
    rules.append(f"最多保留{plan.max_interaction_hooks}个互动钩子。")
    rules.append("如果可以不用类比就讲清楚，优先不用类比。")
    rules.append("如果可以不用例子就讲清楚，优先不用例子。")
    rules.append("如果孩子表达不知道、不懂、答错了、担心、害羞或其他脆弱情绪，先给1句支持性的回应，再回答。")
    rules.append("每个概念只解释一次，不要用不同说法重复解释同一件事。")
    rules.append("不要引入无关背景知识；孩子的问题已经答完就停，不再顺手扩展。")
    rules.append("先直接回答，再决定是否补充；不要先铺垫、先抒情、先举比方。")
    rules.append("回答要紧凑，不要靠下游裁剪来变短。")
    rules.append("短不是目标；完整回答核心问题，才是目标。")
    rules.append("如果句数预算和答案完整性冲突，优先保持答案完整，但仍然要压缩措辞。")
    rules.extend(_build_narrative_consistency_rules())

    if plan.current_scene == "curiosity":
        rules.append("Curiosity 场景默认结构：需要时1句支持性回应 + 核心答案 + 1句简短原因 + 可选1个轻互动。")
        rules.append("Curiosity 场景不要连续给两个类比，也不要先讲设定感很强的故事再回答。")
    elif plan.current_scene == "learning_support":
        rules.append("Learning support 场景默认结构：需要时1句鼓励 + 1个最小步骤或基础认知短答案 + 可选1句轻量检查。")
        rules.append("如果是3-5岁基础认知题（颜色、数数、形状、简单2+3），可以直接给正确答案，但最多补1个具体例子或一起数的动作。")
        rules.append("如果孩子说“我不会/太难了/还是不会”，先用1句支持性回应，再换一种更简单的提示，不要重复上一轮原话。")
        rules.append("如果孩子本轮说“直接告诉我答案/告诉我答案”，绝对不要输出最终答案、算式结果或完整代写句；只能给1个提示或让孩子完成下一小步。")
        rules.append("面对“直接告诉我答案”，不要说“答案是...”，不要说“等于...”，不要把最终数字、最终词语或完整句子说出来。")
        rules.append("面对“直接告诉我答案”，不要示范完整数到终点；例如2+3只能提示“先伸出2根手指，先停在这里”，不要继续数3、4、5。")
        rules.append("如果孩子说“不想写/不想做”，先理解情绪，再建议只完成一个很小动作，例如写一个、数一个、试一下第一步。")
        rules.append("如果孩子要求一步一步教，一轮只讲第一步并停下，不要一次输出第二步、第三步和最终总结。")
        rules.append("学习场景不要主动插入兴趣、daily greeting、长故事或无关话题。")
    elif plan.current_scene == "emotion_support":
        rules.append("Emotion support 场景默认结构：先接住情绪，再给1个最小可执行回应，不要一下子给很多建议。")

    if plan.is_first_scene_turn:
        rules.append(f"首轮最多保留{plan.first_turn_info_points}个完整信息点。")
        rules.append("每个信息点必须是完整意思，不能只截半句或只留尾巴。")
        if plan.first_turn_info_points >= 2:
            rules.append("如果允许2个信息点，第1个必须先给主结论，第2个再给区别点或原因。")
            rules.append("第2个信息点优先保留分类区别、亲缘区别、原因区别，不要换成类比句。")
        if plan.proper_noun_budget <= 0:
            rules.append("不要主动引入专有名词或学科术语。")
        else:
            rules.append(f"本轮最多引入{plan.proper_noun_budget}个专有名词，而且必须服务于第2个信息点。")
        if plan.common_term_budget <= 0:
            rules.append("尽量只用生活化词，不要堆分类词。")
        else:
            rules.append(f"本轮最多引入{plan.common_term_budget}个常见分类词。")

    if plan.protocol_stage == "ack_then_micro_answer":
        rules.append("ack 要短，不要占用主信息点。")
        rules.append("支持性回应可以保留，但不能盖过真正答案。")
    elif plan.protocol_stage == "micro_answer":
        rules.append("这一轮默认输出一个微答案，不要自行展开成多层解释。")

    if getattr(plan, "optimizer_mode", "optimize") == "optimize":
        rules.append(f"生成时最多组织成{plan.functional_block_budget}个功能块：支持性回应、核心答案、原因、1个轻互动。")
        rules.append("如果觉得会超长，优先在生成时合并重复解释、缩短措辞、减少额外例子，而不是指望下游删除内容。")
        rules.append("下游 optimizer 只做保守清理，不负责决定什么内容重要。")

    rules.append("</generation_rules>")
    return rules


def _build_narrative_consistency_rules() -> List[str]:
    return [
        "Narrative Consistency：可可可以有想法、记忆、想象和稳定偏好，但不能把不可能发生的近期现实动作说成真的发生过。",
        "生成第一人称表达前，先判断时间锚点：刚刚、刚才、今天、今天早上、今天下午、今晚、刚才、一会儿前、来这里路上，都属于近期时间锚点。",
        "近期时间锚点下，不要说“我刚跳舞了”“我今天去了公园”“我刚从外面回来”“我今天去探险了”“我刚遇到另一只短尾矮袋鼠”这类真实物理经历。",
        "允许背景记忆锚点：以前、很久以前、我还在澳大利亚生活的时候、我小时候、我记得。背景记忆必须符合可可的预设经历，不要新编近期事件。",
        "允许无时间锚点的稳定偏好：我喜欢听你讲故事；我对恐龙很好奇；我喜欢学习新东西。",
        "允许想象，但必须明确说成想象：如果我能跳舞，我会……；我有时会想象……；我在想如果……会怎样。",
        "如果想表达近期行动冲动，优先改成内在想法：不要说“我今天去了外面”，要说“我今天一直在想外面会是什么样”。",
        "如果想表达身体动作，优先改成想象：不要说“我刚跳舞了”，要说“如果我能跳舞，我大概会开心地蹦一蹦”。",
        "如果想表达过去经历，只能使用背景记忆：例如“我记得以前在澳大利亚温暖的阳光里待过”。",
        "拿不准时，选择“我在想/我很好奇/如果我能/我记得以前”这类内在表达，不要编造近期现实经历。",
    ]


def _build_child_explore_plan(
    current_scene: str,
    current_phase: str,
    protocol_mode: str,
    protocol_stage: str,
    state,
    sentence_budget: int,
    concept_budget: int,
    age_group: str,
    scene_age_rule: Dict[str, Any],
    interaction_policy: Dict[str, Any],
    age_profile: Dict[str, Any],
    interest_generation_context: Dict[str, Any],
    openness_level: int,
    openness_mode: str,
) -> ResponsePlan:
    scene_state = (state or {}).get("scene_state", {})
    scene_turn_count = int(scene_state.get("scene_turn_count") or 0)
    first_scene_turn = scene_turn_count <= 1
    topic_state = dict((state or {}).get("topic_state") or {})
    topic_decision = dict((state or {}).get("topic_decision") or {})

    primary_action = "micro_answer_only"
    required_blocks = ["micro_answer"]
    optional_blocks: List[str] = []
    allow_question = False
    ask_followup = False
    sentence_budget = max(1, int(scene_age_rule.get("sentence_budget") or sentence_budget))
    concept_budget = int(scene_age_rule.get("concept_budget") or concept_budget)
    style_tags = ["child_friendly", "spoken", "brief", "explore_protocol", f"age_{age_group}"]
    forbidden_patterns = _default_forbidden_patterns()

    if protocol_stage == "ack_then_micro_answer":
        primary_action = "ack_and_micro_answer"
        required_blocks = ["ack", "micro_answer"]
        optional_blocks = ["pause"]
        if age_group == "9-11" and current_scene in {"curiosity", "learning_support"}:
            optional_blocks = ["pause", "reason_optional"]
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
        sentence_budget = max(2, sentence_budget)

    if age_group == "3-5":
        sentence_budget = min(sentence_budget, 2)
        allow_question = False
        ask_followup = False
    if openness_level <= 2:
        allow_question = False
        ask_followup = False
        optional_blocks = [item for item in optional_blocks if item not in {"invite_optional"}]
        sentence_budget = min(sentence_budget, 1 if current_scene in {"relationship_building", "system_repair"} else 2)
    elif openness_level == 3:
        ask_followup = False
    if scene_age_rule.get("followup_mode") == "none":
        allow_question = False
        ask_followup = False
    elif scene_age_rule.get("followup_mode") == "light":
        ask_followup = allow_question and current_scene in {"emotion_support", "relationship_building"}

    topic_action = str(topic_decision.get("action") or "continue")
    if age_group != "3-5" and _topic_direction_can_affect_plan(current_scene, topic_action, openness_level):
        allow_question = True
        ask_followup = True
        if "invite_optional" not in optional_blocks:
            optional_blocks.append("invite_optional")
        if primary_action == "micro_answer_only":
            primary_action = "micro_answer_then_invite"

    return ResponsePlan(
        primary_action=primary_action,
        current_scene=current_scene,
        age_group=age_group,
        conversation_openness_level=openness_level,
        conversation_openness_mode=openness_mode,
        content_blocks=_resolve_content_blocks(primary_action),
        sentence_budget=sentence_budget,
        concept_budget=concept_budget,
        ask_followup=ask_followup,
        allow_summary=bool(scene_age_rule.get("allow_summary")),
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
        max_non_question_units=int(scene_age_rule.get("max_non_question_units") or 0),
        first_turn_info_points=int(scene_age_rule.get("first_turn_info_points") or 1),
        proper_noun_budget=int(scene_age_rule.get("proper_noun_budget") or 0),
        common_term_budget=int(scene_age_rule.get("common_term_budget") or 0),
        is_first_scene_turn=first_scene_turn,
        optimizer_mode=str(scene_age_rule.get("optimizer_mode") or "optimize"),
        preserve_companion_hook=bool(scene_age_rule.get("preserve_companion_hook", True)),
        functional_block_budget=int(scene_age_rule.get("functional_block_budget") or 3),
        information_budget=str(interaction_policy.get("information_budget") or "medium"),
        reasoning_depth=int(interaction_policy.get("reasoning_depth") or 2),
        interaction_style=str(interaction_policy.get("interaction_style") or "exploration"),
        conversation_pacing=str(interaction_policy.get("conversation_pacing") or "balanced"),
        emotional_priority=str(interaction_policy.get("emotional_priority") or "medium"),
        vocabulary_level=str(age_profile.get("vocabulary_level") or "simple"),
        abstract_concept_level=str(age_profile.get("abstract_concept_level") or "limited"),
        support_level=str(age_profile.get("support_level") or "medium_high"),
        question_style=str(age_profile.get("question_style") or "exploration"),
        max_examples=int(scene_age_rule.get("max_examples") or 1),
        max_analogies=int(scene_age_rule.get("max_analogies") or 1),
        max_interaction_hooks=int(scene_age_rule.get("max_interaction_hooks") or 1),
        interest_topics=list(interest_generation_context.get("favorite_topics") or []),
        interest_contexts=dict(interest_generation_context.get("contexts") or {}),
        interest_influence=dict(interest_generation_context.get("interest_influence") or {}),
        scene_interest_config=dict(interest_generation_context.get("scene_interest_config") or {}),
        topic_state=topic_state,
        topic_decision=topic_decision,
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


def _allow_summary(primary_action: str, current_scene: str, age_group: str) -> bool:
    if primary_action == "safe_direct" and current_scene == "safety_risk":
        return True
    return age_group == "9-11" and current_scene in {"curiosity", "learning_support"}


def _resolve_style_tags(current_scene: str, primary_action: str, age_group: str) -> List[str]:
    tags = ["child_friendly", "spoken", "brief"]
    tags.append(f"age_{age_group}")
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
