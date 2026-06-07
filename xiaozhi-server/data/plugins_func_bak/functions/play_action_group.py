"""
动作组调度插件 - 模型只选情绪组,后端随机选具体序列执行
部署到: plugins_func/functions/play_action_group.py
"""
import random
import time
import json
import asyncio
import threading
from plugins_func.register import register_function, Action, ActionResponse, ToolType
from core.providers.tools.device_mcp.mcp_handler import call_mcp_tool
from config.logger import setup_logging

logger = setup_logging()
TAG = "play_action_group"

# ========== 8 类动作组,每组 3~5 个候选序列 ==========
ACTION_GROUPS = {
    "idle": {
        "desc": "普通对话、待机、轻回应",
        "default_intensity": 1,
        "sequences": [
            ["Swing"],
            ["Lookup"],
            ["Swing", "Lookup"],
            ["Lookup", "Swing"],
        ]
    },
    "listen": {
        "desc": "老人讲话、等待输入、表示在听",
        "default_intensity": 1,
        "sequences": [
            ["Lookup"],
            ["Sit", "Lookup"],
            ["Swing"],
            ["Lookup", "Sit"],
        ]
    },
    "thinking": {
        "desc": "思考、查询中、识别图片时",
        "default_intensity": 1,
        "sequences": [
            ["Lookup", "Swing"],
            ["Sit", "Lookup"],
            ["Lookup"],
            ["Swing", "Lookup"],
        ]
    },
    "happy": {
        "desc": "好消息、完成任务、老人夸奖、开心",
        "default_intensity": 2,
        "sequences": [
            ["Bouncing", "Wave"],
            ["Swing", "Shaking", "Wave"],
            ["Lookup", "Bouncing"],
            ["Bouncing", "Swing"],
            ["Wave", "Bouncing", "Shaking"],
        ]
    },
    "cute": {
        "desc": "撒娇、讨奖励、卖萌、日常陪伴亲近",
        "default_intensity": 2,
        "sequences": [
            ["Swing", "Hug"],
            ["Sit", "Wave"],
            ["Lookup", "Swing", "Hug"],
            ["Naughty", "Swing"],
            ["Swing", "Lookup", "Wave"],
        ]
    },
    "comfort": {
        "desc": "安慰、陪伴、老人难过孤独生病",
        "default_intensity": 1,
        "sequences": [
            ["Sit", "Hug"],
            ["Lookup", "Sit"],
            ["Swing", "Hug"],
            ["Sit", "Lookup", "Hug"],
            ["Sit"],
        ]
    },
    "guard": {
        "desc": "反诈警告、健康异常、严肃紧急提醒",
        "default_intensity": 1,
        "sequences": [
            ["Sit", "Lookup"],
            ["Sit"],
            ["Lookup", "Sit"],
        ],
        "forbidden": ["Bouncing", "Wave", "Naughty", "Shaking", "Hug", "Rolling"]
    },
    "perform": {
        "desc": "跳舞、表演才艺、逗老人开心",
        "default_intensity": 3,
        "sequences": [
            ["Wave", "Bouncing", "Swing", "Rolling", "Stretch"],
            ["Bouncing", "Shaking", "Wave", "Swing"],
            ["Wave", "Bouncing", "Shaking", "Rolling"],
            ["Swing", "Bouncing", "Wave", "Stretch", "Shaking"],
            ["Rolling", "Bouncing", "Wave", "Swing", "Lookup"],
        ]
    },
}

# ========== 模式行为配置 ==========
# max_intensity: 允许的最大动作强度
# cooldown: 冷却秒数(越大动作越少)
# rate_limit: 每分钟最多几次
# allowed_groups: 允许的动作组(None=全部)
# forbidden_groups: 禁止的动作组
MODE_BEHAVIOR = {
    "lively": {
        "max_intensity": 2,
        "cooldown": 3,
        "rate_limit": 8,
        "forbidden_groups": [],
    },
    "listening": {
        "max_intensity": 1,
        "cooldown": 20,
        "rate_limit": 2,
        "forbidden_groups": ["happy", "cute", "perform"],
    },
    "playmate": {
        "max_intensity": 3,
        "cooldown": 4,
        "rate_limit": 8,
        "forbidden_groups": [],
    },
    "professional": {
        "max_intensity": 1,
        "cooldown": 25,
        "rate_limit": 1,
        "forbidden_groups": ["cute", "happy", "perform", "comfort"],
    },
    "therapist": {
        "max_intensity": 1,
        "cooldown": 20,
        "rate_limit": 2,
        "forbidden_groups": ["happy", "perform", "cute"],
    },
}
DEFAULT_BEHAVIOR = {"max_intensity": 2, "cooldown": 8, "rate_limit": 4, "forbidden_groups": []}

# ========== 冷却/限频 全局状态(per-connection 用 conn 属性) ==========
ACTION_INTERVAL_BETWEEN_STEPS = 1.5  # 序列内动作间隔秒数


def _get_action_state(conn):
    if not hasattr(conn, '_action_state'):
        conn._action_state = {
            'last_time': 0,
            'window': [],
            'last_seq_key': None,
        }
    return conn._action_state


def _check_cooldown(state, cooldown, rate_limit):
    now = time.time()
    if now - state['last_time'] < cooldown:
        return False
    state['window'] = [t for t in state['window'] if now - t < 60]
    if len(state['window']) >= rate_limit:
        return False
    return True


def _record_action(state):
    now = time.time()
    state['last_time'] = now
    state['window'].append(now)


def _pick_sequence(state, group_name, sequences):
    candidates = list(range(len(sequences)))
    last = state['last_seq_key']
    if last and last[0] == group_name and len(candidates) > 1:
        if last[1] in candidates:
            candidates.remove(last[1])
    idx = random.choice(candidates)
    state['last_seq_key'] = (group_name, idx)
    return sequences[idx]


def _execute_sequence_async(conn, sequence, interval):
    """在后台异步执行动作序列,不阻塞对话"""
    async def _run():
        if not hasattr(conn, 'mcp_client') or not conn.mcp_client:
            logger.bind(tag=TAG).warning("设备MCP未连接,跳过动作")
            return
        for i, action_name in enumerate(sequence):
            try:
                await call_mcp_tool(conn, conn.mcp_client, f"self_dog_{action_name}", "{}")
                logger.bind(tag=TAG).info(f"动作执行: {action_name} ✓")
            except Exception as e:
                logger.bind(tag=TAG).warning(f"动作执行失败: {action_name} - {e}")
            if i < len(sequence) - 1:
                await asyncio.sleep(interval)

    loop = getattr(conn, 'loop', None)
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(_run(), loop)
    else:
        threading.Thread(target=lambda: asyncio.run(_run()), daemon=True).start()


# ========== 注册插件 ==========
@register_function('play_action_group', {
    "type": "function",
    "function": {
        "name": "play_action_group",
        "description": (
            "根据情绪/场景让丁一锅做肢体动作。"
            "可选组: idle(轻回应) listen(倾听) thinking(思考) "
            "happy(开心) cute(撒娇) comfort(安慰) "
            "guard(严肃守护) perform(表演跳舞)。"
            "频率控制: 普通对话每3-5轮触发一次idle/listen; "
            "强烈情绪(开心/难过/表演请求)才立即触发happy/comfort/perform。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "group": {
                    "type": "string",
                    "enum": ["idle", "listen", "thinking", "happy",
                             "cute", "comfort", "guard", "perform"],
                    "description": "动作情绪组"
                },
                "intensity": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": "强度:1轻微 2中等 3强烈。不传则用组默认值。"
                },
                "timing": {
                    "type": "string",
                    "enum": ["before", "after", "during"],
                    "description": "动作时机:before说话前 after说话后 during伴随。默认before。"
                }
            },
            "required": ["group"]
        }
    }
}, type=ToolType.SYSTEM_CTL)
def play_action_group(conn, group: str, intensity: int = None, timing: str = "before"):
    """模型调用入口: 选组→限频→选序列→后台执行"""

    # 容错: 去尾部s, 转小写
    group = group.lower().rstrip("s")
    if group not in ACTION_GROUPS:
        # 尝试前缀匹配
        matches = [k for k in ACTION_GROUPS if k.startswith(group)]
        if len(matches) == 1:
            group = matches[0]
        else:
            return ActionResponse(action=Action.REQLLM, result="", response="")

    group_cfg = ACTION_GROUPS[group]
    state = _get_action_state(conn)

    # 获取模式行为配置
    mode_code = getattr(conn, '_current_mode_code', 'lively')
    behavior = MODE_BEHAVIOR.get(mode_code, DEFAULT_BEHAVIOR)

    # 模式禁止的动作组
    if group in behavior.get("forbidden_groups", []):
        logger.bind(tag=TAG).debug(f"模式 {mode_code} 禁止 {group} 组")
        return ActionResponse(action=Action.REQLLM, result="", response="")

    # 冷却检查(根据模式动态调整)
    if not _check_cooldown(state, behavior["cooldown"], behavior["rate_limit"]):
        logger.bind(tag=TAG).debug(f"动作冷却中,跳过 {group}")
        return ActionResponse(action=Action.REQLLM, result="", response="")

    # 强度裁剪
    req_intensity = intensity if intensity else group_cfg["default_intensity"]
    max_allowed = behavior["max_intensity"]
    final_intensity = min(req_intensity, max_allowed)

    if final_intensity == 0:
        return ActionResponse(action=Action.REQLLM, result="", response="")

    # 选序列(避免重复)
    sequence = _pick_sequence(state, group, group_cfg["sequences"])

    # 强度低于组默认时,截断序列
    if final_intensity < group_cfg["default_intensity"]:
        sequence = sequence[:max(1, len(sequence) // 2)]

    # 记录
    _record_action(state)

    # 后台异步执行动作序列(不阻塞TTS)
    _execute_sequence_async(conn, sequence, ACTION_INTERVAL_BETWEEN_STEPS)

    seq_str = " → ".join(sequence)
    logger.bind(tag=TAG).info(
        f"[{group}/lv{final_intensity}/{timing}] 执行: {seq_str}"
    )

    # 动作已触发,让 LLM 继续生成文字回复
    return ActionResponse(action=Action.REQLLM, result="动作已执行", response="")
