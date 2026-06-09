# Dialogue State Manager V1 State Table

## 1. 文档目的

这份文档把 `dialogue_state_manager_v1.md` 里的设计，进一步整理成可直接实现的状态表。

用途：

- 给工程实现提供字段定义
- 给策略设计提供统一状态枚举
- 给调试和日志埋点提供标准结构

---

## 2. 总体结构

V1 建议把状态拆成 5 个层：

1. `scene_state`
2. `phase_state`
3. `turn_state`
4. `user_state`
5. `task_state`

推荐最终聚合结构：

```json
{
  "scene_state": {},
  "phase_state": {},
  "turn_state": {},
  "user_state": {},
  "task_state": {}
}
```

---

## 3. Scene State Table

| 字段名 | 类型 | 示例 | 枚举/范围 | 说明 | 更新时机 |
|---|---|---|---|---|---|
| `current_scene` | `string` | `curiosity` | scene 名称 | 当前主 scene | 每轮 scene router 后更新 |
| `current_subscene` | `string` | `natural_science` | subscene 名称 | 当前子 scene | 每轮 scene router 后更新 |
| `previous_scene` | `string/null` | `relationship_building` | scene 名称或空 | 上一轮主 scene | 当轮更新前保留旧值 |
| `previous_subscene` | `string/null` | `greeting` | subscene 名称或空 | 上一轮子 scene | 当轮更新前保留旧值 |
| `scene_turn_count` | `int` | `2` | `>=0` | 当前 scene 已连续持续几轮 | scene 不变时 +1，切换时重置为 1 |
| `subscene_turn_count` | `int` | `1` | `>=0` | 当前 subscene 已持续几轮 | subscene 不变时 +1，切换时重置为 1 |
| `scene_changed` | `bool` | `true` | `true/false` | 本轮是否发生主 scene 切换 | scene 对比后更新 |
| `subscene_changed` | `bool` | `true` | `true/false` | 本轮是否发生子 scene 切换 | subscene 对比后更新 |
| `scene_enter_reason` | `string` | `router_match` | 见下表 | 进入当前 scene 的原因 | scene 确定后更新 |

### `scene_enter_reason` 推荐枚举

| 值 | 含义 |
|---|---|
| `router_match` | 由 scene router 直接命中 |
| `fallback_default` | 未命中任何规则，进入默认 scene |
| `manual_switch` | 由系统规则强制切换 |
| `safety_override` | 被安全层打断并强制切换 |
| `repair_reanchor` | 由 repair 后重新锚定进入 |

---

## 4. Phase State Table

| 字段名 | 类型 | 示例 | 枚举/范围 | 说明 | 更新时机 |
|---|---|---|---|---|---|
| `current_phase` | `string` | `short_answer` | 由当前 scene 决定 | 当前 scene 内部阶段 | 每轮根据状态迁移规则更新 |
| `previous_phase` | `string/null` | `acknowledge` | phase 名称或空 | 上一阶段 | phase 更新前保留旧值 |
| `phase_turn_count` | `int` | `1` | `>=0` | 当前 phase 已持续几轮 | phase 不变时 +1，切换时重置为 1 |
| `phase_changed` | `bool` | `true` | `true/false` | 本轮是否发生 phase 切换 | phase 对比后更新 |
| `phase_completed` | `bool` | `false` | `true/false` | 当前阶段是否已完成 | 在迁移判断中更新 |
| `next_action` | `string` | `give_example_then_check` | 动作枚举 | 下一步应该做什么 | phase 决策后输出 |
| `should_close_scene` | `bool` | `false` | `true/false` | 是否该收尾当前 scene | phase 决策后输出 |
| `should_switch_scene` | `bool` | `false` | `true/false` | 是否该切 scene | phase 决策后输出 |

---

## 5. Turn State Table

| 字段名 | 类型 | 示例 | 枚举/范围 | 说明 | 更新时机 |
|---|---|---|---|---|---|
| `turn_index` | `int` | `14` | `>=0` | 整段会话轮次 | 每轮 +1 |
| `scene_turn_index` | `int` | `2` | `>=0` | 当前 scene 内轮次 | scene 维度下递增 |
| `followup_count` | `int` | `1` | `>=0` | 当前 scene 已追问几轮 | 每次主动追问后 +1 |
| `repair_count` | `int` | `0` | `>=0` | 当前会话修复次数 | 进入 repair 时 +1 |
| `last_bot_action` | `string/null` | `give_short_answer` | 动作枚举 | 上一轮机器人执行的动作 | 回复后写入 |
| `last_user_move` | `string/null` | `ask_why` | 行为枚举 | 上一轮用户的行为类型 | 本轮解析后写入 |
| `last_transition_reason` | `string/null` | `phase_advance` | 见下表 | 上一次状态迁移原因 | phase/scene 迁移时写入 |
| `last_reply_length_bucket` | `string/null` | `short` | `short/medium/long` | 上一轮回复长度档位 | 回复生成后写入 |

### `last_user_move` 推荐枚举

| 值 | 含义 |
|---|---|
| `ask_why` | 提问“为什么/怎么会/是什么” |
| `describe_event` | 描述发生了什么 |
| `ask_help` | 求助“怎么办/帮我/不会做” |
| `express_emotion` | 情绪表达 |
| `say_understood` | 表示懂了 |
| `say_not_understood` | 表示没懂 |
| `topic_switch` | 主动换话题 |
| `complain_mismatch` | 抱怨没听懂/答错 |
| `silent_or_minimal` | 沉默或极短回应 |

### `last_transition_reason` 推荐枚举

| 值 | 含义 |
|---|---|
| `scene_continue` | 继续当前 scene |
| `scene_switch` | 切到新 scene |
| `phase_advance` | 同一 scene 内推进到下一 phase |
| `phase_repeat` | 仍停留在当前 phase |
| `task_completed` | 当前任务完成，准备收尾 |
| `repair_triggered` | 进入 repair |
| `safety_override` | 被安全层中断 |

---

## 6. User State Table

| 字段名 | 类型 | 示例 | 枚举/范围 | 说明 | 更新时机 |
|---|---|---|---|---|---|
| `emotion_state` | `string` | `curious` | 见下表 | 当前主要情绪 | 每轮根据 scene router + 文本线索更新 |
| `emotion_trend` | `string` | `stable_curious` | 见下表 | 最近几轮情绪变化趋势 | 每轮更新 |
| `understanding_state` | `string` | `unknown` | `unknown/seems_understood/not_understood` | 用户是否理解当前内容 | 根据用户反馈更新 |
| `frustration_level` | `int` | `0` | `0-3` | 即时挫败等级 | 每轮更新 |
| `engagement_level` | `int` | `2` | `0-3` | 当前参与度 | 每轮更新 |
| `topic_switch_signal` | `bool` | `false` | `true/false` | 是否有换话题信号 | 每轮更新 |
| `silence_repair_count` | `int` | `0` | `>=0` | 低响应修复次数 | 用户沉默/极短响应时更新 |

### `emotion_state` 推荐枚举

| 值 | 含义 |
|---|---|
| `neutral` | 中性 |
| `curious` | 好奇 |
| `sad` | 难过 |
| `angry` | 生气 |
| `scared` | 害怕 |
| `frustrated` | 挫败 |
| `happy` | 开心 |

### `emotion_trend` 推荐枚举

| 值 | 含义 |
|---|---|
| `stable_neutral` | 持续中性 |
| `stable_curious` | 持续好奇 |
| `warming_up` | 逐步更愿意交流 |
| `cooling_down` | 情绪正在缓和 |
| `escalating_negative` | 负面情绪在升级 |
| `confused_loop` | 困惑在持续 |

---

## 7. Task State Table

| 字段名 | 类型 | 示例 | 枚举/范围 | 说明 | 更新时机 |
|---|---|---|---|---|---|
| `task_type` | `string` | `explain_question` | 见下表 | 当前局部任务类型 | scene 确定后更新 |
| `task_completed` | `bool` | `false` | `true/false` | 当前局部任务是否完成 | 每轮迁移时更新 |
| `completion_signal` | `string/null` | `user_said_understood` | 见下表 | 任务完成的依据 | 完成时写入 |
| `pending_step_count` | `int` | `1` | `>=0` | 剩余待推进步骤估计 | 每轮更新 |
| `recommended_close_style` | `string` | `brief_warm_close` | 风格枚举 | 收尾时应用的风格 | 任务接近完成时更新 |

### `task_type` 推荐枚举

| 值 | 含义 |
|---|---|
| `explain_question` | 解释一个好奇问题 |
| `emotion_soothing` | 安抚情绪 |
| `homework_guidance` | 作业辅导 |
| `play_round` | 完成一个游戏回合 |
| `repair_alignment` | 修复理解偏差 |
| `safety_stabilize` | 安全风险稳定 |

### `completion_signal` 推荐枚举

| 值 | 含义 |
|---|---|
| `user_said_understood` | 用户表示懂了 |
| `user_accepted_action` | 用户接受建议 |
| `child_finished_step` | 孩子完成当前步骤 |
| `user_switched_topic` | 用户自然切话题 |
| `risk_handed_to_adult` | 风险已交由成人接管 |
| `repair_completed` | 已完成修复并重新锚定 |

---

## 8. Scene -> Phase Table

### 8.1 Emotion Support

| Scene | Phase | 进入条件 | 退出条件 | Next Action |
|---|---|---|---|---|
| `emotion_support` | `empathize` | 首次进入情绪支持 | 已完成一次有效共情 | `validate_feeling` |
| `emotion_support` | `clarify_event` | 用户开始说明原因 | 事件信息足够清楚 | `ask_gentle_clarify` |
| `emotion_support` | `normalize_feeling` | 事件已明朗 | 已完成情绪正常化表达 | `normalize_and_support` |
| `emotion_support` | `small_action` | 用户问怎么办/需要行动 | 已给一个小行动建议 | `suggest_one_small_step` |
| `emotion_support` | `close` | 情绪缓和或准备结束 | 当前 scene 收尾完成 | `warm_close` |

### 8.2 Curiosity

| Scene | Phase | 进入条件 | 退出条件 | Next Action |
|---|---|---|---|---|
| `curiosity` | `acknowledge` | 新知识问题进入 | 已接住问题 | `acknowledge_question` |
| `curiosity` | `short_answer` | 已接住问题 | 已给短答案 | `give_short_answer` |
| `curiosity` | `analogy_or_example` | 需要进一步解释 | 已给类比/例子 | `give_example_then_check` |
| `curiosity` | `check_understanding` | 已给解释 | 已确认理解状态 | `check_understanding` |
| `curiosity` | `optional_followup` | 用户继续追问 | 追问轮数达到上限或回答完成 | `answer_followup_once` |
| `curiosity` | `close` | 用户懂了或结束 | 当前 scene 收尾完成 | `brief_close` |

### 8.3 Learning Support

| Scene | Phase | 进入条件 | 退出条件 | Next Action |
|---|---|---|---|---|
| `learning_support` | `find_block` | 用户表示不会 | 已识别卡点 | `find_where_child_stuck` |
| `learning_support` | `split_step` | 已识别卡点 | 已拆出一个步骤 | `give_one_step_hint` |
| `learning_support` | `child_try` | 已给提示 | 用户已尝试 | `invite_child_try` |
| `learning_support` | `feedback` | 用户给出尝试结果 | 已反馈对错和下一步 | `give_feedback` |
| `learning_support` | `next_step_or_close` | 当前步骤完成 | 决定继续下一步或结束 | `advance_or_close` |

### 8.4 System Repair

| Scene | Phase | 进入条件 | 退出条件 | Next Action |
|---|---|---|---|---|
| `system_repair` | `recognize_mismatch` | 用户抱怨没对上 | 已承认错位 | `acknowledge_mismatch` |
| `system_repair` | `offer_choice` | 已承认错位 | 已给出澄清选项 | `offer_repair_choice` |
| `system_repair` | `re_anchor_topic` | 用户给出真实意图 | 已重新锚定 | `re_anchor_and_switch` |
| `system_repair` | `close` | 修复完成 | 准备切回真实 scene | `close_repair` |

---

## 9. Scene -> 默认 Task Type Table

| Scene | 默认 Task Type |
|---|---|
| `safety_risk` | `safety_stabilize` |
| `emotion_support` | `emotion_soothing` |
| `curiosity` | `explain_question` |
| `learning_support` | `homework_guidance` |
| `play_interaction` | `play_round` |
| `system_repair` | `repair_alignment` |
| `relationship_building` | `relationship_open` |

---

## 10. Reply Style Table

| 值 | 说明 | 适用场景 |
|---|---|---|
| `short_child_friendly` | 儿童短句，先结论后例子 | `curiosity` |
| `soft_empathy` | 先共情再轻问 | `emotion_support` |
| `step_by_step_coach` | 每轮只推进一步 | `learning_support` |
| `brief_repair` | 简短修复，不解释系统 | `system_repair` |
| `direct_safe` | 直接行动指令 | `safety_risk` |
| `playful_turn` | 轻快互动，一轮一回合 | `play_interaction` |
| `warm_opening` | 温暖简短关系建立 | `relationship_building` |

---

## 11. Max Reply Sentences Table

| Scene | Phase | 建议句数上限 |
|---|---|---|
| `safety_risk` | 全部 | `2-3` |
| `emotion_support` | `empathize` | `2` |
| `emotion_support` | `small_action` | `3` |
| `curiosity` | `short_answer` | `2-3` |
| `curiosity` | `analogy_or_example` | `3-4` |
| `learning_support` | `split_step` | `2-3` |
| `system_repair` | 全部 | `1-2` |
| `play_interaction` | 单回合 | `1-3` |

---

## 12. Follow-up Policy Table

| Scene | 是否允许追问 | 最大追问轮数 | 说明 |
|---|---|---|---|
| `safety_risk` | 仅必要时 | `1` | 只问安全必要信息 |
| `emotion_support` | 是 | `1-3` | 但不能像审问 |
| `curiosity` | 是 | `1` | 防止考试感 |
| `learning_support` | 是 | `2-4` | 每轮只问一个小问题 |
| `play_interaction` | 是 | 高 | 游戏可多回合 |
| `system_repair` | 是 | `1-2` | 只做澄清用途 |

---

## 13. Scene Switch Table

| 当前 Scene | 触发信号 | 目标 Scene |
|---|---|---|
| `curiosity` | 用户变成“不会做题/帮我做作业” | `learning_support` |
| `curiosity` | 用户转成讲故事/角色扮演 | `play_interaction` |
| `learning_support` | 用户明显挫败/自责/哭 | `emotion_support` |
| `play_interaction` | 游戏中表达难过或害怕 | `emotion_support` |
| 任意 scene | 出现安全风险 | `safety_risk` |
| `system_repair` | 已明确真实意图 | 切回真实目标 scene |

---

## 14. V1 最小落地字段

如果先做 MVP，只保留下面这些也可以运行：

| 类别 | 必做字段 |
|---|---|
| `scene_state` | `current_scene`, `current_subscene`, `scene_turn_count`, `scene_changed` |
| `phase_state` | `current_phase`, `phase_turn_count`, `next_action`, `should_close_scene` |
| `turn_state` | `turn_index`, `followup_count`, `last_bot_action`, `last_user_move` |
| `user_state` | `emotion_state`, `understanding_state`, `frustration_level` |
| `task_state` | `task_type`, `task_completed`, `completion_signal` |

---

## 15. 推荐日志字段

建议每轮日志固定打这些字段：

| 字段 | 说明 |
|---|---|
| `scene` | 当前主 scene |
| `subscene` | 当前子 scene |
| `phase` | 当前 phase |
| `next_action` | 下一动作 |
| `scene_changed` | 是否切 scene |
| `phase_changed` | 是否切 phase |
| `followup_count` | 当前追问数 |
| `task_completed` | 当前任务是否完成 |
| `transition_reason` | 迁移原因 |

---

## 16. 推荐下一步

在这份表之后，最适合继续补的是：

1. `dialogue_state_manager_v1_transition_rules.md`
2. `dialogue_state_manager_v1_runtime_schema.md`
3. 代码 MVP

