# Puppy Short-Term Memory V1

## Goal

Short-term memory is used to preserve recent topic continuity, not stable profile data.

It should solve cases like:

- talked about going to the zoo in the morning
- came back from the zoo in the afternoon
- continued asking about red pandas
- the robot should not respond as if this is the first time the topic appeared

Short-term memory answers:

- what we have been talking about recently
- what just happened
- what remains unfinished
- what the robot should continue naturally

It does not answer:

- how old the child is
- how the child likes to be addressed
- what dog types the child likes
- what parents want the robot to help with

Those belong to long-term memory.

## Boundary

Long-term memory:

- nickname preference
- age / age group
- robot name preference
- interests
- favorite dog types
- parent goals

Short-term memory:

- today's zoo visit
- just discussed red pandas
- explanation not finished yet
- recent excitement / frustration
- what has already been explained in the current topic

In one sentence:

- long-term memory = who this child is
- short-term memory = what we are currently talking about

## Data Model

V1 should use a topic-based structure instead of a full conversation summary.

Each device keeps 3 to 5 recent topic blocks.

Example:

```json
{
  "topic_id": "zoo_red_panda_2026-07-04",
  "topic": "going to the zoo and talking about red pandas",
  "summary": "The child said they were going to the zoo in the morning and later came back asking why red pandas have their own family.",
  "entities": ["zoo", "red panda", "giant panda", "family"],
  "open_questions": ["Why is the red panda not a kind of giant panda"],
  "resolved_points": ["Already explained what family means"],
  "emotion": "excited",
  "scene": "curiosity",
  "importance": 0.82,
  "last_user_text": "Why does the red panda have its own family",
  "last_assistant_text": "Family is like a larger animal group...",
  "last_active_at": "2026-07-04T15:20:00+08:00",
  "expires_at": "2026-07-05T03:00:00+08:00"
}
```

Core fields for V1:

- `topic`
- `summary`
- `entities`
- `open_questions`
- `scene`
- `expires_at`

## Read Path

Short-term memory should not rely only on explicit memory phrases like `上次` or `还记得吗`.

V1 uses three trigger layers:

### 1. Explicit memory trigger

Current markers can stay:

- `上次`
- `刚才`
- `之前`
- `昨天`
- `还记得`

### 2. Topic continuity trigger

If the current input overlaps with the active topic's `topic` or `entities`, short-term memory should be injected automatically.

Example:

- morning topic contains `动物园 / 小熊猫`
- afternoon input mentions `小熊猫 / 熊猫 / 动物园`
- even without saying `还记得`, the robot should continue naturally

### 3. Scene-default trigger

These scenes should prefer short-term memory by default:

- `curiosity`
- `learning_support`
- `emotion_support`
- `play_interaction`

## Write Path

Short-term memory should not be rewritten on every sentence.

V1 writes at these moments:

### 1. After a reply completes

Write only if the turn contains clear topical content, not pure greeting or filler.

### 2. High-value scenes

Prioritize writes in:

- `curiosity`
- `learning_support`
- `emotion_support`
- `play_interaction`

### 3. Event / experience mentions

Force a write when the child says things like:

- `今天去了……`
- `刚刚我……`
- `下午我……`
- `我看到……`

### 4. Unfinished question remains

If the turn still has unresolved explanatory content, store it in `open_questions`.

## Expiration Rules

V1 expiration should stay simple:

- default TTL: 24 hours
- `emotion_support`: 6 to 12 hours
- `curiosity / learning_support`: 24 hours
- keep at most 5 recent topics
- when exceeding 5, remove the oldest low-importance topic

This is enough to support morning-to-afternoon continuity without making the state too heavy.

## Prompt Injection

Short-term memory should be injected as its own runtime patch, not mixed into the generic `<memory>` block.

Example:

```txt
<short_term_memory>
active_topic=going to the zoo and talking about red pandas
summary=The child first said they were going to the zoo and later came back asking why red pandas have their own family.
entities=zoo,red panda,giant panda,family
open_questions=Why is the red panda not a kind of giant panda
continuity_rule=If the current question is directly related, continue naturally instead of treating it as a first-time topic
memory_rule=Prioritize unfinished questions, answer first, then add one light interaction
</short_term_memory>
```

## Storage Choice For V1

V1 should use runtime session state first, not a new external database table.

Reason:

- the current problem is real-time continuity
- topic memory is more deterministic than vector retrieval
- robot voice session and dingyi-chat already share runtime session state

Recommended V1 storage:

- device/session scoped in shared runtime state
- keep active short-term topic blocks in memory
- inject them into prompt on each turn

Recommended V2 storage:

- Redis or manager-api persistence
- keep same-day continuity after process restart

## Puppy Integration Plan

### Phase 1

Implement device-scoped runtime short-term topic memory.

Files to add or modify:

- `core/short_term_memory.py`
- `core/conversation_session_state.py`
- `core/handle/receiveAudioHandle.py`
- `core/connection.py`

### Phase 2

Persist short-term topics outside process memory.

Options:

- Redis
- manager-api table

### Phase 3

Promote repeated short-term facts into long-term memory.

Example:

- repeatedly mentions liking small dogs
- repeatedly asks science questions
- repeatedly prefers a certain interaction style

## First Implementation Scope

V1 should do only this:

- keep 3 to 5 recent topics per device
- support 24h topic continuity
- inject active topic into runtime prompt
- trigger on topic overlap as well as explicit memory markers
- update topic state after each completed reply

V1 should not do this yet:

- embedding retrieval
- complex topic clustering
- multi-day archival
- full conversation summary replacement
- LLM rewriting a large memory JSON on every turn

## Expected Result

Current behavior:

- child talks about the zoo in the morning
- child returns later and asks about red pandas
- robot responds like it is a brand new topic

Expected V1 behavior:

- robot recognizes the topic overlap
- robot keeps the unfinished question context
- robot answers as a continuation instead of restarting from zero
