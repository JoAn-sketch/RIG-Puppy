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
CLAUSE_SPLITTER = re.compile(r"[，,、；;：:\n]+")
ACK_MARKERS = (
    "这个问题",
    "这个想法",
    "这个呀",
    "好呀",
    "好，我们",
    "我在呢",
    "没事",
    "嗯",
    "诶",
    "哇",
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
ANALOGY_MARKERS = ("像", "就像", "好比", "好像")
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


@dataclass
class ResponseRewriteResult:
    raw_reply: str
    rewritten_reply: str
    rewrite_actions: List[str] = field(default_factory=list)
    quality_flags: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def rewrite_reply_text(reply_text: str, plan: ResponsePlan | None) -> ResponseRewriteResult:
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
    rewrite_actions: List[str] = []
    text = raw_reply
    for source, target in ADULT_STYLE_REPLACEMENTS.items():
        if source in text:
            text = text.replace(source, target)
            rewrite_actions.append(f"replace:{source}")
    sentences = _split_sentences(text)
    if not sentences:
        sentences = [text]

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
        question_sentences = [sentence for sentence in filtered if _looks_like_question(sentence)]
        if question_sentences:
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

    if plan.primary_action == "emotion_validate":
        no_advice = []
        for sentence in filtered:
            if any(marker in sentence for marker in ("你可以", "你先", "你要")) and len(filtered) > 1:
                rewrite_actions.append("remove_extra_advice")
                continue
            no_advice.append(sentence)
        filtered = no_advice or filtered[:1]

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
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _split_sentences(text: str) -> List[str]:
    parts = re.findall(r"[^。！？!?；;\n]+[。！？!?；;\n]?", text)
    return [part.strip() for part in parts if part and part.strip()]


def _cleanup_sentence(sentence: str) -> str:
    cleaned = _normalize_whitespace(sentence)
    cleaned = cleaned.lstrip(LEADING_PUNCTUATION)
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
    ack_sentence = _extract_ack_sentence(non_question)
    core_answer = _extract_core_answer_candidate(non_question, ack_sentence)
    invite_sentence = _extract_invite_candidate(question_sentences) if plan.allow_question else None

    rebuilt = []
    if plan.open_with_ack:
        if ack_sentence is None:
            ack_sentence = DEFAULT_ACK_BY_MODE.get(
                plan.protocol_mode, DEFAULT_ACK_BY_MODE["freeform"]
            )
            rewrite_actions.append("prepend_protocol_ack")
        rebuilt.append(ack_sentence)

    if core_answer:
        rebuilt.append(core_answer)
        if core_answer not in non_question:
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

    max_units = 2 if plan.open_with_ack else 1
    non_question_count = 0
    final_sentences = []
    question_kept = False
    for sentence in deduped:
        if _looks_like_question(sentence):
            if plan.allow_question and not question_kept:
                final_sentences.append(sentence)
                question_kept = True
            continue
        if non_question_count >= max_units:
            rewrite_actions.append("trim_extra_concepts")
            continue
        final_sentences.append(sentence)
        non_question_count += 1
    return final_sentences or deduped or sentences[:1]


def _extract_ack_sentence(sentences: List[str]) -> str | None:
    for sentence in sentences[:2]:
        stripped = sentence.strip()
        if any(marker in stripped for marker in ACK_MARKERS):
            return sentence
        if len(stripped) <= 12 and stripped.endswith(("呀。", "呀", "呢。", "呢", "哦。", "哦")):
            return sentence
    return None


def _extract_core_answer_candidate(
    sentences: List[str], ack_sentence: str | None
) -> str | None:
    candidates = []
    for sentence in sentences:
        if sentence == ack_sentence:
            continue
        core = _compress_to_core_answer(sentence)
        if not core:
            continue
        candidates.append((_score_core_answer(core), core))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_invite_candidate(question_sentences: List[str]) -> str | None:
    for sentence in question_sentences:
        if any(marker in sentence for marker in INVITE_MARKERS):
            return sentence
    return question_sentences[0] if question_sentences else None


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

    strong_non_analogy = [
        clause for clause in informative
        if _clause_is_strong_answer(clause) and not any(marker in clause for marker in ANALOGY_MARKERS)
    ]
    if strong_non_analogy:
        informative = [
            clause for clause in informative
            if not any(marker in clause for marker in ANALOGY_MARKERS)
        ] or strong_non_analogy

    selected = []
    for idx, clause in enumerate(informative):
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
    if any(marker in stripped for marker in ANALOGY_MARKERS):
        score -= 3
    if any(marker in stripped for marker in FILLER_PREFIXES):
        score -= 2
    if any(marker in stripped for marker in ACK_MARKERS):
        score -= 8
    return score


def _clause_is_strong_answer(clause: str) -> bool:
    stripped = clause.strip()
    return any(marker in stripped for marker in ANSWER_HINT_MARKERS)


def _should_merge_following_clause(previous: str, current: str) -> bool:
    prev = previous.strip()
    curr = current.strip()
    if not prev or not curr:
        return False
    if any(marker in curr for marker in ANALOGY_MARKERS):
        return False
    if prev.startswith("因为") and _clause_is_strong_answer(curr):
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
