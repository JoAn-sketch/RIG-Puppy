# Dialogue State Manager V1 Transition Rules

## 1. 目标

这份文档定义 `dialogue state manager` 的状态迁移规则。

关注点不是字段结构本身，而是：

- 什么时候切 `scene`
- 什么时候切 `phase`
- 什么时候继续当前阶段
- 什么时候收尾
- 什么时候被安全层打断

---

## 2. 迁移优先级

V1 建议所有状态迁移都按固定优先级执行：

1. `safety override`
2. `explicit topic switch`
3. `scene switch`
4. `phase advance`
5. `phase repeat`
6. `close scene`

即：

- 先看是否有安全风险
- 再看用户是否明确换话题
- 再看 scene router 是否应该切 scene
- 再决定 scene 内 phase 是否推进

---

## 3. 输入信号

每轮迁移规则建议读取这些输入：

### 3.1 Router Signals

- `primary_scene`
- `subscene`
- `risk_level`
- `confidence`

### 3.2 User Text Signals

- 是否包含继续描述
- 是否包含“怎么办”
- 是否包含“我懂了/知道了”
- 是否包含“我还是不懂”
- 是否包含“换一个/不聊这个”
- 是否包含抱怨系统没听懂

### 3.3 Runtime Signals

- `scene_turn_count`
- `phase_turn_count`
- `followup_count`
- `last_bot_action`
- `repair_count`

### 3.4 Safety Signals

- `should_force_safe_template`
- `should_escalate_parent`

---

## 4. 全局迁移规则

### Rule G1: Safety Override

**条件**

- `scene_output.primary_scene == safety_risk`
- 或安全层检测出高风险

**动作**

- `current_scene = safety_risk`
- `current_phase = stabilize_and_direct`
- `should_switch_scene = true`
- `should_close_scene = false`
- `next_action = direct_safe_response`
- `last_transition_reason = safety_override`

**说明**

- 这是最高优先级
- 直接打断普通状态机

---

### Rule G2: Explicit Topic Switch

**条件**

- 用户文本明确包含：
  - “换一个”
  - “不聊这个”
  - “下一题”
  - “我们玩别的”

**动作**

- 允许切 scene
- `scene_enter_reason = manual_switch`
- `last_transition_reason = scene_switch`

**说明**

- 用户显式换话题优先于 phase 继续

---

### Rule G3: Scene Continue

**条件**

- 本轮 `scene_output.primary_scene == state.scene_state.current_scene`

**动作**

- `scene_changed = false`
- `scene_turn_count += 1`
- `last_transition_reason = scene_continue`

---

### Rule G4: Scene Switch

**条件**

- 本轮 `scene_output.primary_scene != state.scene_state.current_scene`

**动作**

- 更新 `previous_scene`
- 重置 `scene_turn_count = 1`
- 重置 `followup_count = 0`
- 重置 `phase_turn_count = 1`
- 根据新 scene 进入默认 phase
- `scene_changed = true`
- `last_transition_reason = scene_switch`

---

### Rule G5: Close Scene

**条件**

满足任一：

- `task_completed == true`
- 用户表示“懂了/好了/可以了”
- 当前 phase 已到 `close`
- 用户自然切到下一个新主题

**动作**

- `should_close_scene = true`
- `next_action = close_current_scene`

---

## 5. Scene 默认进入 Phase

| Scene | 默认进入 Phase |
|---|---|
| `safety_risk` | `stabilize_and_direct` |
| `emotion_support` | `empathize` |
| `curiosity` | `acknowledge` |
| `learning_support` | `find_block` |
| `play_interaction` | `open_round` |
| `system_repair` | `recognize_mismatch` |
| `relationship_building` | `warm_opening` |

---

## 6. Emotion Support 迁移规则

### Phase 列表

- `empathize`
- `clarify_event`
- `normalize_feeling`
- `small_action`
- `close`

### Rule E1: Enter Empathize

**条件**

- 新进入 `emotion_support`

**动作**

- `current_phase = empathize`
- `next_action = validate_feeling`

---

### Rule E2: Empathize -> Clarify Event

**条件**

满足任一：

- 已完成一轮共情
- 用户继续补充原因
- 用户文本中出现“因为/刚才/他们/同学/妈妈说”

**动作**

- `current_phase = clarify_event`
- `next_action = ask_gentle_clarify`
- `phase_changed = true`
- `last_transition_reason = phase_advance`

---

### Rule E3: Clarify Event -> Normalize Feeling

**条件**

- 当前事件信息足够清楚
- 或连续澄清达到 2 轮

**动作**

- `current_phase = normalize_feeling`
- `next_action = normalize_and_support`

---

### Rule E4: Normalize Feeling -> Small Action

**条件**

满足任一：

- 用户问“怎么办”
- 用户问“那我明天怎么办”
- 用户显式求建议

**动作**

- `current_phase = small_action`
- `next_action = suggest_one_small_step`

---

### Rule E5: Small Action -> Close

**条件**

- 已给出一个小行动建议
- 用户接受建议
- 情绪明显缓和

**动作**

- `current_phase = close`
- `task_completed = true`
- `completion_signal = user_accepted_action`

---

## 7. Curiosity 迁移规则

### Phase 列表

- `acknowledge`
- `short_answer`
- `analogy_or_example`
- `check_understanding`
- `optional_followup`
- `close`

### Rule C1: Enter Acknowledge

**条件**

- 新进入 `curiosity`

**动作**

- `current_phase = acknowledge`
- `next_action = acknowledge_question`

---

### Rule C2: Acknowledge -> Short Answer

**条件**

- 已接住问题

**动作**

- `current_phase = short_answer`
- `next_action = give_short_answer`

---

### Rule C3: Short Answer -> Analogy Or Example

**条件**

满足任一：

- 问题本身需要解释因果
- 当前 subscene 为 `natural_science/body_health/social_rules/technology_world`
- 用户没有立刻表示懂了

**动作**

- `current_phase = analogy_or_example`
- `next_action = give_example_then_check`

---

### Rule C4: Analogy Or Example -> Check Understanding

**条件**

- 已完成一个类比或例子

**动作**

- `current_phase = check_understanding`
- `next_action = check_understanding`

---

### Rule C5: Check Understanding -> Optional Followup

**条件**

- 用户继续追问
- `followup_count < 1`

**动作**

- `current_phase = optional_followup`
- `followup_count += 1`
- `next_action = answer_followup_once`

---

### Rule C6: Any Curiosity Phase -> Close

**条件**

满足任一：

- 用户说“懂了”
- 用户说“知道了”
- 用户切换到新问题
- 当前 follow-up 已达上限并完成回答

**动作**

- `current_phase = close`
- `task_completed = true`

---

## 8. Learning Support 迁移规则

### Phase 列表

- `find_block`
- `split_step`
- `child_try`
- `feedback`
- `next_step_or_close`

### Rule L1: Enter Find Block

**条件**

- 新进入 `learning_support`

**动作**

- `current_phase = find_block`
- `next_action = find_where_child_stuck`

---

### Rule L2: Find Block -> Split Step

**条件**

- 已识别题目类型
- 已识别卡点
- 或用户明确说出“我卡在这里”

**动作**

- `current_phase = split_step`
- `next_action = give_one_step_hint`

---

### Rule L3: Split Step -> Child Try

**条件**

- 已给出一个步骤提示

**动作**

- `current_phase = child_try`
- `next_action = invite_child_try`

---

### Rule L4: Child Try -> Feedback

**条件**

- 用户给出尝试结果
- 用户报出答案
- 用户说“我算出来了/我试了”

**动作**

- `current_phase = feedback`
- `next_action = give_feedback`

---

### Rule L5: Feedback -> Next Step Or Close

**条件**

- 当前步骤反馈完成

**动作**

- `current_phase = next_step_or_close`
- `next_action = advance_or_close`

---

### Rule L6: Feedback/Next Step -> Emotion Support

**条件**

- 用户出现明显挫败、自责、哭泣、羞耻表达

**动作**

- 切 scene 到 `emotion_support`
- `scene_enter_reason = manual_switch`

---

## 9. Play Interaction 迁移规则

### Phase 列表

- `open_round`
- `play_round`
- `branch_choice`
- `close`

### Rule P1: Enter Open Round

**条件**

- 新进入 `play_interaction`

**动作**

- `current_phase = open_round`
- `next_action = start_game_quickly`

---

### Rule P2: Open Round -> Play Round

**条件**

- 已建立玩法上下文

**动作**

- `current_phase = play_round`
- `next_action = continue_play_turn`

---

### Rule P3: Play Round -> Branch Choice

**条件**

- 当前玩法需要用户选 A/B

**动作**

- `current_phase = branch_choice`
- `next_action = offer_choice`

---

### Rule P4: Any Play Phase -> Emotion Support

**条件**

- 用户在游戏中表达难过、害怕、自责

**动作**

- 切 scene 到 `emotion_support`

---

### Rule P5: Any Play Phase -> Close

**条件**

- 用户说停
- 用户开始认真提问或求助

**动作**

- `current_phase = close`
- `task_completed = true`

---

## 10. System Repair 迁移规则

### Phase 列表

- `recognize_mismatch`
- `offer_choice`
- `re_anchor_topic`
- `close`

### Rule R1: Enter Recognize Mismatch

**条件**

- 新进入 `system_repair`

**动作**

- `current_phase = recognize_mismatch`
- `next_action = acknowledge_mismatch`

---

### Rule R2: Recognize Mismatch -> Offer Choice

**条件**

- 已承认没对上

**动作**

- `current_phase = offer_choice`
- `next_action = offer_repair_choice`

---

### Rule R3: Offer Choice -> Re-anchor Topic

**条件**

- 用户给出真实意图
- 用户从选项中做出选择

**动作**

- `current_phase = re_anchor_topic`
- `next_action = re_anchor_and_switch`

---

### Rule R4: Re-anchor Topic -> Close

**条件**

- 已重新识别真实目标 scene

**动作**

- `current_phase = close`
- `task_completed = true`
- `completion_signal = repair_completed`

---

### Rule R5: Repair Timeout

**条件**

- `repair_count >= 2`
- 且用户仍未给出有效澄清

**动作**

- 强制收窄成最小选择题
- 若仍失败，退回 `relationship_building`

---

## 11. Relationship Building 迁移规则

### Phase 列表

- `warm_opening`
- `light_followup`
- `close`

### Rule B1: Enter Warm Opening

**条件**

- 默认兜底
- 新会话开始

**动作**

- `current_phase = warm_opening`
- `next_action = greet_warmly`

---

### Rule B2: Warm Opening -> Light Followup

**条件**

- 用户表达愿意继续说
- 但尚未进入明确 scene

**动作**

- `current_phase = light_followup`
- `next_action = invite_more`

---

### Rule B3: Relationship Building -> Other Scene

**条件**

- router 识别到明确 `curiosity / emotion_support / learning_support / play_interaction`

**动作**

- 切到新 scene

---

## 12. 迁移实现顺序建议

V1 代码实现时建议每轮固定这样跑：

1. `evaluate_safety_override`
2. `evaluate_topic_switch`
3. `evaluate_scene_switch`
4. `resolve_default_phase_on_scene_enter`
5. `run_phase_transition_rules`
6. `set_next_action`
7. `set_close_or_switch_flags`
8. `emit_runtime_state`

---

## 13. 最小可实现规则集

如果先做 MVP，建议只实现这些规则：

- `G1 safety override`
- `G3 scene continue`
- `G4 scene switch`
- `E2 E3 E4 E5`
- `C2 C3 C4 C5 C6`
- `L2 L3 L4 L5 L6`
- `R2 R3 R4`

这样已经足够支撑：

- 情绪安抚
- 好奇心解释
- 作业辅导
- 听不懂修复

---

## 14. 推荐下一步

在这份规则文档之后，下一步最适合补：

1. `dialogue_state_manager_v1_runtime_schema.md`
2. 代码 MVP 中的：
   - `manager.py`
   - `transitions.py`
   - `rules.py`

