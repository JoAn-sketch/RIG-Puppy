from .rules import DEFAULT_SCENE, EMOTION_KEYWORDS, SCENE_RULES, normalize_text
from .schema import SceneRouterInput, SceneRouterOutput


class SceneRouter:
    def route(self, router_input: SceneRouterInput) -> SceneRouterOutput:
        text = normalize_text(router_input.text)
        age_band = router_input.child_profile.age_band or "6-8"
        emotion_state = self._detect_emotion(text, router_input.signals.emotion_hint)

        for scene_name in ("safety_risk", "emotion_support", "system_repair", "learning_support", "play_interaction", "curiosity"):
            scene_rule = SCENE_RULES[scene_name]
            matched_subscene, reason_codes = self._match_subscene(text, scene_rule["subscene_rules"])
            if matched_subscene:
                return SceneRouterOutput(
                    primary_scene=scene_name,
                    secondary_scene=None,
                    subscene=matched_subscene,
                    risk_level=scene_rule["risk_level"],
                    emotion_state=emotion_state,
                    age_band=age_band,
                    policy_profile=scene_rule["policy_profile"],
                    should_use_rag=bool(scene_rule["should_use_rag"]),
                    should_use_memory=bool(scene_rule["should_use_memory"]),
                    should_use_vlm=bool(scene_rule["should_use_vlm"]),
                    should_escalate_parent=bool(scene_rule["should_escalate_parent"]),
                    should_force_safe_template=bool(scene_rule["should_force_safe_template"]),
                    confidence=0.92 if scene_name == "safety_risk" else 0.82,
                    reason_codes=reason_codes,
                )

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

