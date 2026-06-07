"""腾讯云短信 HTTP 直连 (TC3-HMAC-SHA256)，无 SDK 依赖。

凭证从 conn.config["plugins"]["send_message"] 读，缺失则返回 mocked 状态。
"""

import json
import hmac
import hashlib
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import requests


HOST = "sms.tencentcloudapi.com"
SERVICE = "sms"
VERSION = "2021-01-11"
ACTION = "SendSms"
ENDPOINT = f"https://{HOST}"


def _sign(secret_key: str, date: str, service: str) -> bytes:
    k_date = hmac.new(("TC3" + secret_key).encode("utf-8"), date.encode("utf-8"), hashlib.sha256).digest()
    k_service = hmac.new(k_date, service.encode("utf-8"), hashlib.sha256).digest()
    k_signing = hmac.new(k_service, b"tc3_request", hashlib.sha256).digest()
    return k_signing


def _build_headers(secret_id: str, secret_key: str, region: str, body: str) -> Dict[str, str]:
    ts = int(time.time())
    date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = (
        "POST\n"
        "/\n"
        "\n"
        f"content-type:application/json\nhost:{HOST}\nx-tc-action:{ACTION.lower()}\n"
        "\n"
        "content-type;host;x-tc-action\n"
        f"{payload_hash}"
    )
    canonical_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    credential_scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = f"TC3-HMAC-SHA256\n{ts}\n{credential_scope}\n{canonical_hash}"

    signing_key = _sign(secret_key, date, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders=content-type;host;x-tc-action, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "Host": HOST,
        "X-TC-Action": ACTION,
        "X-TC-Timestamp": str(ts),
        "X-TC-Version": VERSION,
        "X-TC-Region": region,
    }


def send(
    cfg: Dict[str, Any],
    phone: str,
    template_id: str,
    sign_name: str,
    template_params: List[str],
) -> Tuple[str, str]:
    """返回 (status, err_msg)。status: success / mocked / error"""
    secret_id = (cfg or {}).get("tencent_secret_id", "").strip()
    secret_key = (cfg or {}).get("tencent_secret_key", "").strip()
    sdk_app_id = (cfg or {}).get("tencent_sdk_app_id", "").strip()
    region = (cfg or {}).get("tencent_region", "ap-guangzhou").strip()

    if not (secret_id and secret_key and sdk_app_id and template_id and sign_name):
        return "mocked", "credentials or template/sign not configured"

    if not phone:
        return "error", "phone empty"

    phone_e164 = phone if phone.startswith("+") else ("+86" + phone)

    body_obj = {
        "PhoneNumberSet": [phone_e164],
        "SmsSdkAppId": sdk_app_id,
        "SignName": sign_name,
        "TemplateId": template_id,
        "TemplateParamSet": [str(x) for x in template_params],
    }
    body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    headers = _build_headers(secret_id, secret_key, region, body)

    try:
        r = requests.post(ENDPOINT, data=body.encode("utf-8"), headers=headers, timeout=10)
        data = r.json()
    except Exception as e:
        return "error", f"http: {e}"

    resp = data.get("Response", {})
    if "Error" in resp:
        return "error", f"{resp['Error'].get('Code')}: {resp['Error'].get('Message')}"

    statuses = resp.get("SendStatusSet", [])
    if statuses and statuses[0].get("Code") == "Ok":
        return "success", ""
    return "error", json.dumps(statuses, ensure_ascii=False) if statuses else "unknown"
