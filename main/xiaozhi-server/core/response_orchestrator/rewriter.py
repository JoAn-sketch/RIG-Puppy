from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List

from .planner import ResponsePlan


SUMMARY_PREFIXES = (
    "总的来说",
    "总之",
    "简单来说",
    "换句话说",
    "所以",
    "所以说",
)

FOLLOWUP_PATTERNS = (
    "你明白了吗",
    "你知道了吗",
    "你猜",
    "你觉得",
    "你想不想",
    "要不要",
)
HOOK_MARKERS = (
    "下次",
    "可以看看",
    "可以观察",
    "试着找找",
    "试试看",
    "留意",
    "观察",
    "看一看",
    "want to",
    "next time",
    "see if you can spot",
    "spot one",
)
COMPANION_REACTION_MARKERS = (
    "可爱",
    "萌",
    "真棒",
    "好玩",
    "有趣",
    "漂亮",
    "喜欢",
)
COMPANION_DESCRIPTION_MARKERS = (
    "滑溜溜",
    "游来游去",
    "跑来跑去",
    "跳来跳去",
    "摇来摇去",
    "毛茸茸",
    "圆滚滚",
    "亮晶晶",
    "软乎乎",
    "胖乎乎",
)

ADULT_STYLE_REPLACEMENTS = {
    "我来给你解释一下": "",
    "接下来我们来": "",
    "让我们一起来": "",
    "你可以理解为": "就像",
    "总的来说": "",
    "简单来说": "",
    "换句话说": "",
}

LEADING_PUNCTUATION = "，,。；;：:、 "
CLAUSE_SPLITTER = re.compile(r"[，,、；;：:。！？!?\n]+")
MARKUP_PATTERN = re.compile(r"[*_`#]+")
TAXONOMY_TERM_PATTERN = re.compile(r"[\u4e00-\u9fff]{1,8}(科|属|目|纲)")
ACK_MARKERS = (
    "这个问题",
    "这个想法",
    "这个呀",
    "好呀",
    "好，我们",
    "我在呢",
    "没事",
    "没关系",
    "不了解也没关系",
    "不知道也没关系",
    "不懂也没关系",
    "嗯",
    "诶",
    "哇",
)
ACK_PHRASE_PATTERNS = (
    "好问题",
    "问得好",
    "这个问得",
    "这个是个好",
    "不了解才好玩",
    "不知道也正常",
    "不懂也正常",
)
DEFAULT_ACK_BY_MODE = {
    "explain_first": "这个问题问得好呀。",
    "coach_step": "好，我们一步一步来。",
    "emotion_hold": "我在呢。",
    "playful_round": "好呀，我们来试试看。",
    "safe_direct": "先听我说。",
    "repair_reset": "好，我们重新来一下。",
    "warm_connect": "好呀。",
    "freeform": "好呀。",
}
INVITE_MARKERS = (
    "你想",
    "要不要",
    "还想",
    "想不想",
    "你猜",
    "你愿意",
    "要不要听",
    "还要听",
)
FILLER_PREFIXES = (
    "其实",
    "然后",
    "而且",
    "另外",
    "还有",
    "比如",
    "例如",
    "你看",
    "你知道吗",
    "所以",
    "那么",
)
FRAGMENT_PREFIXES = (
    "还有",
    "而且",
    "另外",
    "比如",
    "例如",
)
ADDRESS_PREFIXES = (
    "乐乐",
    "宝宝",
    "宝贝",
    "小朋友",
    "小宝",
    "小可爱",
)
ANALOGY_MARKERS = ("像", "就像", "好比", "好像")
APPEARANCE_MARKERS = (
    "毛色",
    "颜色",
    "红棕色",
    "红褐色",
    "黑白",
    "黑白配色",
    "红红的",
    "脸圆圆的",
    "大尾巴",
    "尾巴",
    "毛茸茸",
    "蓬松",
    "胖乎乎",
    "胖胖的",
    "个子小",
    "个头",
    "体型",
    "跳来跳去",
    "灵活",
    "讨人喜欢",
    "可爱",
    "看起来",
    "长得",
)
DIET_MARKERS = (
    "吃",
    "竹子",
    "竹叶",
    "果子",
    "苹果",
    "鸟蛋",
    "小鸟蛋",
    "啃竹子",
)
PROPER_NOUN_HINTS = (
    "生态系统",
    "光合作用",
    "二氧化碳",
    "食肉目",
)
COMMON_TERM_HINTS = (
    "动物",
    "植物",
    "昆虫",
    "鱼",
    "鸟",
    "星球",
    "情绪",
    "规则",
    "习惯",
    "分类",
    "哺乳动物",
)
DISTINCTION_MARKERS = (
    "但是",
    "不过",
    "而",
    "而且",
    "区别",
    "不同",
    "不一样",
    "不是同一种",
    "不是一种",
    "不属于",
    "分家",
    "各自",
)
DEFINITION_MARKERS = (
    "是",
    "属于",
    "叫",
    "分成",
    "分为",
    "有自己的",
)
ANSWER_HINT_MARKERS = (
    "因为",
    "就是",
    "是",
    "有",
    "会",
    "能",
    "可以",
    "让",
    "把",
    "用",
    "叫",
)
RECENT_TIME_ANCHORS = (
    "刚刚",
    "刚才",
    "刚",
    "今天",
    "今早",
    "今天早上",
    "今天上午",
    "今天中午",
    "今天下午",
    "今晚",
    "一会儿前",
    "来这里路上",
    "just now",
    "today",
    "this morning",
    "this afternoon",
    "tonight",
    "a moment ago",
    "on my way here",
)
NARRATIVE_SAFE_MARKERS = (
    "我在想",
    "我一直在想",
    "我想到",
    "我很好奇",
    "我有点好奇",
    "我记得",
    "我想象",
    "我会想象",
    "如果我",
    "要是我",
    "I think",
    "I've been thinking",
    "I am thinking",
    "I remember",
    "I imagine",
    "If I",
    "I wonder",
)
IMPOSSIBLE_RECENT_ACTION_MARKERS = (
    "去了",
    "去过",
    "跑去",
    "回来",
    "刚从",
    "玩了",
    "跳舞",
    "跳了舞",
    "蹦了",
    "散步",
    "探险",
    "探索",
    "见到",
    "遇到",
    "看见",
    "看到",
    "游泳",
    "爬树",
    "went",
    "came back",
    "played",
    "danced",
    "explored",
    "met another",
    "saw another",
)


@dataclass
class ResponseRewriteResult:
    raw_reply: str
    rewritten_reply: str
    rewrite_actions: List[str] = field(default_factory=list)
    quality_flags: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class OptimizerContext:
    latest_user_message: str = ""
    raw_assistant_reply: str = ""
    current_scene: str = ""
    age_profile: str = ""


@dataclass
class UserCommunicationState:
    state: str = "casual_conversation"
    needs_supportive_ack: bool = False


@dataclass
class AckAnalysis:
    text: str = ""
    kind: str = "none"


def rewrite_reply_text(
    reply_text: str,
    plan: ResponsePlan | None,
    user_text: str | None = None,
) -> ResponseRewriteResult:
    raw_reply = _normalize_whitespace(reply_text)
    if not raw_reply:
        return ResponseRewriteResult(
            raw_reply=raw_reply,
            rewritten_reply=raw_reply,
            quality_flags={
                "too_long": False,
                "has_summary": False,
                "has_followup": False,
                "multi_concept": False,
            },
        )

    plan = plan or ResponsePlan(primary_action="answer_only")
    optimizer_context = OptimizerContext(
        latest_user_message=_normalize_whitespace(user_text or ""),
        raw_assistant_reply=raw_reply,
        current_scene=str(getattr(plan, "current_scene", "") or ""),
        age_profile=str(getattr(plan, "age_group", "") or ""),
    )
    rewrite_actions: List[str] = []
    text = raw_reply
    for source, target in ADULT_STYLE_REPLACEMENTS.items():
        if source in text:
            text = text.replace(source, target)
            rewrite_actions.append(f"replace:{source}")
    text = _apply_narrative_consistency_policy(text, rewrite_actions)
    sentences = _split_sentences(text)
    if not sentences:
        sentences = [text]

    if _should_preserve_short_companion_reply(sentences, plan):
        preserved = _normalize_whitespace("".join(sentences).strip())
        rewrite_actions.append("preserve_short_companion_reply")
        return ResponseRewriteResult(
            raw_reply=raw_reply,
            rewritten_reply=preserved or raw_reply,
            rewrite_actions=_dedupe_preserve_order(rewrite_actions),
            quality_flags={
                "too_long": False,
                "has_summary": any(_is_summary_sentence(sentence) for sentence in sentences),
                "has_followup": any(_is_followup_sentence(sentence) for sentence in sentences),
                "multi_concept": False,
            },
        )

    if getattr(plan, "optimizer_mode", "optimize") == "optimize":
        optimized = _rewrite_with_optimizer(sentences, plan, rewrite_actions)
        rewritten = _normalize_whitespace("".join(optimized).strip())
        return ResponseRewriteResult(
            raw_reply=raw_reply,
            rewritten_reply=rewritten or raw_reply,
            rewrite_actions=_dedupe_preserve_order(rewrite_actions),
            quality_flags={
                "too_long": len(sentences) > plan.sentence_budget,
                "has_summary": any(_is_summary_sentence(sentence) for sentence in sentences),
                "has_followup": any(_is_followup_sentence(sentence) for sentence in sentences),
                "multi_concept": len(sentences) > max(2, plan.concept_budget + 1),
            },
        )

    has_summary = any(_is_summary_sentence(sentence) for sentence in sentences)
    has_followup = any(_is_followup_sentence(sentence) for sentence in sentences)
    too_long = len(sentences) > plan.sentence_budget

    filtered = []
    for sentence in sentences:
        sentence = _cleanup_sentence(sentence)
        if not sentence:
            continue
        if not plan.allow_summary and _is_summary_sentence(sentence):
            rewrite_actions.append("remove_summary")
            continue
        if not plan.ask_followup and _is_followup_sentence(sentence):
            rewrite_actions.append("remove_followup")
            continue
        filtered.append(sentence)

    filtered = _enforce_question_order(filtered, plan, rewrite_actions)

    if plan.primary_action in {"ask_one_clarify", "offer_choice"}:
        answer_sentences = [sentence for sentence in filtered if not _looks_like_question(sentence)]
        question_sentences = [sentence for sentence in filtered if _looks_like_question(sentence)]
        if answer_sentences and question_sentences:
            filtered = [answer_sentences[0], question_sentences[0]]
            rewrite_actions.append("keep_answer_plus_question")
        elif question_sentences:
            filtered = question_sentences[:1]
            rewrite_actions.append("keep_single_question")
        else:
            filtered = filtered[:1]
    elif plan.primary_action in {"answer_then_invite", "micro_answer_then_invite"}:
        answer_sentences = [sentence for sentence in filtered if not _looks_like_question(sentence)]
        question_sentences = [sentence for sentence in filtered if _looks_like_question(sentence)]
        rebuilt = []
        if answer_sentences:
            rebuilt.append(answer_sentences[0])
        if question_sentences:
            rebuilt.append(question_sentences[0])
            rewrite_actions.append("keep_single_light_followup")
        filtered = rebuilt or filtered[:1]
    else:
        filtered = [sentence for sentence in filtered if not _looks_like_question(sentence)]
        if not filtered:
            filtered = [sentences[0]]

    filtered = _enforce_child_explore_protocol(filtered, plan, rewrite_actions)
    filtered = _optimize_response_blocks(filtered, plan, rewrite_actions)

    if plan.primary_action == "emotion_validate":
        no_advice = []
        for sentence in filtered:
            if any(marker in sentence for marker in ("你可以", "你先", "你要")) and len(filtered) > 1:
                rewrite_actions.append("remove_extra_advice")
                continue
            no_advice.append(sentence)
        filtered = no_advice or filtered[:1]

    filtered = _enforce_information_density(filtered, plan, rewrite_actions)

    if len(filtered) > plan.sentence_budget:
        filtered = filtered[: plan.sentence_budget]
        rewrite_actions.append(f"trim_to_{plan.sentence_budget}_sentences")

    rewritten = "".join(filtered).strip()
    if not rewritten:
        rewritten = sentences[0].strip()

    rewritten = _normalize_whitespace(rewritten)
    quality_flags = {
        "too_long": too_long,
        "has_summary": has_summary,
        "has_followup": has_followup,
        "multi_concept": len(sentences) > max(2, plan.concept_budget + 1),
    }
    return ResponseRewriteResult(
        raw_reply=raw_reply,
        rewritten_reply=rewritten,
        rewrite_actions=_dedupe_preserve_order(rewrite_actions),
        quality_flags=quality_flags,
    )


def _normalize_whitespace(text: str) -> str:
    text = (text or "").replace("\r", "").strip()
    text = MARKUP_PATTERN.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _rewrite_with_optimizer(
    sentences: List[str],
    plan: ResponsePlan,
    rewrite_actions: List[str],
) -> List[str]:
    cleaned: List[str] = []
    for sentence in sentences:
        sentence = _cleanup_sentence(sentence)
        if not sentence:
            continue
        if not plan.allow_summary and _is_summary_sentence(sentence):
            rewrite_actions.append("remove_summary")
            continue
        cleaned.append(sentence)
    if not cleaned:
        return sentences[:1]

    if _should_skip_optimizer(cleaned, plan):
        rewrite_actions.append("skip_optimizer_short_response")
        return cleaned

    optimized = _safe_cleanup_sentences(cleaned, rewrite_actions)
    if optimized == cleaned:
        rewrite_actions.append("optimizer_keep_original")
        return cleaned
    rewrite_actions.append("safe_cleanup_only")
    return optimized or cleaned


def _split_sentences(text: str) -> List[str]:
    parts = re.findall(r"[^。！？!?；;\n]+[。！？!?；;\n]?", text)
    return [part.strip() for part in parts if part and part.strip()]


def _apply_narrative_consistency_policy(text: str, rewrite_actions: List[str]) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return text
    rewritten = []
    changed = False
    for sentence in sentences:
        next_sentence = _rewrite_impossible_recent_first_person_action(sentence)
        if next_sentence != sentence:
            changed = True
            rewrite_actions.append("narrative_consistency_rewrite")
        rewritten.append(next_sentence)
    return "".join(rewritten) if changed else text


def _rewrite_impossible_recent_first_person_action(sentence: str) -> str:
    stripped = sentence.strip()
    if not stripped:
        return sentence
    if any(marker in stripped for marker in NARRATIVE_SAFE_MARKERS):
        return sentence
    if not _has_first_person_marker(stripped):
        return sentence
    if not any(anchor in stripped for anchor in RECENT_TIME_ANCHORS):
        return sentence
    if not any(action in stripped for action in IMPOSSIBLE_RECENT_ACTION_MARKERS):
        return sentence

    punctuation = "！" if stripped.endswith(("！", "!")) else "。"
    if any(marker in stripped for marker in ("跳舞", "跳了舞", "蹦了", "danced")):
        return f"如果我能跳舞，我大概会像开心的短尾矮袋鼠一样蹦一蹦{punctuation}"
    if any(marker in stripped for marker in ("见到", "遇到", "met another", "saw another")):
        return f"我在想，如果遇到另一只短尾矮袋鼠，会不会很好玩{punctuation}"
    if any(marker in stripped for marker in ("草地", "草丛", "灌木", "grass", "bush")):
        return f"我记得以前在澳大利亚那些有草和灌木的地方探索过{punctuation}"
    if any(marker in stripped for marker in ("外面", "公园", "树林", "海边", "动物园", "outside", "park", "zoo")):
        return f"我今天一直在想，外面会有什么有趣的东西{punctuation}"
    if any(marker in stripped for marker in ("回来", "刚从", "came back")):
        return f"我刚才是在想这些有趣的事{punctuation}"
    if any(marker in stripped for marker in ("探险", "探索", "散步", "explored", "went")):
        return f"我今天一直在想，如果能去探索会是什么感觉{punctuation}"
    return f"我刚才是在想象这件事{punctuation}"


def _has_first_person_marker(sentence: str) -> bool:
    lowered = (sentence or "").lower()
    return (
        "我" in sentence
        or "可可" in sentence
        or "quokka" in lowered
        or "i " in f"{lowered} "
        or "i'" in lowered
    )


def _cleanup_sentence(sentence: str) -> str:
    cleaned = _normalize_whitespace(sentence)
    cleaned = cleaned.lstrip(LEADING_PUNCTUATION)
    for prefix in ADDRESS_PREFIXES:
        if cleaned.startswith(prefix):
            remainder = cleaned[len(prefix) :].lstrip(LEADING_PUNCTUATION)
            if remainder:
                cleaned = remainder
                break
    for prefix in ("但是", "不过", "而且", "所以", "然后", "但", "而"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].lstrip(LEADING_PUNCTUATION)
            break
    return cleaned.strip()


def _is_summary_sentence(sentence: str) -> bool:
    stripped = sentence.strip()
    return any(stripped.startswith(prefix) for prefix in SUMMARY_PREFIXES)


def _looks_like_question(sentence: str) -> bool:
    stripped = sentence.strip()
    return stripped.endswith(("？", "?", "吗", "呢")) or any(
        marker in stripped for marker in ("为什么", "怎么", "是不是", "要不要", "你觉得", "你猜")
    )


def _is_followup_sentence(sentence: str) -> bool:
    stripped = sentence.strip()
    return _looks_like_question(stripped) and any(pattern in stripped for pattern in FOLLOWUP_PATTERNS)


def _enforce_question_order(
    sentences: List[str], plan: ResponsePlan, rewrite_actions: List[str]
) -> List[str]:
    if not sentences:
        return sentences
    if not plan.allow_question:
        no_question = [sentence for sentence in sentences if not _looks_like_question(sentence)]
        if len(no_question) != len(sentences):
            rewrite_actions.append("remove_all_questions")
        return no_question or sentences[:1]
    if not plan.must_answer_before_question:
        return sentences

    answer_sentences = [sentence for sentence in sentences if not _looks_like_question(sentence)]
    question_sentences = [sentence for sentence in sentences if _looks_like_question(sentence)]
    if not question_sentences:
        return sentences
    if sentences and _looks_like_question(sentences[0]):
        rewrite_actions.append("remove_leading_question")
    rebuilt = []
    if answer_sentences:
        rebuilt.extend(answer_sentences[:2])
    if question_sentences and plan.question_position == "after_answer_only":
        rebuilt.append(question_sentences[0])
    return rebuilt or answer_sentences or sentences[:1]


def _enforce_child_explore_protocol(
    sentences: List[str], plan: ResponsePlan, rewrite_actions: List[str]
) -> List[str]:
    if plan.interaction_protocol != "child_explore_v1":
        return sentences

    non_question = [sentence for sentence in sentences if not _looks_like_question(sentence)]
    question_sentences = [sentence for sentence in sentences if _looks_like_question(sentence)]
    ack_analysis = _extract_ack_sentence(non_question)
    ack_sentence = ack_analysis.text or None
    info_point_budget = int(getattr(plan, "first_turn_info_points", 1) or 1)
    candidate_limit = max(2, info_point_budget)
    core_answers = _extract_core_answer_candidates(
        non_question,
        ack_sentence,
        limit=candidate_limit,
    )
    core_answers = _order_first_turn_information(core_answers)
    invite_sentence = _extract_invite_candidate(question_sentences) if plan.allow_question else None

    rebuilt = []
    if plan.open_with_ack:
        if ack_sentence is None:
            ack_sentence = DEFAULT_ACK_BY_MODE.get(
                plan.protocol_mode, DEFAULT_ACK_BY_MODE["freeform"]
            )
            rewrite_actions.append("prepend_protocol_ack")
        rebuilt.append(ack_sentence)

    if core_answers:
        rebuilt.extend(core_answers[: max(1, info_point_budget)])
        if any(core_answer not in non_question for core_answer in core_answers):
            rewrite_actions.append("distill_core_answer")
    elif non_question:
        fallback = _compress_to_core_answer(non_question[0])
        rebuilt.append(fallback)
        if fallback != non_question[0]:
            rewrite_actions.append("distill_core_answer")

    if invite_sentence:
        rebuilt.append(invite_sentence)
        rewrite_actions.append("keep_single_protocol_invite")

    deduped = []
    for sentence in rebuilt:
        if not sentence:
            continue
        if deduped and deduped[-1] == sentence:
            continue
        deduped.append(sentence)

    max_units = int(getattr(plan, "max_non_question_units", 0) or 0)
    if max_units <= 0:
        max_units = 1
    answer_unit_count = 0
    final_sentences = []
    question_kept = False
    for sentence in deduped:
        if _looks_like_question(sentence):
            if plan.allow_question and not question_kept:
                final_sentences.append(sentence)
                question_kept = True
            continue
        if _looks_like_ack_phrase(sentence):
            final_sentences.append(sentence)
            continue
        if answer_unit_count >= max_units:
            rewrite_actions.append("trim_extra_concepts")
            continue
        final_sentences.append(sentence)
        answer_unit_count += 1
    return final_sentences or deduped or sentences[:1]


def _optimize_response_blocks(
    sentences: List[str], plan: ResponsePlan, rewrite_actions: List[str]
) -> List[str]:
    if not sentences or getattr(plan, "optimizer_mode", "optimize") != "optimize":
        return sentences
    return sentences


def _should_skip_optimizer(sentences: List[str], plan: ResponsePlan) -> bool:
    sentence_budget = int(getattr(plan, "sentence_budget", 0) or 0)
    functional_budget = int(getattr(plan, "functional_block_budget", 0) or 0)
    if sentence_budget > 0 and len(sentences) <= sentence_budget:
        return True
    if functional_budget > 0 and len(sentences) <= functional_budget:
        return True
    total_len = len("".join(sentences))
    return total_len <= 90


def _safe_cleanup_sentences(
    sentences: List[str], rewrite_actions: List[str]
) -> List[str]:
    cleaned: List[str] = []
    seen_examples = set()
    seen_questions = set()
    last_normalized = ""

    for sentence in sentences:
        current = _cleanup_safe_surface(sentence)
        if not current:
            rewrite_actions.append("remove_empty_surface")
            continue

        normalized = _normalize_for_dedupe(current)
        if normalized == last_normalized:
            rewrite_actions.append("remove_duplicate_sentence")
            continue

        if _looks_like_question(current):
            if normalized in seen_questions:
                rewrite_actions.append("remove_duplicate_interaction")
                continue
            seen_questions.add(normalized)
        elif _looks_like_example_sentence(current):
            if normalized in seen_examples:
                rewrite_actions.append("remove_duplicate_example")
                continue
            seen_examples.add(normalized)

        cleaned.append(current)
        last_normalized = normalized

    return cleaned or sentences


def _cleanup_safe_surface(sentence: str) -> str:
    current = sentence.strip()
    current = re.sub(r"(。)\1{1,}", r"\1", current)
    current = re.sub(r"(！)\1{1,}", r"\1", current)
    current = re.sub(r"(？)\1{1,}", r"\1", current)
    current = re.sub(r"(，)\1{1,}", r"\1", current)
    current = re.sub(r"(嗯|然后|就是|那个)(，\1)+", r"\1", current)
    current = re.sub(r"(比如|例如)(，|：)?\s*(比如|例如)", r"\1", current)
    current = re.sub(r"\s+", "", current)
    return current.strip()


def _normalize_for_dedupe(sentence: str) -> str:
    return re.sub(r"[，。！？!?；;：:\s]", "", sentence or "")


def _looks_like_example_sentence(sentence: str) -> bool:
    return any(marker in (sentence or "") for marker in ("比如", "例如", "像", "就像"))


def _enforce_information_density(
    sentences: List[str], plan: ResponsePlan, rewrite_actions: List[str]
) -> List[str]:
    if not sentences:
        return sentences

    info_point_budget = int(getattr(plan, "first_turn_info_points", 0) or 0)
    proper_noun_budget = int(getattr(plan, "proper_noun_budget", 0) or 0)
    common_term_budget = int(getattr(plan, "common_term_budget", 0) or 0)
    is_first_scene_turn = bool(getattr(plan, "is_first_scene_turn", False))

    if not is_first_scene_turn or info_point_budget <= 0:
        return sentences

    selected = []
    info_points_used = 0
    proper_nouns_used = 0
    common_terms_used = 0

    for sentence in sentences:
        if _looks_like_ack_phrase(sentence):
            selected.append(sentence)
            continue
        if _looks_like_question(sentence):
            selected.append(sentence)
            continue

        chosen_clause = _select_clause_with_term_budget(
            sentence,
            proper_noun_budget - proper_nouns_used,
            common_term_budget - common_terms_used,
            allow_fallback=info_points_used == 0,
        )
        if not chosen_clause:
            rewrite_actions.append("limit_term_heavy_clause")
            continue
        if chosen_clause != sentence:
            rewrite_actions.append("distill_for_term_budget")

        clause_proper = _count_proper_nouns(chosen_clause)
        clause_common = _count_matching_terms(chosen_clause, COMMON_TERM_HINTS)

        if info_points_used >= info_point_budget:
            rewrite_actions.append("limit_first_turn_info_points")
            continue

        selected.append(chosen_clause)
        info_points_used += 1
        proper_nouns_used += clause_proper
        common_terms_used += clause_common

    return _order_first_turn_information(selected) or sentences[:1]


def _count_matching_terms(sentence: str, terms: tuple[str, ...]) -> int:
    if not sentence:
        return 0
    remaining = sentence
    count = 0
    for term in sorted(set(terms), key=len, reverse=True):
        while term and term in remaining:
            remaining = remaining.replace(term, " ", 1)
            count += 1
    return count


def _count_proper_nouns(sentence: str) -> int:
    explicit_count = _count_matching_terms(sentence, PROPER_NOUN_HINTS)
    taxonomy_count = len(TAXONOMY_TERM_PATTERN.findall(sentence or ""))
    return explicit_count + taxonomy_count


def _select_clause_with_term_budget(
    sentence: str, proper_budget_left: int, common_budget_left: int, allow_fallback: bool
) -> str:
    cleaned = _cleanup_sentence(sentence)
    if not cleaned:
        return ""
    contrast_unit = _extract_taxonomy_contrast_unit(_extract_informative_answer_clauses(cleaned))
    if contrast_unit and _contrast_unit_fits_budget(contrast_unit, proper_budget_left, common_budget_left):
        return contrast_unit
    clauses = _extract_informative_answer_clauses(cleaned)
    if not clauses:
        return cleaned

    eligible = []
    fallback = []
    for clause in clauses:
        proper_count = _count_proper_nouns(clause)
        common_count = _count_matching_terms(clause, COMMON_TERM_HINTS)
        scored = (
            _score_clause_information(clause)
            + _score_clause_term_fit(clause, proper_count, common_count, proper_budget_left, common_budget_left),
            clause,
        )
        if proper_count <= max(0, proper_budget_left) and common_count <= max(0, common_budget_left):
            eligible.append(scored)
        fallback.append(scored)

    pool = eligible or (fallback if allow_fallback else [])
    if not pool:
        return ""
    pool.sort(key=lambda item: item[0], reverse=True)
    best = pool[0][1]
    return _join_clauses([best])


def _extract_ack_sentence(
    sentences: List[str],
    context: OptimizerContext | None = None,
    user_state: UserCommunicationState | None = None,
) -> AckAnalysis:
    context = context or OptimizerContext()
    user_state = user_state or UserCommunicationState()
    for sentence in sentences[:2]:
        stripped = sentence.strip()
        if _looks_like_ack_phrase(stripped):
            if _looks_like_supportive_ack_for_user_state(stripped, context, user_state):
                return AckAnalysis(text=sentence, kind="supportive_ack")
            return AckAnalysis(text=sentence, kind="social_ack")
        if _looks_like_supportive_ack_for_user_state(stripped, context, user_state):
            return AckAnalysis(text=sentence, kind="supportive_ack")
        if len(stripped) <= 12 and stripped.endswith(("呀。", "呀", "呢。", "呢", "哦。", "哦")):
            return AckAnalysis(text=sentence, kind="social_ack")
    return AckAnalysis()


def _extract_core_answer_candidate(
    sentences: List[str], ack_sentence: str | None
) -> str | None:
    candidates = _extract_core_answer_candidates(sentences, ack_sentence, limit=1)
    return candidates[0] if candidates else None


def _extract_core_answer_candidates(
    sentences: List[str], ack_sentence: str | None, limit: int = 1
) -> List[str]:
    candidates = []
    for sentence in sentences:
        if sentence == ack_sentence:
            continue
        for unit in _extract_information_units(sentence):
            candidates.append((_score_core_answer(unit), unit))
    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0], reverse=True)
    deduped = []
    for _, core in candidates:
        if core in deduped:
            continue
        deduped.append(core)
        if len(deduped) >= max(1, limit):
            break
    return deduped


def _extract_informative_answer_clauses(sentence: str) -> List[str]:
    stripped = _cleanup_sentence(sentence)
    if not stripped:
        return []
    clauses = [_cleanup_sentence(part) for part in CLAUSE_SPLITTER.split(stripped)]
    clauses = [part for part in clauses if part]
    if not clauses:
        return []

    candidates = []
    for clause in clauses:
        if _looks_like_ack_phrase(clause):
            continue
        if _is_summary_sentence(clause):
            continue
        if any(marker in clause for marker in INVITE_MARKERS):
            continue
        if any(marker in clause for marker in ANALOGY_MARKERS):
            continue
        candidates.append(clause)

    if not candidates:
        compressed = _compress_to_core_answer(sentence)
        return [compressed] if compressed else []

    return candidates


def _extract_information_units(sentence: str) -> List[str]:
    clauses = _extract_informative_answer_clauses(sentence)
    if not clauses:
        return []

    units: List[str] = []
    contrast_unit = _extract_taxonomy_contrast_unit(clauses)
    if contrast_unit:
        units.append(contrast_unit)

    i = 0
    while i < len(clauses):
        clause = clauses[i]
        if _is_analogy_clause(clause):
            i += 1
            continue

        current = [clause]
        if i + 1 < len(clauses):
            next_clause = clauses[i + 1]
            if _should_merge_information_unit(clause, next_clause):
                current.append(next_clause)
                i += 1
        joined = _join_clauses(current)
        if contrast_unit and joined in contrast_unit:
            i += 1
            continue
        units.append(joined)
        i += 1

    deduped = []
    for unit in units:
        if unit not in deduped:
            deduped.append(unit)
    return deduped


def _extract_primary_explanation_block(sentences: List[str]) -> str:
    if not sentences:
        return ""
    candidates = []
    for sentence in sentences:
        unit = _compress_to_information_block(sentence, prefer_reason=False)
        if unit:
            candidates.append((_score_explanation_block(unit), unit))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_reason_block(sentences: List[str], exclude: str = "") -> str:
    if not sentences:
        return ""
    candidates = []
    for sentence in sentences:
        unit = _compress_to_information_block(sentence, prefer_reason=True)
        if not unit or unit == exclude:
            continue
        candidates.append((_score_reason_block(unit), unit))
    if not candidates:
        ack_text = _extract_ack_sentence(sentences).text
        for sentence in sentences:
            if sentence and sentence != exclude and sentence != ack_text:
                return sentence
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    best = candidates[0][1]
    if _score_reason_block(best) <= 0:
        return ""
    return best


def _compress_to_information_block(sentence: str, prefer_reason: bool) -> str:
    clauses = _extract_informative_answer_clauses(sentence)
    if not clauses:
        return ""
    if prefer_reason:
        contrast_unit = _extract_taxonomy_contrast_unit(clauses)
        if contrast_unit:
            return contrast_unit
        cause_clauses = [
            clause
            for clause in clauses
            if any(marker in clause for marker in ("因为", "所以", "亲缘关系", "属于", "分到", "有自己的"))
        ]
        if cause_clauses:
            return _join_clauses(cause_clauses[:2])
    units = _extract_information_units(sentence)
    if not units:
        return _join_clauses(clauses[:1])
    scored = []
    for unit in units:
        score = _score_reason_block(unit) if prefer_reason else _score_explanation_block(unit)
        scored.append((score, unit))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _shorten_ack(sentence: str, ack_kind: str = "social_ack") -> str:
    stripped = _cleanup_sentence(sentence)
    if ack_kind == "supportive_ack":
        if len(stripped) <= 20:
            return stripped if stripped.endswith(("。", "！", "？", ".", "!", "?")) else stripped + "。"
        if "没关系" in stripped:
            return "没关系。"
        if "正常" in stripped:
            return "这很正常。"
        if "一起" in stripped:
            return "我们可以一起看看。"
        return stripped[:18].rstrip("，,；;：: ") + "。"
    if re.search(r"[A-Za-z]", stripped):
        return "Great question!"
    if any(pattern in stripped for pattern in ACK_PHRASE_PATTERNS):
        return "这个问题问得好！"
    if any(marker in stripped for marker in ("真棒", "真好", "好呀")):
        return "好呀。"
    return stripped if len(stripped) <= 12 else "好问题！"


def _extract_invite_candidate(question_sentences: List[str]) -> str | None:
    for sentence in question_sentences:
        if any(marker in sentence for marker in FOLLOWUP_PATTERNS + INVITE_MARKERS):
            return sentence
    return question_sentences[0] if question_sentences else None


def _extract_interaction_hook(question_sentences: List[str]) -> str | None:
    return _extract_invite_candidate(question_sentences)


def _compress_to_core_answer(sentence: str) -> str:
    stripped = _cleanup_sentence(sentence)
    if not stripped:
        return ""
    clauses = [_cleanup_sentence(part) for part in CLAUSE_SPLITTER.split(stripped)]
    clauses = [part for part in clauses if part]
    if not clauses:
        return stripped

    informative = []
    for clause in clauses:
        if _is_summary_sentence(clause):
            continue
        if any(marker in clause for marker in INVITE_MARKERS):
            continue
        informative.append(clause)

    if not informative:
        informative = clauses[:1]

    best_clause = max(informative, key=_score_clause_information, default="")
    selected = [best_clause] if best_clause else []

    best_index = informative.index(best_clause) if best_clause in informative else -1
    if best_index > 0:
        previous = informative[best_index - 1]
        if _should_prepend_support_clause(previous, best_clause):
            selected.insert(0, previous)
    if best_index >= 0 and best_index + 1 < len(informative):
        following = informative[best_index + 1]
        if _should_merge_following_clause(selected[-1], following):
            selected.append(following)

    strong_non_analogy = [
        clause for clause in informative
        if _clause_is_strong_answer(clause) and not any(marker in clause for marker in ANALOGY_MARKERS)
    ]
    if strong_non_analogy:
        informative = [
            clause for clause in informative
            if not any(marker in clause for marker in ANALOGY_MARKERS)
        ] or strong_non_analogy

    if not selected:
        for clause in informative:
            if not selected:
                selected.append(clause)
                continue
            if len(selected) >= 2:
                break
            prev = selected[-1]
            if _should_merge_following_clause(prev, clause):
                selected.append(clause)
                continue
            if _clause_is_strong_answer(clause) and len(_join_clauses(selected)) < 14:
                selected.append(clause)
                continue
            break

    return _join_clauses(selected[:2]) or stripped


def _score_core_answer(text: str) -> int:
    score = 0
    stripped = text.strip()
    length = len(stripped)
    if 8 <= length <= 28:
        score += 5
    elif length < 6:
        score -= 3
    else:
        score += 2
    if _clause_is_strong_answer(stripped):
        score += 6
    if any(marker in stripped for marker in ("不是同一种", "不同", "不一样", "不属于")):
        score += 8
    if any(marker in stripped for marker in ("属于", "有自己的")):
        score += 4
    if any(marker in stripped for marker in ("单独分到", "单独分到了", "有自己的", "自己的一类")):
        score += 6
    if "亲缘关系" in stripped:
        score += 4
    if any(marker in stripped for marker in ANALOGY_MARKERS):
        score -= 3
    if any(marker in stripped for marker in FILLER_PREFIXES):
        score -= 2
    if _looks_like_ack_phrase(stripped):
        score -= 8
    score += _score_clause_information(stripped)
    return score


def _score_explanation_block(text: str) -> int:
    score = _score_core_answer(text)
    if any(marker in text for marker in ("是", "就是", "不同", "不一样", "不是同一种", "属于")):
        score += 4
    if any(marker in text for marker in ("因为", "所以")):
        score += 1
    if "科" in text or "family" in text.lower():
        score += 4
    if _is_analogy_clause(text):
        score -= 6
    return score


def _score_reason_block(text: str) -> int:
    score = _score_core_answer(text)
    if any(marker in text for marker in ("因为", "所以", "亲缘关系", "属于", "分到", "有自己的")):
        score += 6
    if any(marker in text for marker in ("熊科", "小熊猫科")) or "family" in text.lower():
        score += 4
    if any(marker in text for marker in ("不同", "不一样", "区别")):
        score += 3
    if _is_analogy_clause(text):
        score -= 6
    return score


def _score_distinction_block(text: str) -> int:
    score = _score_core_answer(text)
    if any(marker in text for marker in ("不同", "不一样", "区别", "不是同一种", "一个", "另一个")):
        score += 6
    if any(marker in text for marker in ("颜色", "个头", "尾巴", "脸", "长相", "体型")):
        score += 3
    if any(marker in text for marker in ("属于", "熊科", "小熊猫科", "有自己的")):
        score += 2
    if _is_analogy_clause(text):
        score -= 6
    return score


def _clause_is_strong_answer(clause: str) -> bool:
    stripped = clause.strip()
    return any(marker in stripped for marker in ANSWER_HINT_MARKERS)


def _score_clause_information(clause: str) -> int:
    stripped = clause.strip()
    score = 0
    if any(marker in stripped for marker in DEFINITION_MARKERS):
        score += 4
    if any(marker in stripped for marker in DISTINCTION_MARKERS):
        score += 4
    if "虽然" in stripped and any(marker in stripped for marker in ("但", "但是", "却")):
        score += 3
    if "因为" in stripped or "所以" in stripped:
        score += 2
    if any(marker in stripped for marker in ("单独分到", "单独分到了", "有自己的", "自己的一类")):
        score += 4
    if "亲缘关系" in stripped:
        score += 3
    if any(marker in stripped for marker in ANALOGY_MARKERS):
        score -= 2
    if any(marker in stripped for marker in FILLER_PREFIXES):
        score -= 2
    if _looks_like_ack_phrase(stripped):
        score -= 6
    if len(stripped) < 6:
        score -= 2
    if any(marker in stripped for marker in ("独一无二", "一家子")):
        score -= 2
    return score


def _classify_question_need(user_text: str | None) -> Dict[str, bool]:
    normalized = _normalize_whitespace(user_text or "")
    wants_reason = any(marker in normalized for marker in ("为什么", "怎么会", "怎么不是", "原因"))
    wants_distinction = any(
        marker in normalized
        for marker in ("哪里不一样", "有什么不一样", "区别", "不同", "不一样", "哪儿不一样")
    )
    wants_definition = any(
        marker in normalized
        for marker in ("是什么", "什么意思", "是不是", "为什么", "怎么不是", "怎么会")
    ) or not normalized
    return {
        "wants_reason": wants_reason,
        "wants_distinction": wants_distinction,
        "wants_definition": wants_definition,
    }


def _classify_user_communication_state(user_text: str | None) -> UserCommunicationState:
    normalized = _normalize_whitespace(user_text or "")
    if not normalized:
        return UserCommunicationState()
    if any(marker in normalized for marker in ("我不知道", "不知道", "不太懂", "不懂", "不了解", "挺陌生")):
        return UserCommunicationState(state="expressing_uncertainty", needs_supportive_ack=True)
    if any(marker in normalized for marker in ("我不明白", "没明白", "看不懂", "听不懂", "不理解")):
        return UserCommunicationState(state="expressing_confusion", needs_supportive_ack=True)
    if any(marker in normalized for marker in ("我错了", "我答错了", "我做错了", "没答对", "搞错了")):
        return UserCommunicationState(state="expressing_failure", needs_supportive_ack=True)
    if any(marker in normalized for marker in ("害怕", "担心", "紧张", "不好意思", "丢脸", "尴尬")):
        return UserCommunicationState(state="expressing_worry", needs_supportive_ack=True)
    if any(marker in normalized for marker in ("好开心", "太好了", "我会了", "我成功了", "我做到了")):
        return UserCommunicationState(state="sharing_excitement", needs_supportive_ack=False)
    if any(marker in normalized for marker in ("为什么", "怎么", "是什么", "什么意思", "是不是")):
        return UserCommunicationState(state="asking_factual_question", needs_supportive_ack=False)
    return UserCommunicationState(state="casual_conversation", needs_supportive_ack=False)


def _looks_like_supportive_ack_for_user_state(
    sentence: str,
    context: OptimizerContext | None = None,
    user_state: UserCommunicationState | None = None,
) -> bool:
    stripped = (sentence or "").strip()
    if not stripped:
        return False
    user_state = user_state or UserCommunicationState()
    if not user_state.needs_supportive_ack:
        return False
    supportive_markers = (
        "没关系",
        "没事",
        "别担心",
        "慢慢来",
        "正常",
        "可以一起",
        "一起看看",
        "一起想想",
        "不了解才好玩",
        "不知道也正常",
        "不懂也正常",
        "一开始都这样",
    )
    return any(marker in stripped for marker in supportive_markers)


def _score_clause_term_fit(
    clause: str,
    proper_count: int,
    common_count: int,
    proper_budget_left: int,
    common_budget_left: int,
) -> int:
    score = 0
    if proper_budget_left > 0 and proper_count == 1:
        score += 6
    elif proper_count > 1:
        score -= 3
    if common_budget_left > 0 and common_count == 1:
        score += 1
    if any(marker in clause for marker in ("属于", "分到", "分成", "分为", "有自己的")):
        score += 2
    if any(marker in clause for marker in ("单独分到", "单独分到了", "有自己的", "自己的一类")):
        score += 8
    return score


def _looks_like_ack_phrase(text: str) -> bool:
    stripped = text.strip()
    return any(marker in stripped for marker in ACK_MARKERS) or any(
        pattern in stripped for pattern in ACK_PHRASE_PATTERNS
    )


def _looks_like_companion_reaction(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if any(marker in stripped for marker in COMPANION_REACTION_MARKERS):
        return True
    if len(stripped) <= 12 and stripped.endswith(("呀", "呀。", "啊", "啊。", "呢", "呢。", "哦", "哦。")):
        return True
    return False


def _looks_like_companion_description(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped or _clause_is_strong_answer(stripped):
        return False
    if any(marker in stripped for marker in COMPANION_DESCRIPTION_MARKERS):
        return True
    if any(marker in stripped for marker in APPEARANCE_MARKERS):
        return True
    if _is_analogy_clause(stripped):
        return True
    return False


def _should_preserve_short_companion_reply(
    sentences: List[str], plan: ResponsePlan | None
) -> bool:
    if not sentences:
        return False
    if any(_looks_like_question(sentence) for sentence in sentences):
        return False

    cleaned = [_cleanup_sentence(sentence) for sentence in sentences if _cleanup_sentence(sentence)]
    if not cleaned:
        return False
    if len(cleaned) > 2:
        return False

    total_len = len("".join(cleaned))
    if total_len > 48:
        return False

    if any(_is_summary_sentence(sentence) for sentence in cleaned):
        return False
    if any(_clause_is_strong_answer(sentence) for sentence in cleaned):
        return False
    if any(
        marker in sentence
        for sentence in cleaned
        for marker in ("因为", "所以", "属于", "分到", "有自己的", "不是同一种", "不一样", "不同")
    ):
        return False

    has_reaction = any(_looks_like_companion_reaction(sentence) for sentence in cleaned)
    has_description = any(_looks_like_companion_description(sentence) for sentence in cleaned)
    if not (has_reaction and has_description):
        return False

    current_scene = str(getattr(plan, "current_scene", "") or "")
    return current_scene not in {"safety_risk", "system_repair"}


def _is_analogy_clause(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if any(marker in stripped for marker in ANALOGY_MARKERS):
        return True
    if "好像" in stripped or "打个比方" in stripped:
        return True
    if "而已" in stripped and ("名字里" in stripped or "看着" in stripped):
        return True
    return False


def _extract_taxonomy_contrast_unit(clauses: List[str]) -> str:
    if len(clauses) < 2:
        return ""
    taxonomy = [
        clause
        for clause in clauses
        if any(marker in clause for marker in ("属于", "单独属于", "小熊猫科", "熊科", "有自己的家族"))
    ]
    if len(taxonomy) < 2:
        return ""
    merged = _join_clauses(taxonomy[:2])
    return merged if merged else ""


def _contrast_unit_fits_budget(unit: str, proper_budget_left: int, common_budget_left: int) -> bool:
    if not unit:
        return False
    proper_count = _count_proper_nouns(unit)
    common_count = _count_matching_terms(unit, COMMON_TERM_HINTS)
    if proper_count <= max(0, proper_budget_left) and common_count <= max(0, common_budget_left):
        return True
    if proper_budget_left >= 1 and common_budget_left >= 0 and any(
        marker in unit for marker in ("小熊猫科", "熊科", "属于", "单独属于")
    ):
        return True
    return False


def _collect_answer_blocks(sentences: List[str]) -> List[str]:
    blocks = []
    for sentence in sentences:
        if not sentence:
            continue
        if _is_redundant_explanation(sentence, blocks):
            continue
        blocks.append(sentence)
    return blocks


def _build_optimizer_answer_blocks(sentences: List[str]) -> List[str]:
    blocks: List[str] = []
    cross_sentence_pair = _extract_cross_sentence_species_comparison(sentences)
    if cross_sentence_pair:
        blocks.append(cross_sentence_pair)
    for sentence in sentences:
        appearance_block = _extract_appearance_block(sentence)
        if appearance_block:
            if not _is_redundant_explanation(appearance_block, blocks):
                blocks.append(appearance_block)
            continue
        units = _extract_information_units(sentence) or [sentence]
        for unit in units:
            if _is_analogy_clause(unit):
                continue
            if _looks_like_fragment(unit):
                continue
            if _is_redundant_explanation(unit, blocks):
                continue
            blocks.append(unit)
    return _dedupe_preserve_order(blocks)


def _extract_cross_sentence_species_comparison(sentences: List[str]) -> str:
    if not sentences or len(sentences) < 2:
        return ""
    giant_side = ""
    red_side = ""
    for sentence in sentences[:3]:
        cleaned = _cleanup_sentence(sentence)
        if not cleaned:
            continue
        if not giant_side and "大熊猫" in cleaned and any(
            marker in cleaned for marker in APPEARANCE_MARKERS + ("公斤", "个头", "长尾巴")
        ):
            giant_side = cleaned
            continue
        if not red_side and "小熊猫" in cleaned and any(
            marker in cleaned for marker in APPEARANCE_MARKERS + ("公斤", "个头", "长尾巴")
        ):
            red_side = cleaned
            continue
    if giant_side and red_side:
        return _join_clauses([giant_side, red_side])
    return ""


def _select_optimizer_blocks(
    blocks: List[str],
    info_budget: int,
    context: OptimizerContext | None = None,
) -> List[str]:
    if not blocks:
        return []
    context = context or OptimizerContext()
    question_need = _classify_question_need(context.latest_user_message)
    if info_budget <= 1:
        if question_need["wants_reason"]:
            reason_only = _pick_best_reason(blocks)
            if reason_only:
                return [reason_only]
        if question_need["wants_distinction"]:
            distinction_only = _pick_best_distinction(blocks)
            if distinction_only:
                return [distinction_only]
        return [_pick_best_definition(blocks)]

    definition = _pick_best_definition(blocks)
    primary_distinction = _pick_best_distinction(blocks)
    contrast_expansion = _pick_complete_contrast_expansion(blocks, primary_distinction)
    comparison_pair = _pick_species_comparison_pair(blocks)
    distinction = _pick_best_distinction(blocks, exclude=definition)
    reason = _pick_best_reason(
        blocks,
        exclude=primary_distinction if question_need["wants_distinction"] else definition,
    )
    selected: List[str] = []
    if question_need["wants_definition"] and definition:
        selected.append(definition)
    if question_need["wants_distinction"] and primary_distinction and primary_distinction not in selected:
        selected.append(primary_distinction)
    if (
        question_need["wants_distinction"]
        and len(selected) < info_budget
        and contrast_expansion
        and contrast_expansion not in selected
    ):
        selected.append(contrast_expansion)
    if (
        question_need["wants_distinction"]
        and len(selected) < info_budget
        and comparison_pair
        and comparison_pair not in selected
    ):
        selected.append(comparison_pair)
    if question_need["wants_reason"] and reason and reason not in selected:
        selected.append(reason)
    if (
        question_need["wants_distinction"]
        and len(selected) < info_budget
        and distinction
        and distinction not in selected
    ):
        selected.append(distinction)
    if not selected:
        selected = [block for block in (definition, reason) if block]
    if question_need["wants_distinction"] and len(selected) < info_budget and reason and reason not in selected:
        selected.append(reason)
    if question_need["wants_reason"] and len(selected) < info_budget and distinction and distinction not in selected:
        selected.append(distinction)
    if not selected:
        return blocks[: max(1, info_budget)]
    selected = _prune_overlapping_blocks(selected)
    for block in blocks:
        if len(selected) >= info_budget:
            break
        if block not in selected and not _is_overlapped_by_selected(block, selected):
            selected.append(block)
    return selected[:info_budget]


def _pick_best_definition(blocks: List[str]) -> str:
    scored = [(_score_explanation_block(block), block) for block in blocks]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored else ""


def _pick_best_reason(blocks: List[str], exclude: str = "") -> str:
    taxonomy_pair = _pick_taxonomy_pair(blocks, exclude=exclude)
    if taxonomy_pair:
        return taxonomy_pair
    scored = [(_score_reason_block(block), block) for block in blocks if block != exclude]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else ""


def _pick_best_distinction(blocks: List[str], exclude: str = "") -> str:
    complete_pair = _pick_complete_species_comparison_block(blocks, exclude=exclude)
    if complete_pair:
        return complete_pair
    scored = [(_score_distinction_block(block), block) for block in blocks if block != exclude]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else ""


def _pick_taxonomy_pair(blocks: List[str], exclude: str = "") -> str:
    bear_side = ""
    red_panda_side = ""
    for block in blocks:
        if not block or block == exclude:
            continue
        if not bear_side and any(marker in block for marker in ("大熊猫属于熊科", "属于熊科", "熊科")):
            bear_side = block
            continue
        if not red_panda_side and any(
            marker in block for marker in ("小熊猫科", "自己独成一科", "有自己的家族", "有自己的科")
        ):
            red_panda_side = block
    if bear_side and red_panda_side:
        return _join_clauses([bear_side, red_panda_side])
    return ""


def _pick_species_comparison_pair(blocks: List[str]) -> str:
    complete_pair = _pick_complete_species_comparison_block(blocks)
    if complete_pair:
        return complete_pair
    red_panda_side = ""
    giant_panda_side = ""
    for block in blocks:
        if not block:
            continue
        if not red_panda_side and "小熊猫" in block and any(
            marker in block for marker in ("红", "尾巴", "体型", "个头", "颜色", "长相", "黑白")
        ):
            red_panda_side = block
            continue
        if not giant_panda_side and "大熊猫" in block and any(
            marker in block for marker in ("黑白", "体型", "个头", "颜色", "长相", "尾巴", "一米多")
        ):
            giant_panda_side = block
    if red_panda_side and giant_panda_side:
        return _join_clauses([red_panda_side, giant_panda_side])
    return ""


def _pick_complete_species_comparison_block(blocks: List[str], exclude: str = "") -> str:
    candidates = []
    for block in blocks:
        if not block or block == exclude:
            continue
        if _is_complete_species_comparison_block(block):
            candidates.append((_score_complete_species_comparison(block), block))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1] if candidates else ""


def _is_complete_species_comparison_block(block: str) -> bool:
    text = block or ""
    if "大熊猫" not in text or "小熊猫" not in text:
        return False
    return any(marker in text for marker in APPEARANCE_MARKERS + ("公斤", "个头", "长尾巴", "尾巴"))


def _score_complete_species_comparison(block: str) -> int:
    score = _score_distinction_block(block)
    if "大熊猫" in block and "小熊猫" in block:
        score += 12
    if any(marker in block for marker in ("公斤", "个头", "体型", "尾巴", "颜色", "长相")):
        score += 6
    if any(marker in block for marker in ANALOGY_MARKERS):
        score -= 2
    return score


def _pick_complete_contrast_expansion(blocks: List[str], summary_block: str = "") -> str:
    summary = summary_block or ""
    wants_appearance = any(marker in summary for marker in ("长相", "颜色", "外貌", "个头", "体型"))
    wants_diet = any(marker in summary for marker in ("吃", "食物", "吃的东西", "竹子", "果子"))

    red_appearance, giant_appearance = _pick_species_trait_pair(blocks, APPEARANCE_MARKERS)
    red_diet, giant_diet = _pick_species_trait_pair(
        blocks,
        DIET_MARKERS,
        allow_species_omission=True,
    )

    paired_clauses: List[str] = []
    if wants_appearance and red_appearance and giant_appearance:
        paired_clauses.append(_join_species_pair(red_appearance, giant_appearance))
    if wants_diet and red_diet and giant_diet:
        paired_clauses.append(_join_species_pair(red_diet, giant_diet))

    if not paired_clauses:
        if red_appearance and giant_appearance:
            paired_clauses.append(_join_species_pair(red_appearance, giant_appearance))
        elif red_diet and giant_diet:
            paired_clauses.append(_join_species_pair(red_diet, giant_diet))

    if not paired_clauses:
        return ""
    return _join_clauses(paired_clauses[:2])


def _pick_species_trait_pair(
    blocks: List[str],
    markers: tuple[str, ...],
    allow_species_omission: bool = False,
) -> tuple[str, str]:
    red_side = _pick_species_trait_block(
        blocks,
        "小熊猫",
        markers,
        allow_species_omission=allow_species_omission,
    )
    giant_side = _pick_species_trait_block(
        blocks,
        "大熊猫",
        markers,
        allow_species_omission=allow_species_omission,
    )
    if red_side and giant_side and _strip_trailing_punctuation(red_side) == _strip_trailing_punctuation(giant_side):
        return red_side, ""
    return red_side, giant_side


def _pick_species_trait_block(
    blocks: List[str],
    species: str,
    markers: tuple[str, ...],
    allow_species_omission: bool = False,
) -> str:
    fallback = ""
    last_species = ""
    for block in blocks:
        if not block:
            continue
        if "小熊猫" in block:
            last_species = "小熊猫"
        elif "大熊猫" in block:
            last_species = "大熊猫"
        if species in block and any(marker in block for marker in markers):
            return block
        if (
            allow_species_omission
            and not fallback
            and last_species == species
            and any(marker in block for marker in markers)
        ):
            normalized = _normalize_species_clause(species, block)
            if normalized:
                fallback = normalized
            continue
        if (
            not allow_species_omission
            and not fallback
            and last_species == species
            and any(marker in block for marker in markers)
        ):
            normalized = _normalize_species_clause(species, block)
            if normalized:
                fallback = normalized
            continue
        if allow_species_omission and not fallback and any(marker in block for marker in markers):
            if species == "大熊猫" and any(marker in block for marker in ("只吃", "几乎只", "啃竹子")):
                fallback = _normalize_species_clause("大熊猫", block)
            if species == "小熊猫" and any(marker in block for marker in ("还爱吃", "也爱吃", "果子", "鸟蛋")):
                fallback = _normalize_species_clause("小熊猫", block)
    return fallback


def _join_species_pair(first: str, second: str) -> str:
    first_clean = _strip_trailing_punctuation(first)
    second_clean = _strip_trailing_punctuation(second)
    if not first_clean:
        return second
    if not second_clean:
        return first
    return _join_clauses([first_clean, second_clean])


def _strip_species_prefix(text: str) -> str:
    value = _strip_trailing_punctuation(text).strip()
    for prefix in ("小熊猫", "大熊猫"):
        if value.startswith(prefix):
            return value[len(prefix):].lstrip("，,是")
    return value


def _normalize_species_clause(species: str, text: str) -> str:
    suffix = _strip_species_prefix(text)
    suffix = suffix.strip()
    if not suffix:
        return ""
    return f"{species}{suffix}"


def _prune_overlapping_blocks(blocks: List[str]) -> List[str]:
    pruned: List[str] = []
    for block in blocks:
        normalized = _strip_trailing_punctuation(block)
        if not normalized:
            continue
        duplicate = False
        replace_index = -1
        for index, existing in enumerate(pruned):
            existing_normalized = _strip_trailing_punctuation(existing)
            if normalized == existing_normalized:
                duplicate = True
                break
            if normalized in existing_normalized or existing_normalized in normalized:
                if len(normalized) <= len(existing_normalized):
                    duplicate = True
                    break
                replace_index = index
                break
        if duplicate:
            continue
        if replace_index >= 0:
            pruned[replace_index] = block
            continue
        if not duplicate:
            pruned.append(block)
    return pruned


def _is_overlapped_by_selected(block: str, selected: List[str]) -> bool:
    normalized = _strip_trailing_punctuation(block)
    if not normalized:
        return False
    for existing in selected:
        existing_normalized = _strip_trailing_punctuation(existing)
        if not existing_normalized:
            continue
        if normalized == existing_normalized:
            return True
        if normalized in existing_normalized:
            return True
    return False


def _strip_trailing_punctuation(text: str) -> str:
    return (text or "").strip().strip("。！？!?；;，, ")


def _select_answer_blocks(blocks: List[str], max_blocks: int) -> List[str]:
    if not blocks:
        return []
    if len(blocks) <= max_blocks:
        return blocks

    definition_blocks = [block for block in blocks if _looks_like_definition_block(block)]
    reason_blocks = [block for block in blocks if _looks_like_reason_block(block)]

    selected: List[str] = []
    if definition_blocks:
        selected.append(definition_blocks[0])
    if reason_blocks:
        for block in reason_blocks:
            if block not in selected:
                selected.append(block)
                break

    for block in blocks:
        if len(selected) >= max_blocks:
            break
        if block not in selected:
            selected.append(block)
    return selected[:max_blocks]


def _looks_like_definition_block(sentence: str) -> bool:
    return any(
        marker in (sentence or "")
        for marker in ("是", "就是", "可以理解成", "指的是", "不是同一种", "不同", "不一样")
    )


def _looks_like_reason_block(sentence: str) -> bool:
    return any(
        marker in (sentence or "")
        for marker in ("因为", "所以", "亲缘关系", "属于", "分到", "有自己的", "后来发现")
    )


def _looks_like_distinction_block(sentence: str) -> bool:
    return any(
        marker in (sentence or "")
        for marker in ("不同", "不一样", "区别", "不是同一种", "各自", "一个", "另一个")
    )


def _looks_like_hook_sentence(sentence: str) -> bool:
    lowered = (sentence or "").lower()
    if _looks_like_question(sentence):
        return True
    return any(marker in lowered for marker in HOOK_MARKERS)


def _extract_hook_from_any_sentence(sentences: List[str]) -> str:
    for sentence in sentences:
        if _looks_like_hook_sentence(sentence):
            return sentence
    return ""


def _extract_appearance_block(sentence: str) -> str:
    if _looks_like_reason_block(sentence) or _looks_like_definition_block(sentence):
        return ""
    clauses = [_cleanup_sentence(part) for part in CLAUSE_SPLITTER.split(_cleanup_sentence(sentence))]
    clauses = [clause for clause in clauses if clause]
    if not clauses:
        return ""
    matched = [clause for clause in clauses if any(marker in clause for marker in APPEARANCE_MARKERS)]
    if len(matched) >= 2:
        return _join_clauses(matched[:3])
    if matched and any(marker in sentence for marker in ("讨人喜欢", "可爱", "小小一只")):
        return _join_clauses(matched[:2])
    return ""


def _is_redundant_explanation(sentence: str, kept: List[str]) -> bool:
    if not kept:
        return False
    current_terms = set(_extract_semantic_markers(sentence))
    if not current_terms:
        return False
    for existing in kept:
        existing_terms = set(_extract_semantic_markers(existing))
        if current_terms and current_terms.issubset(existing_terms):
            return True
    return False


def _extract_semantic_markers(sentence: str) -> List[str]:
    markers = []
    patterns = (
        "科",
        "family",
        "亲缘关系",
        "属于",
        "小熊猫科",
        "熊科",
        "不同",
        "不一样",
        "不是同一种",
        "原因",
        "because",
        "different",
    )
    lowered = (sentence or "").lower()
    for pattern in patterns:
        if pattern.lower() in lowered:
            markers.append(pattern.lower())
    return markers


def _looks_like_fragment(sentence: str) -> bool:
    stripped = (sentence or "").strip()
    if len(stripped) <= 8 and not any(ch in stripped for ch in "。！？!?"):
        return True
    return any(stripped.startswith(prefix) for prefix in FRAGMENT_PREFIXES)


def _order_first_turn_information(sentences: List[str]) -> List[str]:
    if not sentences:
        return sentences
    prefix = []
    answers = []
    for sentence in sentences:
        if _looks_like_ack_phrase(sentence) or _looks_like_question(sentence):
            prefix.append(sentence)
            continue
        answers.append(sentence)
    if len(answers) <= 1:
        return prefix + answers
    ordered_answers = sorted(answers, key=_first_turn_answer_priority)
    return prefix + ordered_answers


def _first_turn_answer_priority(sentence: str) -> tuple[int, int, int, int]:
    analogy = 1 if _is_analogy_clause(sentence) else 0
    proper = _count_proper_nouns(sentence)
    distinction = 0 if any(marker in sentence for marker in DISTINCTION_MARKERS) else 1
    common = _count_matching_terms(sentence, COMMON_TERM_HINTS)
    score = -_score_core_answer(sentence)
    return (analogy, proper, distinction, common, score)


def _should_merge_information_unit(current: str, following: str) -> bool:
    if not current or not following:
        return False
    if _is_analogy_clause(following):
        return False
    if "亲缘关系" in current and any(marker in following for marker in ("属于", "分到", "小熊猫科", "熊科")):
        return True
    if any(marker in current for marker in ("不同", "不一样", "不是同一种")) and any(
        marker in following for marker in ("属于", "分到", "有自己的", "小熊猫科", "熊科")
    ):
        return True
    if any(marker in current for marker in ("属于", "分到")) and any(
        marker in following for marker in ("小熊猫科", "熊科", "有自己的")
    ):
        return True
    return False


def _should_prepend_support_clause(previous: str, current: str) -> bool:
    prev = previous.strip()
    curr = current.strip()
    if not prev or not curr:
        return False
    if _looks_like_ack_phrase(prev):
        return False
    if any(marker in prev for marker in ANALOGY_MARKERS):
        return False
    if "虽然" in prev and any(marker in curr for marker in ("但", "但是", "却", "而")):
        return True
    if _score_clause_information(prev) >= 4 and len(prev) <= 16:
        return True
    return False


def _should_merge_following_clause(previous: str, current: str) -> bool:
    prev = previous.strip()
    curr = current.strip()
    if not prev or not curr:
        return False
    if any(marker in curr for marker in ANALOGY_MARKERS):
        return False
    if prev.startswith("因为") and _clause_is_strong_answer(curr):
        return True
    if any(marker in prev for marker in ("虽然", "一种", "一员")) and any(
        marker in curr for marker in ("但", "但是", "而", "不同", "不一样", "各自", "分家")
    ):
        return True
    if _clause_is_strong_answer(prev):
        return False
    if len(prev) <= 10 and _clause_is_strong_answer(curr):
        return True
    if prev.endswith(("有鳃", "有壳", "有牙齿", "会呼吸", "是这样")):
        return True
    if any(marker in curr for marker in ("能", "会", "可以", "就是", "把")):
        return len(prev) < 14
    return False


def _join_clauses(clauses: List[str]) -> str:
    cleaned = [clause.strip("，,。！？!?；;：:、 ") for clause in clauses if clause]
    if not cleaned:
        return ""
    joined = "，".join(cleaned)
    if not joined.endswith(("。", "！", "？", ".", "!", "?")):
        joined += "。"
    return joined


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
