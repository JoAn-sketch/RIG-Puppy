"""send_message: 给联系人发短信/微信。

LLM 调用示例:
  send_message(nickname="大儿子", template_key="miss_you")
  send_message(nickname="奶奶", template_key="health_concern",
               variables={"msg":"血压有点高","tip":"按时吃药"})

配置(plugins.send_message):
  tencent_secret_id / tencent_secret_key / tencent_sdk_app_id / tencent_region
  wxpusher_app_token
  sender_name: 噜噜在模板中代指的"我"——默认"噜噜"
任何凭证缺失对应通道回退为 mocked，不影响对话流程。
"""

import json
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions import msg_db, msg_tencent_sms, msg_wxpusher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

SEND_MESSAGE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "send_message",
        "description": (
            "给已配置的联系人发送短信或微信消息。"
            "适用场景：用户说'给XX发个短信''告诉XX我想他了''让XX回个电话''跟XX报个平安'等。"
            "支持的模板 template_key："
            " miss_you(想你了)、call_back(让回电话)、safe(报平安)、health_concern(健康关心)、custom(自由文本)。"
            "短信只能用审核过的预设模板；微信(custom)可发任意文本。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nickname": {
                    "type": "string",
                    "description": "联系人昵称或关系，如'大儿子''小芳''女儿'。后端会模糊匹配。",
                },
                "template_key": {
                    "type": "string",
                    "description": "模板键。miss_you/call_back/safe/health_concern/custom 之一。"
                                   "用户说'想他了'用 miss_you；说'有事让他回电话'用 call_back；"
                                   "说'报平安/今天挺好'用 safe；说'血压高/咳嗽/记得吃药'用 health_concern；"
                                   "其他自由文本用 custom。",
                },
                "variables": {
                    "type": "object",
                    "description": "模板变量字典。health_concern 需要 msg(身体状况)+tip(嘱咐)；"
                                   "custom 需要 msg(完整消息文本)。其他模板无需变量。",
                },
            },
            "required": ["nickname", "template_key"],
        },
    },
}


def _channel_decide(contact, channel_pref: str, sms_supported: bool):
    """返回要走的 channel 列表：sms / wechat。"""
    pref = (channel_pref or "auto").lower()
    has_phone = bool(contact.get("phone"))
    has_uid = bool(contact.get("wxpusher_uid"))

    if pref == "sms":
        return ["sms"] if has_phone and sms_supported else []
    if pref == "wechat":
        return ["wechat"] if has_uid else []
    if pref == "both":
        out = []
        if has_uid:
            out.append("wechat")
        if has_phone and sms_supported:
            out.append("sms")
        return out

    if has_uid:
        return ["wechat"]
    if has_phone and sms_supported:
        return ["sms"]
    return []


@register_function(
    "send_message",
    SEND_MESSAGE_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
def send_message(
    conn: "ConnectionHandler",
    nickname: str = "",
    template_key: str = "",
    variables=None,
):
    cfg = conn.config.get("plugins", {}).get("send_message", {}) or {}
    sender_name = cfg.get("sender_name", "噜噜")

    if isinstance(variables, str):
        try:
            variables = json.loads(variables) if variables else {}
        except Exception:
            variables = {}
    variables = variables or {}
    variables.setdefault("name", sender_name)

    mac = getattr(conn, "device_id", "") or ""
    agent_id = msg_db.agent_id_by_mac(mac)
    if not agent_id:
        return ActionResponse(
            Action.REQLLM,
            "找不到当前设备对应的智能体，请管理员先在数据库里绑定。",
            None,
        )

    contact = msg_db.find_contact(agent_id, nickname)
    if not contact:
        existing = msg_db.list_contacts(agent_id)
        names = "、".join(c["nickname"] for c in existing) or "（通讯录是空的）"
        report = (
            f"未找到联系人「{nickname}」。当前通讯录里有：{names}。"
            f"请告诉用户没有这个联系人，可以让他报一个已存在的昵称。"
        )
        return ActionResponse(Action.REQLLM, report, None)

    template = msg_db.find_template(template_key)
    if not template:
        return ActionResponse(
            Action.REQLLM,
            f"模板「{template_key}」不存在，可用模板：miss_you/call_back/safe/health_concern/custom。",
            None,
        )

    rendered = msg_db.render(template["content"], variables)

    channels = _channel_decide(contact, contact.get("channel_pref"), bool(template["sms_supported"]))
    if not channels:
        msg_db.log_send(agent_id, contact["id"], contact["nickname"], "none",
                        template_key, rendered, "error", "no usable channel")
        return ActionResponse(
            Action.REQLLM,
            f"联系人「{contact['nickname']}」没有可用的发送方式（手机号未配或微信未绑定，"
            f"或这个模板不支持短信）。请告诉用户去管理后台补全。",
            None,
        )

    results = []
    for ch in channels:
        if ch == "sms":
            params = _build_sms_params(template, variables)
            status, err = msg_tencent_sms.send(
                cfg,
                contact.get("phone", ""),
                template.get("tencent_sms_template_id", ""),
                template.get("tencent_sms_sign", "") or cfg.get("tencent_sign_default", ""),
                params,
            )
        else:
            status, err = msg_wxpusher.send(
                cfg,
                contact.get("wxpusher_uid", ""),
                rendered,
                template.get("display_name", ""),
            )
        msg_db.log_send(agent_id, contact["id"], contact["nickname"], ch,
                        template_key, rendered, status, err or None)
        results.append((ch, status, err))
        logger.bind(tag=TAG).info(f"send_message channel={ch} status={status} err={err}")

    summary = _summary_for_llm(contact["nickname"], template["display_name"], rendered, results)
    return ActionResponse(Action.REQLLM, summary, None)


def _build_sms_params(template, variables):
    """按模板 variables 字段顺序提取参数列表（腾讯云短信模板用位置参数）。"""
    keys = [k.strip() for k in (template.get("variables") or "").split(",") if k.strip()]
    return [str(variables.get(k, "")) for k in keys]


def _summary_for_llm(nickname, template_name, rendered, results):
    has_success = any(s == "success" for _, s, _ in results)
    has_mocked = any(s == "mocked" for _, s, _ in results)
    has_error = any(s == "error" for _, s, _ in results)

    channels_text = "、".join(
        {"sms": "短信", "wechat": "微信"}.get(ch, ch) for ch, _, _ in results
    )

    if has_success and not has_error:
        return (
            f"已通过{channels_text}给{nickname}发出「{template_name}」消息，"
            f"内容：{rendered}。请简短告诉用户已经帮他发出去了。"
        )
    if has_mocked and not has_error:
        return (
            f"消息已暂存（{channels_text}通道暂未配置真实凭证，处于演练模式）。"
            f"内容：{rendered}。请告诉用户：发送通道还没接通，等管理员配好就能真的发了。"
        )
    if has_success and has_error:
        return (
            f"已通过部分通道把「{template_name}」发给{nickname}，但有通道失败。"
            f"请告诉用户主要消息已经发出，若没收到再让他试一次。"
        )
    return (
        f"给{nickname}发送「{template_name}」失败：{results}。"
        f"请告诉用户发送失败了，建议稍后再试或检查联系人配置。"
    )
