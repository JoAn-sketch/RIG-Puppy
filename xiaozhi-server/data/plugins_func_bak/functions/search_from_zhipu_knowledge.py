"""
search_from_zhipu_knowledge.py
智谱知识库检索插件 — 支持多知识库，按模式配置动态选择

工作模式:
  调用 glm-4-flash + retrieval tool，对每个启用的知识库并行检索，
  汇总结果返回给主 LLM。
"""
import json
import requests
import concurrent.futures
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

SEARCH_FROM_ZHIPU_KNOWLEDGE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "search_from_zhipu_knowledge",
        "description": "从知识库中查询信息。仅当用户明确询问养生健康、防诈骗、医疗健康等专业知识，且这类信息不在你的常识范围内时才调用。普通科学常识、日常问答、儿童百科类问题（如为什么鱼能在水里呼吸）不要调用此工具，直接回答即可。",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "查询的问题，原样转述用户的问题"}
            },
            "required": ["question"],
        },
    },
}


def _query_single_kb(api_key, base_url, model, knowledge_id, question):
    """查询单个知识库"""
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "严格基于知识库内容回答；若知识库中没有相关信息，直接回答无相关信息。",
            },
            {"role": "user", "content": question},
        ],
        "tools": [{"type": "retrieval", "retrieval": {"knowledge_id": knowledge_id}}],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    r.encoding = "utf-8"
    r.raise_for_status()
    result = r.json()
    answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return answer


@register_function(
    "search_from_zhipu_knowledge",
    SEARCH_FROM_ZHIPU_KNOWLEDGE_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
def search_from_zhipu_knowledge(conn: "ConnectionHandler", question=None):
    if not isinstance(question, str) or not question.strip():
        question = str(question or "")

    cfg = conn.config.get("plugins", {}).get("search_from_zhipu_knowledge", {})
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "https://open.bigmodel.cn/api/paas/v4")
    model = cfg.get("model", "glm-4-flash")

    if not api_key:
        return ActionResponse(Action.RESPONSE, None, "知识库未配置(缺 api_key)")

    # 获取当前模式绑定的知识库列表
    knowledge_ids = []
    # 优先从连接的运行时状态获取（switch_mode 设置的）
    if hasattr(conn, '_current_knowledge_ids') and conn._current_knowledge_ids:
        knowledge_ids = conn._current_knowledge_ids
    else:
        # fallback: 从插件配置获取单个 knowledge_id（兼容旧配置）
        single_id = cfg.get("knowledge_id", "")
        if single_id:
            knowledge_ids = [single_id]

    if not knowledge_ids:
        return ActionResponse(Action.RESPONSE, None, "当前模式未配置知识库")

    # 并行查询所有知识库
    answers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_query_single_kb, api_key, base_url, model, kid, question): kid
            for kid in knowledge_ids
        }
        for future in concurrent.futures.as_completed(futures):
            kid = futures[future]
            try:
                answer = future.result()
                if answer and "无相关信息" not in answer:
                    answers.append(answer)
            except Exception as e:
                logger.bind(tag=TAG).warning(f"知识库 {kid} 查询失败: {e}")

    if not answers:
        return ActionResponse(Action.REQLLM, "知识库中未找到相关信息。", None)

    # 合并结果
    combined = "\n---\n".join(answers)
    context = f"# 关于问题【{question}】查到知识库如下\n```\n{combined}\n```"
    return ActionResponse(Action.REQLLM, context, None)
