# Dialogue State Manager V1

## 1. 目标

`dialogue state manager` 是多轮对话的运行时状态层。

它解决的不是：

- 这句话属于哪个 `scene`

它解决的是：

- 当前这段对话已经进行到哪一步
- 下一步该怎么推进
- 什么时候继续当前 scene
- 什么时候切 scene
- 什么时候收尾

一句话定义：

- `scene router` 决定“聊什么”
- `scene policy` 决定“怎么聊”
- `dialogue state manager` 决定“聊到哪一步了”

---

## 2. 为什么现在必须补

当前系统已经有：

- `scene router`
- `scene policy`
- `memory`
- `RAG`
- `intent recognition`

但还缺一个“多轮推进器”。

没有它，会出现这些问题：

- 同一个 `scene` 每轮都像重新开始
- 刚共情完又重复共情
- 刚解释完又重新解释
- 该追问时没追问
- 该结束时还在继续追问
- 同一个 `scene` 内部阶段变化无法表达

典型例子：

### 情绪支持

用户：

- “我今天好难过”

第一轮应该：

- 共情

第二轮用户：

- “因为同学不跟我玩”

第二轮不应该继续只做共情，而应该：

- 澄清事件
- 帮孩子说清发生了什么

第三轮用户：

- “那我明天怎么办”

第三轮应该：

- 给一个很小的行动建议

这 3 轮仍然都是 `emotion_support`

但已经不是同一个对话阶段。

---

## 3. 模块定位

`dialogue state manager` 位于：

1. `scene router` 之后
2. `scene policy` 执行之前
3. 回复生成之后还要反向更新状态

建议链路：

1. 用户输入
2. `scene router`
3. `dialogue state manager` 读取旧状态
4. 产出当前 `state + phase + next_action`
5. `scene policy executor`
6. LLM 生成回答
7. `dialogue state manager` 更新状态
8. 写入 memory / logs / evaluation

---

## 4. 核心职责

### 4.1 管理 scene 运行态

不是只看本轮 `scene`，而是管理：

- 当前 scene
- 上一轮 scene
- 已持续几轮
- 是否刚发生切换

### 4.2 管理 scene 内部 phase

同一个 scene 内部拆分阶段。

例如 `curiosity`：

- `acknowledge`
- `short_answer`
- `analogy`
- `check_understanding`
- `close`

### 4.3 管理追问与收尾

决定：

- 是否追问
- 还能追问几轮
- 是否已经足够
- 是否该收束

### 4.4 管理即时用户状态

跟踪：

- 当前情绪趋势
- 是否听懂
- 是否烦躁
- 是否沉默
- 是否想换话题

### 4.5 输出控制信号

它不直接回答用户，而是给后续生成层输出：

- 当前阶段
- 下一步动作
- 回复长度
- 是否允许追问
- 是否该切 scene

---

## 5. V1 状态模型

V1 建议使用分层状态：

- `scene_state`
- `phase_state`
- `turn_state`
- `user_state`
- `task_state`

---

## 6. 状态字段表

### 6.1 SceneState

```json
{
  "current_scene": "curiosity",
  "current_subscene": "natural_science",
  "previous_scene": "relationship_building",
  "scene_turn_count": 2,
  "scene_changed": true
}
```

字段说明：

- `current_scene`: 当前主 scene
- `current_subscene`: 当前子 scene
- `previous_scene`: 上一轮主 scene
- `scene_turn_count`: 当前 scene 已持续的轮数
- `scene_changed`: 本轮是否发生 scene 切换

### 6.2 PhaseState

```json
{
  "current_phase": "short_answer",
  "phase_turn_count": 1,
  "phase_completed": false
}
```

字段说明：

- `current_phase`: 当前 scene 内部阶段
- `phase_turn_count`: 当前 phase 持续轮数
- `phase_completed`: 当前阶段是否完成

### 6.3 TurnState

```json
{
  "turn_index": 14,
  "followup_count": 1,
  "last_bot_action": "give_short_answer",
  "last_user_intent": "why_question",
  "last_transition_reason": "scene_continue"
}
```

字段说明：

- `turn_index`: 整段对话轮次
- `followup_count`: 当前 scene 已追问几轮
- `last_bot_action`: 上一轮机器做了什么
- `last_user_intent`: 用户上一轮的主要行为
- `last_transition_reason`: 上次状态迁移原因

### 6.4 UserState

```json
{
  "emotion_trend": "stable_curious",
  "understanding_state": "unknown",
  "frustration_level": 0,
  "silence_repair_count": 0,
  "topic_switch_signal": false
}
```

字段说明：

- `emotion_trend`: 最近几轮情绪趋势
- `understanding_state`: `unknown / seems_understood / not_understood`
- `frustration_level`: 0 到 3
- `silence_repair_count`: 沉默修复次数
- `topic_switch_signal`: 是否想换话题

### 6.5 TaskState

```json
{
  "task_type": "explain_question",
  "task_completed": false,
  "completion_signal": null
}
```

字段说明：

- `task_type`: 这段对话当前的局部目标
- `task_completed`: 是否已经完成
- `completion_signal`: 完成原因

---

## 7. V1 输出字段

`dialogue state manager` 对外建议输出：

```json
{
  "current_scene": "curiosity",
  "current_subscene": "natural_science",
  "current_phase": "analogy",
  "next_action": "give_example_then_check",
  "should_ask_followup": true,
  "should_switch_scene": false,
  "should_close_scene": false,
  "reply_style": "short_child_friendly",
  "max_reply_sentences": 3
}
```

---

## 8. Scene 到 Phase 的状态机

V1 先覆盖 4 个最关键 scene：

- `emotion_support`
- `curiosity`
- `learning_support`
- `system_repair`

---

## 9. Emotion Support 状态机

### phase 列表

- `empathize`
- `clarify_event`
- `normalize_feeling`
- `small_action`
- `close`

### 迁移逻辑

1. 首次进入 `emotion_support`
   - 进入 `empathize`

2. 用户继续描述原因
   - `empathize -> clarify_event`

3. 事件已明确
   - `clarify_event -> normalize_feeling`

4. 用户询问怎么办 / 可行动
   - `normalize_feeling -> small_action`

5. 用户缓和 / 接受建议 / 话题结束
   - `small_action -> close`

### 控制规则

- `empathize` 最多 1 轮
- `clarify_event` 最多 2 轮
- `small_action` 一次只给一个建议

---

## 10. Curiosity 状态机

### phase 列表

- `acknowledge`
- `short_answer`
- `analogy_or_example`
- `check_understanding`
- `optional_followup`
- `close`

### 迁移逻辑

1. 新问题进入
   - `acknowledge`

2. 接住问题后
   - `acknowledge -> short_answer`

3. 如果问题需要进一步解释
   - `short_answer -> analogy_or_example`

4. 给完类比后
   - `analogy_or_example -> check_understanding`

5. 如果用户继续问
   - `check_understanding -> optional_followup`

6. 用户表示懂了或结束
   - 任意阶段 -> `close`

### 控制规则

- `short_answer` 必须先于长解释
- `optional_followup` 最多 1 轮
- 避免无限苏格拉底追问

---

## 11. Learning Support 状态机

### phase 列表

- `find_block`
- `split_step`
- `child_try`
- `feedback`
- `next_step_or_close`

### 迁移逻辑

1. 用户说不会做
   - `find_block`

2. 确认卡点后
   - `find_block -> split_step`

3. 给出一步后
   - `split_step -> child_try`

4. 用户尝试后
   - `child_try -> feedback`

5. 若仍未完成
   - `feedback -> next_step_or_close`

6. 若完成
   - `feedback -> close`

### 控制规则

- 不允许一上来直接整题代答
- 每轮只推进一个小步骤
- 一旦用户明显受挫，可切 `emotion_support`

---

## 12. System Repair 状态机

### phase 列表

- `recognize_mismatch`
- `offer_choice`
- `re_anchor_topic`
- `close`

### 迁移逻辑

1. 检测到没听懂 / 答非所问
   - `recognize_mismatch`

2. 承认没对上后
   - `offer_choice`

3. 用户重新给意图
   - `re_anchor_topic`

4. 跳回真实 scene
   - `close`

### 控制规则

- 修复不超过 2 轮
- 不能一直在 repair 里循环

---

## 13. 状态迁移触发信号

建议使用以下触发源：

### 13.1 来自 scene router

- `primary_scene`
- `subscene`
- `risk_level`

### 13.2 来自用户文本

- 是否继续描述
- 是否问“怎么办”
- 是否说“我懂了”
- 是否说“换一个”
- 是否表达烦躁

### 13.3 来自策略执行结果

- 上一轮是否已给短答案
- 是否已给行动建议
- 是否已做澄清

### 13.4 来自安全层

- 若有高风险，直接打断普通状态机

---

## 14. 和现有模块的连接方式

### 14.1 和 Scene Router 的关系

输入：

- 当前用户话语
- 当前 `scene router` 输出

作用：

- 判断 scene 是继续还是切换

### 14.2 和 Scene Policy 的关系

`dialogue state manager` 输出：

- `current_phase`
- `next_action`
- `reply_style`

然后 `scene policy` 再根据：

- `scene + subscene + phase`

生成更具体的 prompt 约束。

### 14.3 和 Memory 的关系

不是每轮都把状态写入长期记忆。

建议分层：

- `dialogue_state`: 会话内短期状态
- `memory`: 跨会话长期记忆

只有这些内容适合写入 memory：

- 长期兴趣
- 长期情绪模式
- 长期学习薄弱点

### 14.4 和 RAG 的关系

由状态决定 RAG 何时真正启用。

例如：

- `curiosity.short_answer`: 可以先不用 RAG
- `curiosity.analogy_or_example`: 如果需要准确知识，再开 RAG

### 14.5 和 Safety Guardian 的关系

`safety guardian` 优先级高于 `dialogue state manager`

即：

- 有风险先切安全
- 状态机暂停普通推进

---

## 15. V1 最小实现范围

不要一开始就做成通用复杂状态机。

建议 V1 范围：

### 必做字段

- `current_scene`
- `current_subscene`
- `current_phase`
- `scene_turn_count`
- `followup_count`
- `last_bot_action`
- `task_completed`

### 必做 scene

- `emotion_support`
- `curiosity`
- `learning_support`
- `system_repair`

### 先不做

- 通用全场景复杂状态图
- 过深的用户认知建模
- 自动长期记忆写回策略
- 动作规划联动

---

## 16. 在你当前项目里的落点建议

结合现有结构，建议新增：

### 新模块

`core/dialogue_state/`

建议包含：

- `schema.py`
- `manager.py`
- `transitions.py`
- `rules.py`

### 当前调用位置

建议放在：

- `receiveAudioHandle.startToChat`

顺序建议：

1. `scene_router.route(...)`
2. `dialogue_state_manager.update(...)`
3. 生成 `scene_policy + phase_policy`
4. 注入 prompt
5. 进入 `conn.chat(...)`

---

## 17. 推荐输出给 Prompt 的附加结构

除了现有的：

```xml
<scene_router>
...
</scene_router>
```

建议新增：

```xml
<dialogue_state>
current_scene=curiosity
current_phase=analogy_or_example
scene_turn_count=2
followup_count=1
next_action=give_example_then_check
should_close_scene=false
</dialogue_state>
```

这样 LLM 才知道：

- 不是重新开始
- 而是继续当前多轮推进

---

## 18. 评估指标

V1 至少跟踪这些指标：

- scene 内重复回答率
- 无效追问率
- 过长回答率
- 正确收尾率
- scene 切换合理率
- 学习辅导中直接代答率

---

## 19. 一句话总结

`dialogue state manager` 是把静态的 `scene` 变成“多轮可推进对话”的关键模块。

没有它：

- 你只有分类和策略

有了它：

- 你才真正有“对话流程”

---

## 20. 下一步

在这份设计之后，下一步建议直接产出：

1. `dialogue_state_manager_v1_state_table.md`
2. `dialogue_state_manager_v1_transition_rules.md`
3. 代码 MVP：
   - 先只接 `curiosity / emotion_support / learning_support / system_repair`

