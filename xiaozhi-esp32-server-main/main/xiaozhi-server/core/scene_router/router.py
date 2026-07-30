from .rules import DEFAULT_SCENE, EMOTION_KEYWORDS, SCENE_RULES, normalize_text
from .schema import SceneRouterInput, SceneRouterOutput


class SceneRouter:
    def route(self, router_input: SceneRouterInput) -> SceneRouterOutput:
        text = normalize_text(router_input.text)
        age_band = router_input.child_profile.age_band or "6-8"
        emotion_state = self._detect_emotion(text, router_input.signals.emotion_hint)
        current_scene = router_input.dialog_state.current_scene
        openness_level = int(getattr(router_input.signals, "conversation_openness_level", 3) or 3)
        openness_reason = str(getattr(router_input.signals, "conversation_openness_reason", "neutral_default") or "neutral_default")
        self._current_openness_level = openness_level
        self._current_openness_reason = openness_reason

        for scene_name in ("safety_risk", "emotion_support", "system_repair", "learning_support", "play_interaction", "curiosity"):
            if scene_name == "system_repair" and self._should_skip_repair_for_context_followup(
                text, current_scene
            ):
                continue
            scene_rule = SCENE_RULES[scene_name]
            matched_subscene, reason_codes = self._match_subscene(text, scene_rule["subscene_rules"])
            if not matched_subscene and scene_name == "learning_support":
                matched_subscene, reason_codes = self._match_learning_pattern(text, current_scene)
            if matched_subscene:
                policy_profile = self._resolve_policy_profile(
                    scene_name=scene_name,
                    age_band=age_band,
                    base_policy=scene_rule["policy_profile"],
                )
                return SceneRouterOutput(
                    primary_scene=scene_name,
                    secondary_scene=None,
                    subscene=matched_subscene,
                    risk_level=scene_rule["risk_level"],
                    emotion_state=emotion_state,
                    age_band=age_band,
                    policy_profile=policy_profile,
                    should_use_rag=bool(scene_rule["should_use_rag"]),
                    should_use_memory=bool(scene_rule["should_use_memory"]),
                    should_use_vlm=bool(scene_rule["should_use_vlm"]),
                    should_escalate_parent=bool(scene_rule["should_escalate_parent"]),
                    should_force_safe_template=bool(scene_rule["should_force_safe_template"]),
                    interaction_protocol=self._resolve_interaction_protocol(scene_name),
                    protocol_mode=self._resolve_protocol_mode(scene_name, age_band),
                    conversation_openness_level=openness_level,
                    conversation_openness_reason=openness_reason,
                    confidence=self._resolve_confidence(scene_name, age_band),
                    reason_codes=reason_codes + [f"age_band:{age_band}"],
                )

        context_followup_output = self._match_context_followup(
            text=text,
            age_band=age_band,
            emotion_state=emotion_state,
            router_input=router_input,
        )
        if context_followup_output is not None:
            return context_followup_output

        return SceneRouterOutput(
            primary_scene=DEFAULT_SCENE["primary_scene"],
            secondary_scene=None,
            subscene=DEFAULT_SCENE["subscene"],
            risk_level=DEFAULT_SCENE["risk_level"],
            emotion_state=emotion_state,
            age_band=age_band,
            policy_profile=DEFAULT_SCENE["policy_profile"],
            should_use_rag=DEFAULT_SCENE["should_use_rag"],
            should_use_memory=DEFAULT_SCENE["should_use_memory"],
            should_use_vlm=DEFAULT_SCENE["should_use_vlm"],
            should_escalate_parent=DEFAULT_SCENE["should_escalate_parent"],
            should_force_safe_template=DEFAULT_SCENE["should_force_safe_template"],
            interaction_protocol=self._resolve_interaction_protocol(
                DEFAULT_SCENE["primary_scene"]
            ),
            protocol_mode=self._resolve_protocol_mode(DEFAULT_SCENE["primary_scene"]),
            conversation_openness_level=openness_level,
            conversation_openness_reason=openness_reason,
            confidence=0.55,
            reason_codes=["default_fallback"],
        )

    def _match_subscene(self, text, subscene_rules):
        for subscene, keywords in subscene_rules:
            hits = [kw for kw in keywords if normalize_text(kw) in text]
            if hits:
                return subscene, hits
        return None, []

    def _detect_emotion(self, text, emotion_hint):
        if emotion_hint and emotion_hint != "neutral":
            return emotion_hint
        for emotion, keywords in EMOTION_KEYWORDS:
            if any(normalize_text(kw) in text for kw in keywords):
                return emotion
        return "neutral"

    def _should_skip_repair_for_context_followup(self, text, current_scene):
        if current_scene not in {"curiosity", "learning_support"}:
            return False
        return self._is_context_followup_question(text)

    def _match_context_followup(self, text, age_band, emotion_state, router_input):
        current_scene = router_input.dialog_state.current_scene
        if current_scene == "learning_support" and self._is_learning_continuation(text):
            return self._build_context_scene_output(
                scene_name="learning_support",
                subscene=router_input.dialog_state.current_subscene or "homework_support",
                age_band=age_band,
                emotion_state=emotion_state,
                reason_codes=["learning_context_continuation"],
            )
        if current_scene == "curiosity" and self._is_context_followup_question(text):
            return self._build_context_scene_output(
                scene_name="curiosity",
                subscene=router_input.dialog_state.current_subscene or "natural_science",
                age_band=age_band,
                emotion_state=emotion_state,
                reason_codes=["context_followup"],
            )
        if current_scene == "learning_support" and self._is_context_followup_question(text):
            return self._build_context_scene_output(
                scene_name="learning_support",
                subscene=router_input.dialog_state.current_subscene or "homework_help",
                age_band=age_band,
                emotion_state=emotion_state,
                reason_codes=["context_followup"],
            )
        if self._is_short_memory_followup(text, router_input):
            inferred_scene = self._infer_scene_from_short_memory(router_input)
            current_subscene = router_input.dialog_state.current_subscene
            if inferred_scene == "curiosity":
                inferred_subscene = (
                    current_subscene
                    if current_subscene and current_subscene != "greeting"
                    else "natural_science"
                )
            elif inferred_scene == "learning_support":
                inferred_subscene = (
                    current_subscene
                    if current_subscene and current_subscene != "greeting"
                    else "homework_help"
                )
            else:
                inferred_subscene = current_subscene or "natural_science"
            return self._build_context_scene_output(
                scene_name=inferred_scene,
                subscene=inferred_subscene,
                age_band=age_band,
                emotion_state=emotion_state,
                reason_codes=["short_memory_followup"],
            )
        return None

    def _build_context_scene_output(
        self, scene_name, subscene, age_band, emotion_state, reason_codes
    ):
        scene_rule = SCENE_RULES[scene_name]
        return SceneRouterOutput(
            primary_scene=scene_name,
            secondary_scene=None,
            subscene=subscene,
            risk_level=scene_rule["risk_level"],
            emotion_state=emotion_state,
            age_band=age_band,
            policy_profile=self._resolve_policy_profile(
                scene_name=scene_name,
                age_band=age_band,
                base_policy=scene_rule["policy_profile"],
            ),
            should_use_rag=bool(scene_rule["should_use_rag"]),
            should_use_memory=bool(scene_rule["should_use_memory"]),
            should_use_vlm=bool(scene_rule["should_use_vlm"]),
            should_escalate_parent=bool(scene_rule["should_escalate_parent"]),
            should_force_safe_template=bool(scene_rule["should_force_safe_template"]),
            interaction_protocol=self._resolve_interaction_protocol(scene_name),
            protocol_mode=self._resolve_protocol_mode(scene_name, age_band),
            conversation_openness_level=int(getattr(self, "_current_openness_level", 3) or 3),
            conversation_openness_reason=str(getattr(self, "_current_openness_reason", "neutral_default") or "neutral_default"),
            confidence=self._resolve_confidence(scene_name, age_band, context_followup=True),
            reason_codes=reason_codes + [f"age_band:{age_band}"],
        )

    def _resolve_interaction_protocol(self, scene_name):
        if scene_name in {"curiosity", "learning_support", "emotion_support", "play_interaction"}:
            return "child_explore_v1"
        if scene_name == "safety_risk":
            return "child_safe_v1"
        if scene_name == "system_repair":
            return "repair_reset_v1"
        return "warm_companion_v1"

    def _resolve_protocol_mode(self, scene_name, age_band="6-8"):
        if scene_name == "curiosity":
            if age_band == "3-5":
                return "explain_brief"
            if age_band == "9-11":
                return "explain_then_check"
        if scene_name == "learning_support" and age_band == "3-5":
            return "coach_micro_step"
        return {
            "curiosity": "explain_first",
            "learning_support": "coach_step",
            "emotion_support": "emotion_hold",
            "play_interaction": "playful_round",
            "safety_risk": "safe_direct",
            "system_repair": "repair_reset",
            "relationship_building": "warm_connect",
        }.get(scene_name, "warm_connect")

    def _resolve_policy_profile(self, scene_name, age_band, base_policy):
        if age_band == "3-5":
            if scene_name == "curiosity":
                return "brief_answer_with_example"
            if scene_name == "learning_support":
                return "coach_one_step_gentle"
        if age_band == "9-11":
            if scene_name == "curiosity":
                return "guided_step_check_understanding"
            if scene_name == "learning_support":
                return "coach_step_then_check"
        return base_policy

    def _resolve_confidence(self, scene_name, age_band, context_followup=False):
        confidence = 0.92 if scene_name == "safety_risk" else 0.82
        if context_followup:
            confidence = 0.78
        if age_band == "3-5" and scene_name in {"curiosity", "learning_support"}:
            confidence -= 0.04
        if age_band == "9-11" and scene_name in {"curiosity", "learning_support"}:
            confidence += 0.03
        return confidence

    def _is_context_followup_question(self, text):
        if not text or len(text) > 16:
            return False
        if self._contains_any(
            text,
            (
                "你再说一遍",
                "没听清",
                "再来一次",
                "换一个",
                "不聊这个",
                "下一题",
                "你怎么回事",
                "你听不懂",
                "你又错了",
            ),
        ):
            return False
        followup_markers = (
            "是什么",
            "什么意思",
            "是啥",
            "那是什么",
            "这个是什么",
            "这是什么",
            "它是什么",
            "这个词是什么意思",
            "这个词是什么",
            "啥意思",
            "怎么理解",
            "是什么东西",
            "在哪",
            "在哪里",
            "有什么用",
            "干什么的",
            "干嘛的",
            "怎么用",
            "怎么呼吸",
            "怎么来的",
            "为什么呀",
            "为什么呢",
            "然后呢",
            "那然后呢",
            "接下来呢",
            "会怎样",
            "会怎么样",
            "是不是",
            "能不能",
        )
        if any(marker in text for marker in followup_markers):
            return True
        if any(text.startswith(prefix) for prefix in ("那", "这个", "这", "它")):
            return self._contains_any(
                text,
                ("什么", "怎么", "为什么", "哪", "哪里", "是不是", "能不能"),
            )
        return False

    def _contains_any(self, text, keywords):
        return any(keyword in text for keyword in keywords)

    def _match_learning_pattern(self, text, current_scene):
        if not text:
            return None, []
        if self._looks_like_arithmetic(text):
            return "math", ["arithmetic_pattern"]
        if self._looks_like_counting_task(text):
            return "counting", ["counting_pattern"]
        if self._looks_like_color_task(text):
            return "color", ["color_task_pattern"]
        if self._looks_like_shape_task(text):
            return "shape", ["shape_task_pattern"]
        if self._looks_like_language_practice(text):
            return "language_practice", ["language_practice_pattern"]
        if current_scene == "learning_support" and self._is_learning_continuation(text):
            return "homework_support", ["learning_context_continuation"]
        return None, []

    def _looks_like_arithmetic(self, text):
        if "等于多少" in text or "一共" in text:
            return True
        has_digit = any(ch.isdigit() for ch in text)
        has_operator = any(op in text for op in ("+", "＋", "-", "－", "加", "减"))
        return has_digit and has_operator

    def _looks_like_counting_task(self, text):
        if self._contains_any(text, ("数数", "数一数", "帮我数", "一起数")):
            return True
        countable_emoji = ("🍎", "🍏", "🍐", "🍊", "🍓", "⭐", "🌟", "🐶", "🐱", "🐰", "🚗")
        return sum(text.count(item) for item in countable_emoji) >= 2

    def _looks_like_color_task(self, text):
        if "什么颜色" in text:
            return True
        color_words = ("红色", "蓝色", "黄色", "绿色", "黑色", "白色", "粉色", "紫色", "橙色")
        if "找" in text and any(color in text for color in color_words):
            return True
        return False

    def _looks_like_shape_task(self, text):
        shape_words = ("圆形", "三角形", "正方形", "长方形", "形状")
        if any(shape in text for shape in shape_words):
            return True
        return "像什么" in text and len(text) <= 16

    def _looks_like_language_practice(self, text):
        return self._contains_any(
            text,
            ("造句", "说一句话", "因为……所以", "因为...所以", "用'因为", "用“因为"),
        )

    def _is_learning_continuation(self, text):
        if not text or len(text) > 24:
            return False
        return self._contains_any(
            text,
            (
                "我不会",
                "不会",
                "还是不会",
                "太难了",
                "好难",
                "直接告诉我",
                "告诉我答案",
                "答案",
                "再讲一次",
                "再说一次",
                "慢一点",
                "一步一步",
                "不想写",
                "不想做",
                "答对了吗",
                "学会了吗",
            ),
        )

    def _is_short_memory_followup(self, text, router_input):
        active_topic = (router_input.dialog_state.active_topic or "").strip()
        active_entities = list(router_input.dialog_state.active_entities or [])
        if not active_topic and not active_entities:
            return False
        if len(text) > 40:
            return False
        followup_markers = ("那", "它", "这个", "这次", "回来", "刚从", "哪里不一样", "为什么", "怎么")
        if any(marker in text for marker in followup_markers):
            return True
        overlap_hits = [entity for entity in active_entities if entity and entity in text]
        return len(overlap_hits) >= 1

    def _infer_scene_from_short_memory(self, router_input):
        current_scene = router_input.dialog_state.current_scene
        if current_scene in {"curiosity", "learning_support", "emotion_support", "play_interaction"}:
            return current_scene
        active_topic = router_input.dialog_state.active_topic or ""
        active_entities = router_input.dialog_state.active_entities or []
        merged = f"{active_topic} {' '.join(active_entities)}"
        if any(keyword in merged for keyword in ("作业", "数学", "英语", "拼音", "题")):
            return "learning_support"
        return "curiosity"
