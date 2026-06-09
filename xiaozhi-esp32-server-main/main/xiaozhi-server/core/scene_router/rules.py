import re
from typing import Dict, List, Tuple


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    return re.sub(r"\s+", "", text)


SCENE_RULES: Dict[str, Dict[str, object]] = {
    "safety_risk": {
        "risk_level": "high",
        "policy_profile": "safety_directive",
        "subscene_rules": [
            ("self_harm", ["不想活", "想死", "伤害自己", "自杀"]),
            ("harm_others", ["想打人", "想杀", "伤害别人"]),
            ("privacy_touch", ["不要告诉爸爸妈妈", "不能告诉家长", "摸我", "碰我身体", "隐私部位"]),
            ("stranger_danger", ["陌生人", "叔叔带我走", "阿姨带我走"]),
            ("lost_child", ["找不到妈妈", "找不到爸爸", "我走丢了", "迷路了"]),
            ("medical_discomfort", ["流血", "喘不过气", "胸口疼", "肚子特别疼", "头很晕"]),
        ],
        "should_force_safe_template": True,
        "should_use_memory": False,
        "should_use_rag": False,
        "should_use_vlm": False,
        "should_escalate_parent": True,
    },
    "emotion_support": {
        "risk_level": "medium",
        "policy_profile": "empathize_then_act",
        "subscene_rules": [
            ("sadness", ["难过", "伤心", "哭了", "不开心"]),
            ("fear", ["害怕", "我怕", "吓死了", "不敢"]),
            ("anger", ["生气", "气死了", "烦死了"]),
            ("shame", ["丢脸", "羞死了", "好笨", "我很差"]),
            ("school_stress", ["作业好多", "不想上学", "考试很烦"]),
        ],
        "should_force_safe_template": False,
        "should_use_memory": True,
        "should_use_rag": False,
        "should_use_vlm": False,
        "should_escalate_parent": False,
    },
    "curiosity": {
        "risk_level": "low",
        "policy_profile": "ask_then_explain",
        "subscene_rules": [
            ("natural_science", ["为什么", "怎么会", "鱼为什么", "天空为什么", "星星为什么"]),
            ("body_health", ["为什么会发烧", "为什么要刷牙", "身体为什么"]),
            ("social_rules", ["为什么不能", "为什么要排队", "为什么要分享"]),
            ("technology_world", ["机器人为什么", "电脑为什么", "手机为什么"]),
        ],
        "should_force_safe_template": False,
        "should_use_memory": False,
        "should_use_rag": True,
        "should_use_vlm": False,
        "should_escalate_parent": False,
    },
    "learning_support": {
        "risk_level": "low",
        "policy_profile": "coach_step_by_step",
        "subscene_rules": [
            ("math", ["加法", "减法", "乘法", "除法", "数学题", "算一下"]),
            ("english", ["英语", "英文", "单词", "字母"]),
            ("literacy_reading", ["认字", "拼音", "读一下", "这个字怎么读"]),
            ("homework_help", ["作业", "不会做", "帮我做题"]),
        ],
        "should_force_safe_template": False,
        "should_use_memory": True,
        "should_use_rag": False,
        "should_use_vlm": False,
        "should_escalate_parent": False,
    },
    "play_interaction": {
        "risk_level": "low",
        "policy_profile": "play_along",
        "subscene_rules": [
            ("story_game", ["讲故事", "编故事", "还要听", "继续讲"]),
            ("language_game", ["猜谜语", "绕口令", "成语接龙"]),
            ("role_play", ["你演", "我们假装", "扮演"]),
            ("movement_game", ["跳舞", "一起动", "玩个游戏"]),
        ],
        "should_force_safe_template": False,
        "should_use_memory": True,
        "should_use_rag": False,
        "should_use_vlm": False,
        "should_escalate_parent": False,
    },
    "system_repair": {
        "risk_level": "low",
        "policy_profile": "repair_and_recover",
        "subscene_rules": [
            ("repeat_question", ["你再说一遍", "没听清", "什么意思", "再来一次", "没明白", "没听明白"]),
            ("silence_repair", ["...", "嗯", "啊"]),
            ("frustration_repair", ["你怎么回事", "你听不懂", "你没听懂", "你又错了", "你没回答", "答非所问"]),
            ("topic_switch", ["换一个", "不聊这个", "下一题", "换个话题"]),
        ],
        "should_force_safe_template": False,
        "should_use_memory": False,
        "should_use_rag": False,
        "should_use_vlm": False,
        "should_escalate_parent": False,
    },
}


DEFAULT_SCENE = {
    "primary_scene": "relationship_building",
    "subscene": "greeting",
    "risk_level": "low",
    "policy_profile": "warm_and_brief",
    "should_force_safe_template": False,
    "should_use_memory": True,
    "should_use_rag": False,
    "should_use_vlm": False,
    "should_escalate_parent": False,
}


EMOTION_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("sad", ["难过", "伤心", "哭"]),
    ("angry", ["生气", "烦", "气死"]),
    ("scared", ["害怕", "怕", "吓"]),
    ("curious", ["为什么", "怎么", "是什么"]),
    ("frustrated", ["不会", "好难", "听不懂"]),
]
