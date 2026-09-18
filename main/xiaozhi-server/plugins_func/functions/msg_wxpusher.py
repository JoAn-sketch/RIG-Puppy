"""WxPusher 微信公众号推送。

凭证：app_token（你扫码注册应用拿到的）。
收件人：UID（每个子女各自扫码关注后获得）。
"""

from typing import Dict, Any, Tuple
import requests


ENDPOINT = "https://wxpusher.zjiecode.com/api/send/message"


def send(cfg: Dict[str, Any], uid: str, content: str, summary: str = "") -> Tuple[str, str]:
    """返回 (status, err_msg)。"""
    app_token = (cfg or {}).get("wxpusher_app_token", "").strip()

    if not app_token:
        return "mocked", "wxpusher app_token not configured"
    if not uid:
        return "error", "uid empty"

    payload = {
        "appToken": app_token,
        "content": content,
        "summary": (summary or content)[:20],
        "contentType": 1,
        "uids": [uid],
    }
    try:
        r = requests.post(ENDPOINT, json=payload, timeout=10)
        data = r.json()
    except Exception as e:
        return "error", f"http: {e}"

    if data.get("code") == 1000:
        results = data.get("data") or []
        if results and results[0].get("code") == 1000:
            return "success", ""
        return "error", str(results)
    return "error", f"{data.get('code')}: {data.get('msg')}"
