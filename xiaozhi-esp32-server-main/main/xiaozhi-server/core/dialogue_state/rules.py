import re
from typing import Dict, List, Tuple


DEFAULT_PHASES: Dict[str, str] = {
    "safety_risk": "stabilize_and_direct",
    "emotion_support": "empathize",
    "curiosity": "acknowledge",
    "learning_support": "find_block",
    "play_interaction": "open_round",
    "system_repair": "recognize_mismatch",
    "relationship_building": "warm_opening",
}


REPLY_STYLE_BY_SCENE: Dict[str, str] = {
    "safety_risk": "calm_directive",
    "emotion_support": "gentle_validation",
    "curiosity": "short_child_friendly",
    "learning_support": "coach_step_by_step",
    "play_interaction": "playful_turn_based",
    "system_repair": "clear_repair",
    "relationship_building": "warm_brief",
}


MAX_SENTENCES_BY_SCENE: Dict[str, int] = {
    "safety_risk": 2,
    "emotion_support": 3,
    "curiosity": 3,
    "learning_support": 3,
    "play_interaction": 2,
    "system_repair": 2,
    "relationship_building": 2,
}


PHASE_POLICY_HINTS: Dict[Tuple[str, str], List[str]] = {
    ("safety_risk", "stabilize_and_direct"): [
        "第一句先稳定孩子，不展开危险细节。",
        "第二句只给一个最关键的安全动作。",
    ],
    ("emotion_support", "empathize"): [
        "先接住情绪，不急着讲道理。",
        "可以轻轻复述孩子的感受，但不要像审问。",
    ],
    ("emotion_support", "clarify_event"): [
        "只帮孩子把发生了什么说清楚。",
        "最多问一个轻量澄清问题。",
    ],
    ("emotion_support", "normalize_feeling"): [
        "告诉孩子这种感觉是可以被理解的。",
        "避免把事件上升成对孩子的评价。",
    ],
    ("emotion_support", "small_action"): [
        "只给一个小行动，不要给一串建议。",
    ],
    ("curiosity", "short_answer"): [
        "先一句话说结论。",
        "尽量用孩子熟悉的词，不要百科式长讲。",
    ],
    ("curiosity", "analogy_or_example"): [
        "给一个生活类比或具体例子。",
        "例子要短，方便孩子马上抓住画面。",
    ],
    ("curiosity", "check_understanding"): [
        "只问一个很轻的问题检查理解。",
    ],
    ("curiosity", "optional_followup"): [
        "只回答一轮追问，不要无限展开。",
    ],
    ("learning_support", "find_block"): [
        "先确认孩子卡在哪一步，不直接整题代答。",
    ],
    ("learning_support", "split_step"): [
        "一次只拆一个步骤。",
    ],
    ("learning_support", "child_try"): [
        "鼓励孩子先试一步，再继续。",
    ],
    ("learning_support", "feedback"): [
        "先肯定尝试，再指出下一步。",
    ],
    ("learning_support", "next_step_or_close"): [
        "如果已经完成就收尾，否则只推进下一小步。",
    ],
    ("play_interaction", "open_round"): [
        "快速进入玩法，不要长规则说明。",
    ],
    ("play_interaction", "play_round"): [
        "保持一来一回的短回合。",
    ],
    ("play_interaction", "branch_choice"): [
        "优先给 A/B 选择题。",
    ],
    ("system_repair", "recognize_mismatch"): [
        "承认刚才没有对上，不解释系统原因。",
    ],
    ("system_repair", "offer_choice"): [
        "给 2 个以内的澄清选项，帮助孩子快速重来。",
    ],
    ("system_repair", "re_anchor_topic"): [
        "快速回到孩子真正想聊的事。",
    ],
    ("relationship_building", "warm_opening"): [
        "友好接住，不要抢主导权。",
    ],
    ("relationship_building", "light_followup"): [
        "只问一个很轻的问题邀请继续。",
    ],
}


CLOSE_MARKERS = (
    "懂了",
    "知道了",
    "明白了",
    "好了",
    "可以了",
    "停",
    "先这样",
)

TOPIC_SWITCH_MARKERS = ("换一个", "不聊这个", "下一题", "我们玩别的")
ADVICE_MARKERS = ("怎么办", "怎么做", "那我明天怎么办", "我该怎么办")
EMOTION_CAUSE_MARKERS = ("因为", "刚才", "他们", "同学", "妈妈说", "老师说")
ATTEMPT_MARKERS = ("我试了", "我算出来了", "我写了", "是不是", "答案是")
CHOICE_MARKERS = ("选", "我要", "a", "b", "A", "B")
GREETING_MARKERS = ("你好", "嗨", "在吗", "早上好", "晚上好")
REPAIR_MARKERS = ("你没听懂", "不是这个", "答错了", "你说的不对", "你没回答")
FOLLOWUP_CLARIFY_MARKERS = (
    "是什么",
    "什么意思",
    "是啥",
    "啥意思",
    "怎么理解",
    "这个是什么",
    "这是什么",
    "那是什么",
    "它是什么",
    "这个词是什么意思",
    "这个词是什么",
    "在哪里",
    "在哪",
    "有什么用",
    "干什么的",
    "干嘛的",
    "怎么用",
    "然后呢",
    "那然后呢",
    "接下来呢",
    "会怎样",
    "会怎么样",
    "是不是",
    "能不能",
)


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    return text


def contains_any(text: str, keywords) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(keyword) in normalized for keyword in keywords)


def reply_length_bucket(reply_text: str) -> str:
    length = len((reply_text or "").strip())
    if length <= 20:
        return "short"
    if length <= 80:
        return "medium"
    return "long"
