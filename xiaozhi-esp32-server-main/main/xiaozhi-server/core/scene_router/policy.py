from core.scene_router.schema import SceneRouterOutput


def build_scene_prompt_patch(scene_output: SceneRouterOutput) -> str:
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
        "</scene_router>"
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
