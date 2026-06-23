from .rules import DEFAULT_SCENE, EMOTION_KEYWORDS, SCENE_RULES, normalize_text
from .schema import SceneRouterInput, SceneRouterOutput


class SceneRouter:
    def route(self, router_input: SceneRouterInput) -> SceneRouterOutput:
        text = normalize_text(router_input.text)
        age_band = router_input.child_profile.age_band or "6-8"
        emotion_state = self._detect_emotion(text, router_input.signals.emotion_hint)
        current_scene = router_input.dialog_state.current_scene

        for scene_name in ("safety_risk", "emotion_support", "system_repair", "learning_support", "play_interaction", "curiosity"):
            if scene_name == "system_repair" and self._should_skip_repair_for_context_followup(
                text, current_scene
            ):
                continue
            scene_rule = SCENE_RULES[scene_name]
            matched_subscene, reason_codes = self._match_subscene(text, scene_rule["subscene_rules"])
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
