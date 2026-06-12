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

    if plan.primary_action in {"ask_one_clarify", "offer_choice"}:
        question_sentences = [sentence for sentence in filtered if _looks_like_question(sentence)]
        if question_sentences:
            filtered = question_sentences[:1]
            rewrite_actions.append("keep_single_question")
        else:
            filtered = filtered[:1]
    elif plan.primary_action == "answer_then_invite":
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
    if cleaned and cleaned[0] in "但不过而且所以然后":
        cleaned = cleaned[1:].lstrip(LEADING_PUNCTUATION)
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


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
