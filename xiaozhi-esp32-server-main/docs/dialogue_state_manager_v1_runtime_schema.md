# Dialogue State Manager V1 Runtime Schema

## 1. 目标

这份文档定义 `dialogue state manager` 在运行时的输入、输出、内部状态和更新接口。

它回答的是：

- 代码里这个模块该吃什么
- 该吐什么
- 内存里状态长什么样
- 每轮更新怎么调用

---

## 2. 设计原则

### 2.1 与 Scene Router 解耦

`dialogue state manager` 不负责分类 scene。

它依赖外部输入：

- `scene_router_output`

然后只做：

- 状态推进
- phase 管理
- next action 决策

### 2.2 会话内状态优先

V1 先把它设计成：

- 会话内短期状态机

而不是长期 memory 模块。

### 2.3 输出控制信号，不直接生成文本

它的输出应该是：

- `current_phase`
- `next_action`
- `reply_style`
- `should_close_scene`

而不是最终回复文本。

---

## 3. Runtime Position

建议在当前链路中的位置：

1. `ASR`
2. `scene router`
3. `dialogue state manager`
4. `scene policy`
5. `prompt patch`
6. `LLM`
7. `state update after reply`

---

## 4. Runtime Input Schema

推荐输入结构：

```json
{
  "text": "鱼为什么能在水里呼吸",
  "timestamp_ms": 1717911111000,
  "scene_router_output": {},
  "dialogue_history_summary": {},
  "signals": {},
  "child_profile": {}
}
```

---

## 5. Input Object Definition

### 5.1 DialogueStateManagerInput

```json
{
  "text": "string",
  "timestamp_ms": 0,
  "scene_router_output": {},
  "dialogue_state": {},
  "signals": {},
  "child_profile": {}
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | `string` | 是 | 本轮用户文本 |
| `timestamp_ms` | `int` | 否 | 当前时间戳 |
| `scene_router_output` | `object` | 是 | scene router 输出 |
| `dialogue_state` | `object/null` | 否 | 上一轮状态，首次可空 |
| `signals` | `object` | 否 | 情绪、沉默、打断等运行信号 |
| `child_profile` | `object` | 否 | 年龄段与儿童画像信息 |

---

## 6. Scene Router Output Contract

`dialogue state manager` 建议依赖这些字段：

```json
{
  "primary_scene": "curiosity",
  "subscene": "natural_science",
  "risk_level": "low",
  "emotion_state": "curious",
  "age_band": "6-8",
  "policy_profile": "ask_then_explain",
  "should_use_rag": true,
  "should_use_memory": false,
  "should_force_safe_template": false,
  "confidence": 0.82,
  "reason_codes": ["为什么", "鱼为什么"]
}
```

---

## 7. Runtime Signals Schema

```json
{
  "emotion_hint": "neutral",
  "interruption": false,
  "silence_ms": 0,
  "user_move": "ask_why",
  "understanding_signal": "unknown",
  "topic_switch_signal": false,
  "frustration_signal": 0
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `emotion_hint` | `string` | 外部情绪提示 |
| `interruption` | `bool` | 是否被打断 |
| `silence_ms` | `int` | 沉默时长 |
| `user_move` | `string` | 当前用户行为类型 |
| `understanding_signal` | `string` | 是否理解 |
| `topic_switch_signal` | `bool` | 是否换话题 |
| `frustration_signal` | `int` | 0 到 3 的挫败程度 |

---

## 8. Child Profile Schema

```json
{
  "age_band": "6-8",
  "language_level": "child_basic",
  "interests": ["animals", "stories"],
  "learning_flags": ["math_weak"],
  "emotion_preferences": ["gentle_validation"]
}
```

V1 最少依赖：

| 字段 | 必要性 |
|---|---|
| `age_band` | 必做 |
| `language_level` | 可选 |
| `interests` | 可选 |
| `learning_flags` | 可选 |

---

## 9. Runtime State Schema

这是 `dialogue state manager` 内部维护的核心状态对象。

```json
{
  "scene_state": {},
  "phase_state": {},
  "turn_state": {},
  "user_state": {},
  "task_state": {},
  "meta": {}
}
```

---

## 10. Meta Schema

```json
{
  "version": "v1",
  "updated_at_ms": 1717911111000,
  "state_source": "runtime",
  "last_manager_result": "phase_advance"
}
```

| 字段 | 说明 |
|---|---|
| `version` | schema 版本 |
| `updated_at_ms` | 最后更新时间 |
| `state_source` | 状态来源 |
| `last_manager_result` | 上一次管理器决策结果 |

---

## 11. Runtime Output Schema

每轮管理器建议输出一个结构化结果：

```json
{
  "state": {},
  "control": {},
  "debug": {}
}
```

---

## 12. Control Schema

```json
{
  "current_scene": "curiosity",
  "current_subscene": "natural_science",
  "current_phase": "analogy_or_example",
  "next_action": "give_example_then_check",
  "reply_style": "short_child_friendly",
  "max_reply_sentences": 3,
  "should_ask_followup": true,
  "should_close_scene": false,
  "should_switch_scene": false,
  "should_use_memory": false,
  "should_use_rag": true,
  "should_force_safe_template": false
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `current_scene` | `string` | 当前主 scene |
| `current_subscene` | `string` | 当前子 scene |
| `current_phase` | `string` | 当前阶段 |
| `next_action` | `string` | 下一步动作 |
| `reply_style` | `string` | 推荐回复风格 |
| `max_reply_sentences` | `int` | 推荐句数上限 |
| `should_ask_followup` | `bool` | 是否允许追问 |
| `should_close_scene` | `bool` | 是否收尾 |
| `should_switch_scene` | `bool` | 是否切 scene |
| `should_use_memory` | `bool` | 是否允许记忆 |
| `should_use_rag` | `bool` | 是否允许 RAG |
| `should_force_safe_template` | `bool` | 是否强制安全模板 |

---

## 13. Debug Schema

```json
{
  "transition_reason": "phase_advance",
  "scene_changed": false,
  "phase_changed": true,
  "matched_rule": "C3",
  "router_confidence": 0.82,
  "notes": ["short_answer_completed"]
}
```

| 字段 | 说明 |
|---|---|
| `transition_reason` | 为什么迁移 |
| `scene_changed` | 是否切 scene |
| `phase_changed` | 是否切 phase |
| `matched_rule` | 命中的迁移规则编号 |
| `router_confidence` | scene router 置信度 |
| `notes` | 额外调试备注 |

---

## 14. 推荐 Python Dataclass Schema

建议后续代码层拆成这些对象：

### 14.1 Input

- `DialogueStateManagerInput`
- `RuntimeSignals`
- `ChildProfileSnapshot`

### 14.2 State

- `SceneState`
- `PhaseState`
- `TurnState`
- `UserState`
- `TaskState`
- `DialogueRuntimeState`

### 14.3 Output

- `DialogueControlOutput`
- `DialogueDebugOutput`
- `DialogueStateManagerResult`

---

## 15. Manager Interface

推荐接口：

```python
result = dialogue_state_manager.update(manager_input)
```

返回：

```python
DialogueStateManagerResult(
    state=...,
    control=...,
    debug=...,
)
```

---

## 16. Update Lifecycle

每轮建议分成两个阶段：

### 16.1 Pre-LLM Update

在进入 LLM 前执行：

1. 读取旧状态
2. 读取本轮 scene router 输出
3. 决定 scene/phase
4. 生成 control output

### 16.2 Post-LLM Update

在 LLM 输出后执行：

1. 写入 `last_bot_action`
2. 写入 `last_reply_length_bucket`
3. 如果需要，更新 `task_completed`

---

## 17. State Persistence Strategy

V1 建议：

- 存在 `ConnectionHandler` 会话对象上
- 不立即写数据库
- 不立即写长期 memory

建议字段名：

```python
conn.dialogue_state_runtime
```

---

## 18. Prompt Injection Schema

建议输出给 prompt 的内容：

```xml
<dialogue_state>
current_scene=curiosity
current_subscene=natural_science
current_phase=analogy_or_example
scene_turn_count=2
followup_count=1
next_action=give_example_then_check
reply_style=short_child_friendly
max_reply_sentences=3
should_close_scene=false
</dialogue_state>
```

---

## 19. Minimal V1 Runtime Schema

如果先做 MVP，可用最小版：

```json
{
  "scene_state": {
    "current_scene": "curiosity",
    "current_subscene": "natural_science",
    "scene_turn_count": 1,
    "scene_changed": true
  },
  "phase_state": {
    "current_phase": "short_answer",
    "phase_turn_count": 1,
    "next_action": "give_short_answer",
    "should_close_scene": false
  },
  "turn_state": {
    "turn_index": 4,
    "followup_count": 0,
    "last_bot_action": null,
    "last_user_move": "ask_why"
  },
  "user_state": {
    "emotion_state": "curious",
    "understanding_state": "unknown",
    "frustration_level": 0
  },
  "task_state": {
    "task_type": "explain_question",
    "task_completed": false
  }
}
```

---

## 20. 在你当前项目里的落点建议

建议后续新增目录：

```text
core/dialogue_state/
  __init__.py
  schema.py
  manager.py
  transitions.py
  rules.py
```

建议接入位置：

- `receiveAudioHandle.startToChat`

建议流程：

1. `scene_router.route(...)`
2. `dialogue_state_manager.update(...)`
3. `build_scene_prompt_patch(...)`
4. 注入 `<dialogue_state>`
5. `conn.chat(...)`

---

## 21. 推荐下一步

这两份文档之后，下一步就可以直接进代码 MVP：

1. `schema.py`
2. `manager.py`
3. `transitions.py`
4. `receiveAudioHandle` 接入

