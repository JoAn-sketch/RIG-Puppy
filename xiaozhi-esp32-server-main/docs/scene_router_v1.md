# 儿童 Companion Robot Scene Router v1

## 1. 目标

基于现有对话场景树，把每一轮儿童输入路由成一组稳定、可执行的控制标签，供后续 `dialog manager`、`policy engine`、`LLM`、`safety engine` 使用。

Router 不直接决定具体回复文本，只决定：

- 这轮属于什么主场景
- 子场景是什么
- 风险等级多高
- 是否需要先共情、先修复、先给安全指令
- 是否应该调用 `RAG` / `memory` / `VLM`
- 是否需要转交家长

## 2. 设计原则

1. 不直接把 XMind 每个叶子节点当分类标签。
2. 采用 `L1 主场景 + L2 子场景 + 控制标签`。
3. 允许 `primary_scene + secondary_scene`，但任何时刻只能有一个主路由。
4. 高风险优先级永远高于普通陪伴。
5. 强情绪优先级高于知识回答和任务推进。
6. Router 输出应该可用于规则和模型混合实现。

## 3. 输入

建议 Router 输入结构：

```json
{
  "text": "鱼为什么能在水里呼吸",
  "asr_confidence": 0.95,
  "child_profile": {
    "age_band": "6-8"
  },
  "dialog_state": {
    "current_scene": "curiosity",
    "turn_index": 4,
    "question_count_in_current_topic": 1,
    "last_policy": "ask_then_explain"
  },
  "signals": {
    "emotion_hint": "neutral",
    "interruption": false,
    "silence_ms": 0,
    "vlm_tags": []
  }
}
```

## 4. 输出 Schema

```json
{
  "primary_scene": "curiosity",
  "secondary_scene": null,
  "subscene": "natural_science",
  "risk_level": "low",
  "emotion_state": "neutral",
  "age_band": "6-8",
  "policy_profile": "ask_then_explain",
  "should_use_rag": true,
  "should_use_memory": false,
  "should_use_vlm": false,
  "should_escalate_parent": false,
  "should_force_safe_template": false,
  "confidence": 0.94,
  "reason_codes": ["fact_question", "why_question", "science_keyword"]
}
```

字段说明：

- `primary_scene`: 当前主路由
- `secondary_scene`: 混合场景下的辅助标签
- `subscene`: 二级标签
- `risk_level`: `low | medium | high | critical`
- `emotion_state`: `neutral | happy | curious | frustrated | sad | angry | scared | ashamed`
- `policy_profile`: 给策略层的执行建议
- `should_use_rag`: 是否需要事实检索
- `should_use_memory`: 是否读取长期偏好/关系记忆
- `should_use_vlm`: 是否需要视觉确认
- `should_escalate_parent`: 是否建议转家长
- `should_force_safe_template`: 是否禁止自由生成
- `reason_codes`: 方便离线分析和调试

## 5. L1 主场景标签

### 5.1 `relationship_building`

用于建立关系和轻社交。

L2：

- `greeting`
- `self_intro`
- `memory_share`
- `trust_check`

默认策略：`warm_and_brief`

### 5.2 `curiosity`

用于“为什么/怎么会”这类世界解释问题。

L2：

- `natural_science`
- `body_health`
- `social_rules`
- `technology_world`

默认策略：`ask_then_explain`

### 5.3 `daily_routine`

用于日常流程、生活提醒和切换。

L2：

- `wakeup`
- `hygiene_meal`
- `transition`
- `bedtime`
- `family_help`

默认策略：`guide_small_step`

### 5.4 `learning_support`

用于学业和认知辅导。

L2：

- `literacy_reading`
- `english`
- `math`
- `science_learning`
- `homework_help`

默认策略：`coach_step_by_step`

### 5.5 `play_interaction`

用于游戏和一起玩。

L2：

- `language_game`
- `role_play`
- `movement_game`
- `story_game`

默认策略：`play_along`

### 5.6 `creative_expression`

用于创作、故事、画画、音乐等表达场景。

L2：

- `story_creation`
- `drawing_idea`
- `music_rhythm`
- `character_creation`

默认策略：`co_create`

### 5.7 `emotion_support`

用于情绪识别、安抚和陪伴。

L2：

- `anger`
- `fear`
- `sadness`
- `shame`
- `separation_anxiety`
- `school_stress`

默认策略：`empathize_then_act`

### 5.8 `social_growth`

用于同伴冲突、表达需求、修复关系。

L2：

- `peer_conflict`
- `assert_need`
- `repair_relationship`
- `help_seek`

默认策略：`coach_social_script`

### 5.9 `self_cognition`

用于能力感、自我评价、成长想象。

L2：

- `competence_doubt`
- `difference_awareness`
- `future_self`
- `self_worth`

默认策略：`reframe_and_support`

### 5.10 `boundary_rules`

用于规则解释和行为边界。

L2：

- `family_rules`
- `behavior_boundary`
- `screen_time`
- `routine_rule`

默认策略：`set_boundary_with_reason`

### 5.11 `safety_risk`

用于一切需要明确安全指令、限制自由生成、可能升级家长的场景。

L2：

- `physical_injury`
- `medical_discomfort`
- `stranger_danger`
- `lost_child`
- `privacy_touch`
- `bullying_threat`
- `secret_from_parent`
- `self_harm`
- `harm_others`
- `death_crisis`

默认策略：`safety_directive`

### 5.12 `system_repair`

用于交互失败、听不清、沉默、重复问、打断修复。

L2：

- `asr_repair`
- `silence_repair`
- `repeat_question`
- `frustration_repair`
- `topic_switch`

默认策略：`repair_and_recover`

### 5.13 `parent_bridge`

用于家长侧请求和家长接管。

L2：

- `parent_takeover`
- `parent_summary`
- `parent_config`
- `parent_safety_feedback`

默认策略：`handoff_to_parent`

## 6. 控制标签

这些标签不等于主场景，但会影响策略：

- `risk_level`
- `emotion_state`
- `age_band`
- `needs_direct_answer`
- `max_questions_before_answer`
- `allow_free_generation`
- `requires_parent_visibility`

推荐默认值：

```json
{
  "curiosity": {
    "needs_direct_answer": true,
    "max_questions_before_answer": 2,
    "allow_free_generation": true
  },
  "emotion_support": {
    "needs_direct_answer": false,
    "max_questions_before_answer": 1,
    "allow_free_generation": true
  },
  "safety_risk": {
    "needs_direct_answer": true,
    "max_questions_before_answer": 0,
    "allow_free_generation": false
  }
}
```

## 7. 优先级规则

Router 建议按下面顺序判定：

1. `safety_risk`
2. `system_repair`
3. `parent_bridge`
4. `emotion_support`
5. `active_scene_continuation`
6. 其他语义分类

### 7.1 安全优先

以下表达直接优先进入 `safety_risk`：

- “有人让我别告诉妈妈”
- “我找不到妈妈了”
- “有人打我”
- “我流血了”
- “我不想活了”
- “我想伤害他”

动作：

- `should_force_safe_template = true`
- `should_escalate_parent = true`
- `should_use_rag = false`

### 7.2 修复优先

满足以下情况优先进入 `system_repair`：

- `asr_confidence < 0.65`
- 孩子沉默超过阈值
- 连续两轮“我听不懂/不是这个”
- 机器人被中途打断且上下文丢失

### 7.3 情绪压过任务

如果输入同时包含任务和强负面自我评价：

- “我不会写这个，我好笨”
- “我不要做作业了，我想哭”

则：

- `primary_scene = emotion_support`
- `secondary_scene = learning_support`
- `subscene` 优先保留情绪或自我认知标签，例如 `sadness`、`shame`、`competence_doubt`

### 7.4 延续当前场景

如果当前已在一个稳定场景中，且新输入是短续接：

- “然后呢？”
- “不是这个意思”
- “我猜是鳃”

优先沿用 `dialog_state.current_scene`。

## 8. Policy Profile 定义

### 8.1 `ask_then_explain`

用于 `curiosity`

- 先肯定问题
- 最多追问 1 到 2 轮
- 必须收口给答案
- 可附带 1 个延伸问题

### 8.2 `coach_step_by_step`

用于 `learning_support`

- 先拆解任务
- 一次只给一小步
- 不直接把完整答案全部交出
- 孩子明显挫败时切 `emotion_support`

### 8.3 `empathize_then_act`

用于 `emotion_support`

- 先共情
- 帮孩子命名情绪
- 给一个能立刻做的小动作
- 不要长篇说教

### 8.4 `set_boundary_with_reason`

用于 `boundary_rules`

- 明确边界
- 给原因
- 给替代选择

### 8.5 `safety_directive`

用于 `safety_risk`

- 不走开放式苏格拉底互动
- 明确告诉孩子先做什么
- 尽快联系可信成人
- 必要时直接结束普通话题

### 8.6 `repair_and_recover`

用于 `system_repair`

- 先承认没听清或没理解
- 换更简单的话
- 给按钮式或二选一式提问
- 恢复后切回原场景

## 9. 工具调用建议

### `should_use_rag = true`

适合：

- `curiosity`
- `learning_support`
- 少量 `boundary_rules`

不适合：

- `emotion_support`
- `play_interaction`
- `safety_risk`

### `should_use_memory = true`

适合：

- `relationship_building`
- `daily_routine`
- `play_interaction`
- `creative_expression`

注意：

- 不长期记忆高敏感内容
- 不默认记忆所有负面情绪表达

### `should_use_vlm = true`

适合：

- “我这个拼图怎么拼”
- “我写的对吗”
- “这里流血了吗”
- “这个玩具怎么装”

## 10. MVP 规则版实现建议

先不要一上来训练复杂分类器。可以先做：

1. `安全规则匹配`
2. `系统修复规则`
3. `LLM/小分类器做 L1 场景判断`
4. `LLM/小分类器做 L2 子场景判断`
5. `规则修正 policy profile`

推荐初版混合实现：

```text
规则命中 safety/system -> 直接输出
否则 -> 场景分类模型
再 -> 子场景分类模型
再 -> 规则修正 secondary_scene / risk / policy
```

## 11. 训练标签建议

每条训练数据至少打这些字段：

```json
{
  "text": "朋友不跟我玩",
  "primary_scene": "emotion_support",
  "secondary_scene": "social_growth",
  "subscene": "sadness",
  "risk_level": "low",
  "emotion_state": "sad",
  "policy_profile": "empathize_then_act",
  "should_use_rag": false,
  "should_use_memory": true,
  "should_escalate_parent": false
}
```

## 12. 第一版上线建议

先覆盖这 6 个主场景就够：

- `curiosity`
- `emotion_support`
- `daily_routine`
- `play_interaction`
- `learning_support`
- `safety_risk`

其他场景可先并到这 6 类中：

- `social_growth` 并入 `emotion_support`
- `self_cognition` 并入 `emotion_support`
- `boundary_rules` 并入 `daily_routine`
- `creative_expression` 并入 `play_interaction`

这是为了先把线上标签体系做稳，再逐步拆细。
