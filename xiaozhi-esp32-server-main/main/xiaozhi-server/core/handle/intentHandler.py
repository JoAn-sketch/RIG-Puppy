from __future__ import annotations

import json
import uuid
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import ContentType
from core.handle.helloHandle import checkWakeupWords
from plugins_func.register import Action, ActionResponse
from core.handle.sendAudioHandle import send_stt_message
from core.handle.reportHandle import enqueue_tool_report
from core.utils.util import remove_punctuation_and_length
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType
from core.response_orchestrator import rewrite_reply_text

TAG = __name__

TIME_QUERY_MARKERS = ("现在几点", "几点了", "几点啦", "当前时间", "现在时间", "时间是多少")
DATE_QUERY_MARKERS = ("今天几号", "今天多少号", "今天日期", "今天是什么日期", "今天星期几", "今天周几")
LUNAR_QUERY_MARKERS = ("今天农历", "农历几号", "农历多少", "今天什么节气")
TOOL_INTENT_MARKERS = (
    "打开",
    "关闭",
    "调高",
    "调低",
    "设置",
    "播放",
    "暂停",
    "停止播放",
    "音量",
    "亮度",
    "灯",
    "音乐",
    "歌曲",
    "天气",
    "电池",
    "设备",
)
CHAT_FAST_PATH_SCENES = {
    "curiosity",
    "relationship_building",
    "emotion_support",
    "learning_support",
    "play_interaction",
}


def _normalize_text(text: str) -> str:
    return "".join((text or "").strip().split())


def _is_time_query(text: str) -> bool:
    normalized = _normalize_text(text)
    if any(marker in normalized for marker in TIME_QUERY_MARKERS):
        return True
    return ("现在" in normalized or "当前" in normalized) and ("几点" in normalized or "时间" in normalized)


def _is_date_query(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(marker in normalized for marker in DATE_QUERY_MARKERS)


def _is_lunar_query(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(marker in normalized for marker in LUNAR_QUERY_MARKERS)


def _should_skip_llm_intent(conn: "ConnectionHandler", text: str) -> bool:
    if getattr(conn, "intent_type", None) != "intent_llm":
        return False
    scene_output = getattr(conn, "last_scene_output", None)
    current_scene = getattr(scene_output, "primary_scene", None)
    if current_scene not in CHAT_FAST_PATH_SCENES:
        return False
    normalized = _normalize_text(text)
    return not any(marker in normalized for marker in TOOL_INTENT_MARKERS)


def _build_grounded_context_reply(text: str) -> str | None:
    from core.utils.current_time import get_current_time_info

    normalized = _normalize_text(text)
    current_time, today_date, today_weekday, lunar_date = get_current_time_info()
    wants_time = _is_time_query(normalized)
    wants_date = _is_date_query(normalized)
    wants_lunar = _is_lunar_query(normalized)

    if not any((wants_time, wants_date, wants_lunar)):
        return None

    parts = []
    if wants_time:
        parts.append(f"现在是{current_time}")
    if wants_date:
        parts.append(f"今天是{today_date}，{today_weekday}")
    if wants_lunar:
        parts.append(f"今天农历是{lunar_date}")
    return "。".join(parts) + "。"


def _build_grounded_greeting_reply(conn: "ConnectionHandler", text: str) -> str | None:
    if getattr(conn, "pending_daily_greeting", None) is not None:
        return None
    state_result = getattr(conn, "last_dialogue_state_result", None)
    if state_result is None:
        return None
    social_state = (getattr(state_result, "state", {}) or {}).get("social_state", {})
    if not social_state.get("is_greeting_turn"):
        return None
    if not social_state.get("greeting_conflict_with_time"):
        return None

    current_label = social_state.get("current_time_label") or "现在这个时段"
    recommended = social_state.get("recommended_greeting") or "你好"
    if social_state.get("greeting_conflict_with_previous"):
        return f"现在还是{current_label}呢，我们接着聊吧，{recommended}。"
    return f"现在更像{current_label}呢，不过见到你很开心，{recommended}。"


async def _speak_grounded_reply(conn: "ConnectionHandler", original_text: str, reply_text: str) -> bool:
    await send_stt_message(conn, original_text)
    conn.client_abort = False
    conn.sentence_id = str(uuid.uuid4().hex)
    conn.dialogue.put(Message(role="user", content=original_text))
    speak_txt(conn, reply_text)
    return True


async def handle_user_intent(conn: "ConnectionHandler", text):
    # 预处理输入文本，处理可能的JSON格式
    try:
        if text.strip().startswith("{") and text.strip().endswith("}"):
            parsed_data = json.loads(text)
            if isinstance(parsed_data, dict) and "content" in parsed_data:
                text = parsed_data["content"]  # 提取content用于意图分析
                conn.current_speaker = parsed_data.get("speaker")  # 保留说话人信息
    except (json.JSONDecodeError, TypeError):
        pass

    # 检查是否有明确的退出命令
    _, filtered_text = remove_punctuation_and_length(text)
    if await check_direct_exit(conn, filtered_text):
        return True

    # 检查是否是唤醒词
    if await checkWakeupWords(conn, filtered_text):
        return True

    grounded_context_reply = _build_grounded_context_reply(text)
    if grounded_context_reply:
        conn.logger.bind(tag=TAG).info(f"命中确定性时间/日期回复: {text}")
        return await _speak_grounded_reply(conn, text, grounded_context_reply)

    grounded_greeting_reply = _build_grounded_greeting_reply(conn, text)
    if grounded_greeting_reply:
        conn.logger.bind(tag=TAG).info(f"命中时间感知问候纠偏: {text}")
        return await _speak_grounded_reply(conn, text, grounded_greeting_reply)

    if _should_skip_llm_intent(conn, text):
        conn.logger.bind(tag=TAG).debug(f"普通儿童聊天跳过 LLM 意图识别: {text}")
        return False

    if conn.intent_type == "nointent":
        return False

    if conn.intent_type == "function_call":
        # 使用支持function calling的聊天方法,不再进行意图分析
        return False
    # 使用LLM进行意图分析
    intent_result = await analyze_intent_with_llm(conn, text)
    if not intent_result:
        return False
    # 会话开始时生成sentence_id
    conn.sentence_id = str(uuid.uuid4().hex)
    # 处理各种意图
    return await process_intent_result(conn, intent_result, text)


async def check_direct_exit(conn: "ConnectionHandler", text):
    """检查是否有明确的退出命令"""
    _, text = remove_punctuation_and_length(text)
    cmd_exit = conn.cmd_exit
    for cmd in cmd_exit:
        if text == cmd:
            conn.logger.bind(tag=TAG).info(f"识别到明确的退出命令: {text}")
            await send_stt_message(conn, text)
            await conn.close()
            return True
    return False


async def analyze_intent_with_llm(conn: "ConnectionHandler", text):
    """使用LLM分析用户意图"""
    if not hasattr(conn, "intent") or not conn.intent:
        conn.logger.bind(tag=TAG).warning("意图识别服务未初始化")
        return None

    # 对话历史记录
    dialogue = conn.dialogue
    try:
        intent_result = await conn.intent.detect_intent(conn, dialogue.dialogue, text)
        return intent_result
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"意图识别失败: {str(e)}")

    return None


async def process_intent_result(
    conn: "ConnectionHandler", intent_result, original_text
):
    """处理意图识别结果"""
    try:
        # 尝试将结果解析为JSON
        intent_data = json.loads(intent_result)

        # 检查是否有function_call
        if "function_call" in intent_data:
            # 直接从意图识别获取了function_call
            conn.logger.bind(tag=TAG).debug(
                f"检测到function_call格式的意图结果: {intent_data['function_call']['name']}"
            )
            function_name = intent_data["function_call"]["name"]
            if function_name == "continue_chat":
                return False

            if function_name == "result_for_context":
                await send_stt_message(conn, original_text)
                conn.client_abort = False

                def process_context_result():
                    conn.dialogue.put(Message(role="user", content=original_text))

                    from core.utils.current_time import get_current_time_info

                    current_time, today_date, today_weekday, lunar_date = (
                        get_current_time_info()
                    )

                    # 构建带上下文的基础提示
                    context_prompt = f"""当前时间：{current_time}
                                        今天日期：{today_date} ({today_weekday})
                                        今天农历：{lunar_date}

                                        请根据以上信息回答用户的问题：{original_text}"""

                    response = conn.intent.replyResult(context_prompt, original_text)
                    speak_txt(conn, response)

                conn.executor.submit(process_context_result)
                return True

            function_args = {}
            if "arguments" in intent_data["function_call"]:
                function_args = intent_data["function_call"]["arguments"]
                if function_args is None:
                    function_args = {}
            # 确保参数是字符串格式的JSON
            if isinstance(function_args, dict):
                function_args = json.dumps(function_args)

            function_call_data = {
                "name": function_name,
                "id": str(uuid.uuid4().hex),
                "arguments": function_args,
            }

            await send_stt_message(conn, original_text)
            conn.client_abort = False

            # 准备工具调用参数
            tool_input = {}
            if function_args:
                if isinstance(function_args, str):
                    tool_input = json.loads(function_args) if function_args else {}
                elif isinstance(function_args, dict):
                    tool_input = function_args

            # 上报工具调用
            enqueue_tool_report(conn, function_name, tool_input)

            # 使用executor执行函数调用和结果处理
            def process_function_call():
                conn.dialogue.put(Message(role="user", content=original_text))
                
                # 工具调用超时时间
                tool_call_timeout = int(conn.config.get("tool_call_timeout", 30))
                # 使用统一工具处理器处理所有工具调用
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        conn.func_handler.handle_llm_function_call(
                            conn, function_call_data
                        ),
                        conn.loop,
                    ).result(timeout=tool_call_timeout)
                except Exception as e:
                    conn.logger.bind(tag=TAG).error(f"工具调用失败: {e}")
                    result = ActionResponse(
                        action=Action.ERROR, result="工具调用超时，请一会再试下哈", response="工具调用超时，请一会再试下哈"
                    )

                # 上报工具调用结果
                if result:
                    enqueue_tool_report(conn, function_name, tool_input, str(result.result) if result.result else None, report_tool_call=False)

                    if result.action == Action.RESPONSE:  # 直接回复前端
                        text = result.response
                        if text is not None:
                            speak_txt(conn, text)
                    elif result.action == Action.REQLLM:  # 调用函数后再请求llm生成回复
                        text = result.result
                        conn.dialogue.put(Message(role="tool", content=text))
                        llm_result = conn.intent.replyResult(text, original_text)
                        if llm_result is None:
                            llm_result = text
                        speak_txt(conn, llm_result)
                    elif (
                        result.action == Action.NOTFOUND
                        or result.action == Action.ERROR
                    ):
                        text = result.response if result.response else result.result
                        if text is not None:
                            speak_txt(conn, text)
                    elif function_name != "play_music":
                        # For backward compatibility with original code
                        # 获取当前最新的文本索引
                        text = result.response
                        if text is None:
                            text = result.result
                        if text is not None:
                            speak_txt(conn, text)

            # 将函数执行放在线程池中
            conn.executor.submit(process_function_call)
            return True
        return False
    except json.JSONDecodeError as e:
        conn.logger.bind(tag=TAG).error(f"处理意图结果时出错: {e}")
        return False


def speak_txt(conn: "ConnectionHandler", text):
    text = conn._rewrite_assistant_reply(text)
    # 记录文本到 sentence_id 映射
    conn.tts.store_tts_text(conn.sentence_id, text)

    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.FIRST,
            content_type=ContentType.ACTION,
        )
    )
    conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=text)
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.LAST,
            content_type=ContentType.ACTION,
        )
    )
    conn.dialogue.put(Message(role="assistant", content=text))
    if hasattr(conn, "_record_assistant_reply"):
        conn._record_assistant_reply(
            text,
            next_action=getattr(conn, "_get_dialogue_next_action", lambda: None)(),
        )
