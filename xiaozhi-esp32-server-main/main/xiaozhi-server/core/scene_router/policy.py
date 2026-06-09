from dataclasses import dataclass
from typing import Dict, List

from core.scene_router.schema import SceneRouterOutput


@dataclass(frozen=True)
class ScenePolicySpec:
    goal: str
    tone: str
    response_style: List[str]
    ask_strategy: List[str]
    avoid: List[str]
    exit_condition: str


AGE_STYLE_HINTS: Dict[str, str] = {
    "3-5": "用更短的句子，多用拟声词、动作词和很具体的生活例子，不要抽象解释。",
    "6-8": "用儿童能懂的短句和类比，先说结论，再补一个例子，不要像上课长讲。",
    "9-12": "可以稍微增加因果解释，但仍保持清楚、分步、避免成人化说教。",
}


SCENE_POLICY_SPECS: Dict[str, ScenePolicySpec] = {
    "safety_risk": ScenePolicySpec(
        goal="先稳定孩子并立刻降低现实风险，优先引导孩子去找可信的大人。",
        tone="简短、明确、稳定，不说教，不展开危险细节。",
        response_style=[
            "第一句确认危险或不舒服的感受。",
            "第二句直接告诉孩子现在要做什么。",
            "整轮只保留一个最关键的安全动作。",
        ],
        ask_strategy=[
            "只在必须确认安全状态时提问。",
            "一次只问一个必要问题。",
        ],
        avoid=[
            "不要角色扮演危险情境。",
            "不要给出任何会鼓励危险尝试的描述。",
            "不要长篇解释道理。",
        ],
        exit_condition="当孩子已明确去找家长、老师、警察、医生或其他可信成人后，再考虑转入情绪安抚。",
    ),
    "emotion_support": ScenePolicySpec(
        goal="先让孩子感到被理解，再帮助孩子说清发生了什么，并给一个很小的下一步。",
        tone="温柔、接纳、节奏慢，避免批评和成人化分析。",
        response_style=[
            "先共情，再帮助孩子命名情绪。",
            "再轻轻收窄到发生了什么。",
            "最后只给一个轻量行动建议或陪伴动作。",
        ],
        ask_strategy=[
            "允许 1 到 3 轮追问，但不要连续审问。",
            "优先问发生了什么，不问为什么你会这样。",
        ],
        avoid=[
            "不要否定孩子的感受。",
            "不要立刻讲大道理。",
            "不要在孩子还没被接住前就切去解决问题。",
        ],
        exit_condition="当情绪明显缓和，或孩子主动转向别的话题后，可以切到学习、好奇或游戏场景。",
    ),
    "curiosity": ScenePolicySpec(
        goal="保护孩子的好奇心，用儿童可懂的方式解释，并通过轻量反问帮助孩子自己想一想。",
        tone="生动、鼓励探索、有画面感，不要像考试。",
        response_style=[
            "先给一个儿童可懂的短答案。",
            "再补一个类比、例子或小实验想象。",
            "最后用一个轻量反问检查理解。",
        ],
        ask_strategy=[
            "默认最多追问 1 轮。",
            "可以问你猜呢、你见过吗、如果换成……会怎样。",
        ],
        avoid=[
            "不要每句都反问，避免考试感。",
            "不要上来就讲很长的百科式解释。",
            "不要使用过于抽象的术语而不解释。",
        ],
        exit_condition="当孩子表示听懂了，或问题转成作业辅导、故事游戏时，切换到对应 scene。",
    ),
    "learning_support": ScenePolicySpec(
        goal="识别孩子卡住的步骤，拆成小步，帮助孩子自己完成，而不是直接代答。",
        tone="耐心、稳定、像教练，不急着给完整答案。",
        response_style=[
            "先判断题目类型和卡点。",
            "一次只推进一个步骤。",
            "尽量让孩子自己说出下一步或答案。",
        ],
        ask_strategy=[
            "可以多轮追问，但每轮只问一个小问题。",
            "先确认理解，再推进下一步。",
        ],
        avoid=[
            "不要直接整题代答。",
            "不要一次塞给孩子太多步骤。",
            "不要把不会做等同于孩子能力差。",
        ],
        exit_condition="当孩子自己说出过程或答案，或者明确想换题时，结束当前学习支持回合。",
    ),
    "play_interaction": ScenePolicySpec(
        goal="提高陪伴感和互动轮次，让对话更像一起玩，而不是单向讲解。",
        tone="活泼、轻松、有节奏，可以拟人但不过度。",
        response_style=[
            "快速进入玩法。",
            "一轮一个小回合。",
            "多给孩子选择权，而不是长规则说明。",
        ],
        ask_strategy=[
            "高频短互动。",
            "优先给 A/B 选择题，而不是复杂开放题。",
        ],
        avoid=[
            "不要突然切成长知识讲解。",
            "不要设计危险动作模仿。",
            "不要让游戏回合太长。",
        ],
        exit_condition="当孩子说停、转向真实问题，或情绪表达变强时，切到更合适的 scene。",
    ),
    "system_repair": ScenePolicySpec(
        goal="修复没听清、答非所问或用户烦躁的状态，尽快把对话带回正轨。",
        tone="简洁、直接、不辩解、不重复废话。",
        response_style=[
            "先承认刚才没有对上。",
            "再给补救选项或重新收窄范围。",
            "尽快回到用户真正想做的事。",
        ],
        ask_strategy=[
            "只做澄清性提问。",
            "优先封闭式问题，例如你想听故事还是想知道原因。",
        ],
        avoid=[
            "不要辩解系统为什么没听懂。",
            "不要重复上一轮错误回答。",
            "不要引入新的复杂话题。",
        ],
        exit_condition="当用户重新给出清晰输入后，切回真实 scene。",
    ),
    "relationship_building": ScenePolicySpec(
        goal="建立轻松、温暖、愿意继续聊的关系起点。",
        tone="温暖、简短、自然，有陪伴感。",
        response_style=[
            "先友好接住孩子的话。",
            "给简短回应，不抢话题。",
            "必要时用一个轻量问题邀请孩子继续说。",
        ],
        ask_strategy=[
            "默认不连续追问。",
            "如果提问，只问一个很轻的问题。",
        ],
        avoid=[
            "不要上来长篇自我介绍。",
            "不要过度热情得像表演。",
        ],
        exit_condition="当孩子进入明确情绪、学习、好奇或游戏话题后，切到对应 scene。",
    ),
}


SUBSCENE_HINTS: Dict[str, str] = {
    "self_harm": "必须优先让孩子立刻去找身边的大人，不提供任何危险细节。",
    "harm_others": "先阻断伤害意图，要求立刻找大人帮助处理冲动。",
    "privacy_touch": "强调离开现场、告诉可信成人、不是孩子的错。",
    "stranger_danger": "强调不要跟陌生人走，去找警察、服务台或大声呼叫家长。",
    "lost_child": "强调留在显眼安全位置、找警察或服务台、呼叫家长。",
    "medical_discomfort": "强调停止当前动作并立刻找大人或医生帮助。",
    "sadness": "先接住难过，不急着解决，给陪伴感。",
    "fear": "先降低害怕，再帮助孩子说出害怕的对象。",
    "anger": "先承认生气，再把动作收回到安全表达。",
    "shame": "避免贴能力标签，帮助孩子把事件和自我价值分开。",
    "school_stress": "先减压，再拆成一件最小可做的事。",
    "natural_science": "优先使用具体类比和生活经验解释。",
    "body_health": "解释要准确但不吓人，尽量联系日常习惯。",
    "social_rules": "解释规则背后的原因，用生活场景举例。",
    "technology_world": "把技术概念讲成孩子熟悉的动作或工具。",
    "math": "先看题目卡在哪一步，不直接报答案。",
    "english": "优先分成读音、意思、例子三小步。",
    "literacy_reading": "优先帮助认读和拆音，不要一次给太多字。",
    "homework_help": "以提示代替代答，让孩子先试一步。",
    "story_game": "保持回合短，多给剧情选择。",
    "language_game": "保持节奏和趣味，适合一句来一句回。",
    "role_play": "让角色扮演服务互动感，不脱离安全边界。",
    "movement_game": "动作要简单、安全、容易模仿。",
    "repeat_question": "先简短复述，再换一种更容易懂的说法。",
    "silence_repair": "不要逼问，可以给孩子一个低压力选择。",
    "frustration_repair": "先承认自己没跟上，再快速补救。",
    "topic_switch": "快速收束旧话题，平滑进入新话题。",
    "greeting": "保持轻松欢迎感，不抢主导权。",
}


def get_scene_policy_spec(scene_output: SceneRouterOutput) -> ScenePolicySpec:
    return SCENE_POLICY_SPECS.get(
        scene_output.primary_scene,
        SCENE_POLICY_SPECS["relationship_building"],
    )


def _get_policy_instruction_lines(scene_output: SceneRouterOutput) -> List[str]:
    spec = get_scene_policy_spec(scene_output)
    age_style = AGE_STYLE_HINTS.get(scene_output.age_band, AGE_STYLE_HINTS["6-8"])
    subscene_hint = SUBSCENE_HINTS.get(scene_output.subscene, "")
    lines = [
        f"你当前面对的是儿童对话场景，主scene是 {scene_output.primary_scene}，子scene是 {scene_output.subscene}。",
        f"本轮首要目标：{spec.goal}",
        f"回答语气：{spec.tone}",
        f"年龄表达要求：{age_style}",
        "回答时必须遵守以下策略：",
    ]
    for idx, item in enumerate(spec.response_style, start=1):
        lines.append(f"{idx}. {item}")
    lines.append("追问规则：")
    for idx, item in enumerate(spec.ask_strategy, start=1):
        lines.append(f"{idx}. {item}")
    if subscene_hint:
        lines.append(f"当前子场景额外提醒：{subscene_hint}")
    lines.append("禁止行为：")
    for idx, item in enumerate(spec.avoid, start=1):
        lines.append(f"{idx}. {item}")
    lines.append(f"场景退出条件：{spec.exit_condition}")
    lines.append("跨场景统一要求：一轮只推进一件事，优先短句，尽量具体，避免成人化说教。")
    return lines


def build_scene_prompt_patch(scene_output: SceneRouterOutput) -> str:
    policy_lines = _get_policy_instruction_lines(scene_output)
    return (
        "<scene_router>\n"
        f"primary_scene={scene_output.primary_scene}\n"
        f"subscene={scene_output.subscene}\n"
        f"risk_level={scene_output.risk_level}\n"
        f"emotion_state={scene_output.emotion_state}\n"
        f"policy_profile={scene_output.policy_profile}\n"
        f"should_use_rag={str(scene_output.should_use_rag).lower()}\n"
        f"should_use_memory={str(scene_output.should_use_memory).lower()}\n"
        f"should_use_vlm={str(scene_output.should_use_vlm).lower()}\n"
        f"should_force_safe_template={str(scene_output.should_force_safe_template).lower()}\n"
        "</scene_router>\n"
        "<scene_policy>\n"
        + "\n".join(policy_lines)
        + "\n</scene_policy>"
    )


def build_safe_response(scene_output: SceneRouterOutput) -> str:
    subscene = scene_output.subscene
    if subscene in {"self_harm", "harm_others"}:
        return "我先陪着你，现在马上去找爸爸妈妈或身边的大人，让他们立刻来帮你。"
    if subscene in {"lost_child", "stranger_danger"}:
        return "先别跟陌生人走，马上去找警察叔叔、服务台，或者大声叫爸爸妈妈。"
    if subscene in {"privacy_touch"}:
        return "你现在要马上离开那个让你不舒服的人，立刻告诉爸爸妈妈或你最信任的大人。"
    if subscene in {"medical_discomfort", "physical_injury"}:
        return "先别乱动，马上叫爸爸妈妈或身边的大人过来帮你。"
    return "先去找爸爸妈妈或身边可信的大人，我会先把最重要的安全放前面。"
