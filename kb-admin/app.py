"""
知识库管理小后端 - 代理智谱 API + 监控面板 + Prompt 版本化
"""
import os
import json
import time
import base64
import subprocess
import shutil
import sys
import importlib.util
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file, Response
import requests
from app_messaging_patch import register_messaging_routes

ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
ADMIN_USER = os.environ.get("KB_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("KB_ADMIN_PASS", "")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
FILES_DIR = os.path.join(DATA_DIR, "files")
PROMPTS_DIR = os.path.join(DATA_DIR, "prompts")
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")
H = {"Authorization": f"Bearer {ZHIPU_API_KEY}"}

DB_CONTAINER = "xiaozhi-esp32-server-db"
DB_NAME = "xiaozhi_esp32_server"
DB_PASS = "123456"
DINGYIGUO_AGENT_ID = "1822c2babf1b44cca6b25d0bdebc796f"

SCENE_ROUTER_ROOT = os.path.join(
    os.path.dirname(__file__),
    "..",
    "xiaozhi-esp32-server-main",
    "main",
    "xiaozhi-server",
)
if SCENE_ROUTER_ROOT not in sys.path:
    sys.path.insert(0, SCENE_ROUTER_ROOT)

SCENE_ROUTER_RULES_PATH = os.path.join(
    SCENE_ROUTER_ROOT,
    "core",
    "scene_router",
    "rules.py",
)
SCENE_ROUTER_POLICY_PATH = os.path.join(
    SCENE_ROUTER_ROOT,
    "core",
    "scene_router",
    "policy.py",
)

try:
    from core.scene_router import ChildProfile, DialogState, SceneRouter, SceneRouterInput, SignalState
except Exception:
    SceneRouter = None
    ChildProfile = None
    DialogState = None
    SceneRouterInput = None
    SignalState = None

SCENE_ROUTER = SceneRouter() if SceneRouter else None

def check_auth(u, p):
    return u == ADMIN_USER and p == ADMIN_PASS and ADMIN_PASS != ""


def requires_auth(f):
    @wraps(f)
    def wrapped(*a, **kw):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                "Auth required", 401, {"WWW-Authenticate": 'Basic realm="kb-admin"'}
            )
        return f(*a, **kw)
    return wrapped


def _route_scene_for_text(user_text, history):
    if not SCENE_ROUTER or not user_text:
        return None

    turn_index = 0
    last_scene = None
    for item in history or []:
        if item.get("role") == "user":
            turn_index += 1
            scene = item.get("scene") or {}
            if scene.get("primary_scene"):
                last_scene = scene.get("primary_scene")

    routed = SCENE_ROUTER.route(
        SceneRouterInput(
            text=user_text,
            child_profile=ChildProfile(age_band="6-8"),
            dialog_state=DialogState(
                current_scene=last_scene,
                turn_index=turn_index,
            ),
            signals=SignalState(
                emotion_hint="neutral",
                interruption=False,
                silence_ms=0,
                vlm_tags=[],
            ),
        )
    )
    return {
        "primary_scene": routed.primary_scene,
        "subscene": routed.subscene,
        "secondary_scene": routed.secondary_scene,
        "risk_level": routed.risk_level,
        "emotion_state": routed.emotion_state,
        "age_band": routed.age_band,
        "policy_profile": routed.policy_profile,
        "should_use_rag": routed.should_use_rag,
        "should_use_memory": routed.should_use_memory,
        "should_use_vlm": routed.should_use_vlm,
        "should_escalate_parent": routed.should_escalate_parent,
        "should_force_safe_template": routed.should_force_safe_template,
        "confidence": routed.confidence,
        "reason_codes": routed.reason_codes,
    }


def _load_scene_router_snapshot():
    rules_spec = importlib.util.spec_from_file_location(
        f"scene_router_rules_snapshot_{int(time.time() * 1000)}",
        SCENE_ROUTER_RULES_PATH,
    )
    policy_spec = importlib.util.spec_from_file_location(
        f"scene_router_policy_snapshot_{int(time.time() * 1000)}",
        SCENE_ROUTER_POLICY_PATH,
    )
    if rules_spec is None or rules_spec.loader is None:
        raise RuntimeError("scene router rules load failed")
    if policy_spec is None or policy_spec.loader is None:
        raise RuntimeError("scene router policy load failed")
    rules_module = importlib.util.module_from_spec(rules_spec)
    policy_module = importlib.util.module_from_spec(policy_spec)
    rules_spec.loader.exec_module(rules_module)
    policy_spec.loader.exec_module(policy_module)

    scene_rules = getattr(rules_module, "SCENE_RULES", {}) or {}
    default_scene = getattr(rules_module, "DEFAULT_SCENE", {}) or {}
    policy_specs = getattr(policy_module, "SCENE_POLICY_SPECS", {}) or {}
    subscene_hints = getattr(policy_module, "SUBSCENE_HINTS", {}) or {}
    age_style_hints = getattr(policy_module, "AGE_STYLE_HINTS", {}) or {}
    scenes = []
    for scene_name, scene_rule in scene_rules.items():
        subscene_rules = scene_rule.get("subscene_rules") or []
        policy_spec_value = policy_specs.get(scene_name)
        policy_data = None
        if policy_spec_value is not None:
            policy_data = {
                "goal": getattr(policy_spec_value, "goal", ""),
                "tone": getattr(policy_spec_value, "tone", ""),
                "response_style": list(getattr(policy_spec_value, "response_style", []) or []),
                "ask_strategy": list(getattr(policy_spec_value, "ask_strategy", []) or []),
                "avoid": list(getattr(policy_spec_value, "avoid", []) or []),
                "exit_condition": getattr(policy_spec_value, "exit_condition", ""),
            }
        scenes.append({
            "scene_name": scene_name,
            "risk_level": scene_rule.get("risk_level") or "low",
            "policy_profile": scene_rule.get("policy_profile") or "",
            "should_force_safe_template": bool(scene_rule.get("should_force_safe_template")),
            "should_use_memory": bool(scene_rule.get("should_use_memory")),
            "should_use_rag": bool(scene_rule.get("should_use_rag")),
            "should_use_vlm": bool(scene_rule.get("should_use_vlm")),
            "should_escalate_parent": bool(scene_rule.get("should_escalate_parent")),
            "policy": policy_data,
            "subscenes": [
                {
                    "subscene": subscene,
                    "keywords": keywords,
                    "hint": subscene_hints.get(subscene) or "",
                }
                for subscene, keywords in subscene_rules
            ],
        })

    return {
        "scenes": scenes,
        "default_scene": default_scene,
        "rules_path": SCENE_ROUTER_RULES_PATH,
        "policy_path": SCENE_ROUTER_POLICY_PATH,
        "age_style_hints": age_style_hints,
        "scene_count": len(scenes),
    }


register_messaging_routes(app, requires_auth)


def mysql_query(sql):
    """通过 docker exec 跑 mysql 查询,返回行列表(dict)"""
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", f"-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "--batch", "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 and "Warning" not in r.stderr:
        raise RuntimeError(f"mysql err: {r.stderr[:300]}")
    lines = [l for l in r.stdout.split("\n") if l.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        rows.append(dict(zip(headers, cells)))
    return rows


def mysql_exec(sql):
    """跑 update/insert,不返回行"""
    cmd = ["docker", "exec", DB_CONTAINER, "mysql", f"-uroot", f"-p{DB_PASS}",
           DB_NAME, "--default-character-set=utf8mb4", "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 and "Warning" not in r.stderr:
        raise RuntimeError(f"mysql err: {r.stderr[:300]}")
    return True


@app.route("/")
@requires_auth
def index():
    return send_from_directory("static", "index.html")


@app.route("/scene-router")
@requires_auth
def scene_router_page():
    return send_from_directory("static", "scene-router.html")


@app.route("/monitor")
@requires_auth
def monitor_page():
    return send_from_directory("static", "monitor.html")


@app.route("/prompt")
@requires_auth
def prompt_page():
    return send_from_directory("static", "prompt.html")


# ============= 知识库 =============

@app.route("/api/knowledge")
@requires_auth
def list_kb():
    r = requests.get(f"{ZHIPU_BASE}/knowledge", headers=H, timeout=15)
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/knowledge", methods=["POST"])
@requires_auth
def create_kb():
    body = request.get_json(force=True)
    payload = {
        "name": body.get("name", "未命名"),
        "description": body.get("description", ""),
        "embedding_id": body.get("embedding_id", 3),
    }
    r = requests.post(
        f"{ZHIPU_BASE}/knowledge",
        headers={**H, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/knowledge/<kb_id>", methods=["DELETE"])
@requires_auth
def delete_kb(kb_id):
    r = requests.delete(f"{ZHIPU_BASE}/knowledge/{kb_id}", headers=H, timeout=15)
    return Response(r.text, status=r.status_code, mimetype="application/json")


# ============= 文件 =============

@app.route("/api/files")
@requires_auth
def list_files():
    kb_id = request.args.get("knowledge_id", "")
    r = requests.get(
        f"{ZHIPU_BASE}/files",
        headers=H,
        params={"purpose": "retrieval", "knowledge_id": kb_id},
        timeout=15,
    )
    data = r.json() if r.status_code == 200 else {}
    if "list" in data:
        for f in data["list"]:
            local = os.path.join(FILES_DIR, kb_id, f.get("id", ""))
            f["has_local"] = os.path.exists(local)
    return jsonify(data) if r.status_code == 200 else Response(r.text, status=r.status_code)


@app.route("/api/files", methods=["POST"])
@requires_auth
def upload_file():
    kb_id = request.form.get("knowledge_id", "")
    f = request.files.get("file")
    if not kb_id or not f:
        return jsonify({"error": "missing knowledge_id or file"}), 400

    raw = f.stream.read()
    files = {"file": (f.filename, raw, f.mimetype or "application/octet-stream")}
    data = {"purpose": "retrieval", "knowledge_id": kb_id}
    r = requests.post(
        f"{ZHIPU_BASE}/files", headers=H, files=files, data=data, timeout=120
    )
    try:
        resp = r.json()
        if resp.get("successInfos"):
            kb_local = os.path.join(FILES_DIR, kb_id)
            os.makedirs(kb_local, exist_ok=True)
            for info in resp["successInfos"]:
                fid = info.get("fileId") or info.get("documentId") or info.get("id")
                if fid:
                    with open(os.path.join(kb_local, fid), "wb") as out:
                        out.write(raw)
                    meta = {"name": f.filename, "uploaded_at": int(time.time()),
                            "size": len(raw), "mime": f.mimetype}
                    with open(os.path.join(kb_local, fid + ".meta.json"), "w", encoding="utf-8") as m:
                        json.dump(meta, m, ensure_ascii=False)
    except Exception:
        pass
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/files/<file_id>", methods=["DELETE"])
@requires_auth
def delete_file(file_id):
    r = requests.delete(f"{ZHIPU_BASE}/files/{file_id}", headers=H, timeout=15)
    for kb_dir in os.listdir(FILES_DIR):
        p = os.path.join(FILES_DIR, kb_dir, file_id)
        if os.path.exists(p):
            try:
                os.remove(p)
                mp = p + ".meta.json"
                if os.path.exists(mp):
                    os.remove(mp)
            except Exception:
                pass
    return Response(r.text, status=r.status_code, mimetype="application/json")


@app.route("/api/files/<file_id>/download")
@requires_auth
def download_file(file_id):
    kb_id = request.args.get("knowledge_id", "")
    p = os.path.join(FILES_DIR, kb_id, file_id)
    mp = p + ".meta.json"
    if not os.path.exists(p):
        return jsonify({"error": "本地副本不存在(此文件在 kb-admin 升级前上传,无副本)"}), 404
    name = file_id
    if os.path.exists(mp):
        try:
            with open(mp, encoding="utf-8") as m:
                name = json.load(m).get("name", file_id)
        except Exception:
            pass
    return send_file(p, as_attachment=True, download_name=name)


@app.route("/api/files/<file_id>/preview")
@requires_auth
def preview_file(file_id):
    kb_id = request.args.get("knowledge_id", "")
    p = os.path.join(FILES_DIR, kb_id, file_id)
    if not os.path.exists(p):
        return jsonify({"error": "本地副本不存在"}), 404
    try:
        with open(p, "rb") as f:
            raw = f.read(64 * 1024)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")
        return jsonify({"text": text, "truncated": os.path.getsize(p) > 64 * 1024})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= 检索测试 =============

@app.route("/api/test", methods=["POST"])
@requires_auth
def test_query():
    body = request.get_json(force=True)
    kb_id = body.get("knowledge_id", "")
    question = body.get("question", "")
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": "严格基于知识库回答；若没有相关信息，说“知识库中没有”。"},
            {"role": "user", "content": question},
        ],
        "tools": [{"type": "retrieval", "retrieval": {"knowledge_id": kb_id}}],
    }
    r = requests.post(
        f"{ZHIPU_BASE}/chat/completions",
        headers={**H, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    return Response(r.text, status=r.status_code, mimetype="application/json")


# ============= D: 监控面板 =============

@app.route("/api/health")
@requires_auth
def health():
    out = {"ts": int(time.time()), "containers": [], "memory": {}, "disk": {}, "errors": {}}

    try:
        r = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"],
            capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().split("\n"):
            if not line: continue
            parts = line.split("|")
            if len(parts) == 4:
                out["containers"].append({
                    "name": parts[0], "cpu": parts[1],
                    "mem": parts[2], "mem_perc": parts[3],
                })
    except Exception as e:
        out["containers_error"] = str(e)

    try:
        r = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if line.startswith("Mem:"):
                f = line.split()
                out["memory"] = {"total_mb": int(f[1]), "used_mb": int(f[2]),
                                 "free_mb": int(f[3]), "available_mb": int(f[6])}
            elif line.startswith("Swap:"):
                f = line.split()
                out["memory"]["swap_total_mb"] = int(f[1])
                out["memory"]["swap_used_mb"] = int(f[2])
    except Exception as e:
        out["memory_error"] = str(e)

    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 2:
            f = lines[1].split()
            out["disk"] = {"total": f[1], "used": f[2], "avail": f[3], "use_pct": f[4]}
    except Exception as e:
        out["disk_error"] = str(e)

    try:
        r = subprocess.run(
            ["docker", "logs", "--since", "1h", "xiaozhi-esp32-server"],
            capture_output=True, text=True, timeout=15)
        all_log = (r.stdout or "") + (r.stderr or "")
        out["errors"]["server_1h"] = {
            "ERROR": all_log.count(" ERROR ") + all_log.count("[ERROR]"),
            "WARNING": all_log.count(" WARNING ") + all_log.count("[WARNING]"),
            "asr_fail": all_log.lower().count("asr") + all_log.lower().count("paraformer"),
            "tts_fail": sum(1 for l in all_log.split("\n") if "tts" in l.lower() and ("error" in l.lower() or "timeout" in l.lower() or "fail" in l.lower())),
        }
    except Exception as e:
        out["errors"]["server_error"] = str(e)

    try:
        r = requests.get("http://localhost:8003/xiaozhi/ota/", timeout=5)
        out["ota_status"] = r.status_code
    except Exception as e:
        out["ota_status"] = f"ERR: {str(e)[:100]}"

    return jsonify(out)


@app.route("/api/health/logs")
@requires_auth
def recent_logs():
    container = request.args.get("container", "xiaozhi-esp32-server")
    lines = request.args.get("lines", "100")
    level = request.args.get("level", "")
    try:
        r = subprocess.run(
            ["docker", "logs", "--tail", lines, container],
            capture_output=True, text=True, timeout=15)
        log = (r.stdout or "") + (r.stderr or "")
        if level:
            log = "\n".join(l for l in log.split("\n") if level.upper() in l.upper())
        return jsonify({"log": log[-50000:]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============= E: Prompt 版本化 =============

@app.route("/api/agents")
@requires_auth
def list_agents():
    try:
        rows = mysql_query("SELECT id, agent_name, LENGTH(system_prompt) as plen, LENGTH(summary_memory) as mlen FROM ai_agent ORDER BY agent_name")
        return jsonify({"list": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_id>/prompt")
@requires_auth
def get_current_prompt(agent_id):
    try:
        agent_id = agent_id.replace("'", "")
        rows = mysql_query(f"SELECT system_prompt, agent_name FROM ai_agent WHERE id='{agent_id}'")
        if not rows:
            return jsonify({"error": "agent 不存在"}), 404
        return jsonify({"system_prompt": rows[0].get("system_prompt", ""),
                        "agent_name": rows[0].get("agent_name", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompt-history/<agent_id>")
@requires_auth
def list_prompt_history(agent_id):
    d = os.path.join(PROMPTS_DIR, agent_id)
    if not os.path.isdir(d):
        return jsonify({"list": []})
    items = []
    for fn in sorted(os.listdir(d), reverse=True):
        if not fn.endswith(".json"): continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                meta = json.load(f)
            meta["filename"] = fn
            items.append(meta)
        except Exception:
            pass
    return jsonify({"list": items})


@app.route("/api/prompt-history/<agent_id>/<filename>")
@requires_auth
def get_prompt_version(agent_id, filename):
    if "/" in filename or ".." in filename:
        return jsonify({"error": "bad filename"}), 400
    p = os.path.join(PROMPTS_DIR, agent_id, filename)
    if not os.path.exists(p):
        return jsonify({"error": "版本不存在"}), 404
    with open(p, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/agents/<agent_id>/prompt", methods=["POST"])
@requires_auth
def save_prompt(agent_id):
    """保存当前 prompt 为快照,然后更新数据库"""
    body = request.get_json(force=True)
    new_prompt = body.get("system_prompt", "")
    note = body.get("note", "")
    if not new_prompt:
        return jsonify({"error": "system_prompt 必填"}), 400
    try:
        agent_id_safe = agent_id.replace("'", "")
        rows = mysql_query(f"SELECT system_prompt FROM ai_agent WHERE id='{agent_id_safe}'")
        if not rows:
            return jsonify({"error": "agent 不存在"}), 404
        old = rows[0].get("system_prompt", "")

        d = os.path.join(PROMPTS_DIR, agent_id_safe)
        os.makedirs(d, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        snap = {"agent_id": agent_id_safe, "saved_at": int(time.time()),
                "saved_at_str": ts, "system_prompt": old, "note": note,
                "size": len(old)}
        with open(os.path.join(d, f"{ts}.json"), "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)

        escaped = new_prompt.replace("\\", "\\\\").replace("'", "''")
        mysql_exec(f"UPDATE ai_agent SET system_prompt='{escaped}', updated_at=NOW() WHERE id='{agent_id_safe}'")
        return jsonify({"ok": True, "snapshot": ts, "old_size": len(old), "new_size": len(new_prompt)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompt-history/<agent_id>/<filename>/restore", methods=["POST"])
@requires_auth
def restore_prompt(agent_id, filename):
    if "/" in filename or ".." in filename:
        return jsonify({"error": "bad filename"}), 400
    p = os.path.join(PROMPTS_DIR, agent_id, filename)
    if not os.path.exists(p):
        return jsonify({"error": "版本不存在"}), 404
    try:
        with open(p, encoding="utf-8") as f:
            snap = json.load(f)
        old_prompt = snap.get("system_prompt", "")
        if not old_prompt:
            return jsonify({"error": "该快照无 prompt 内容"}), 400

        agent_id_safe = agent_id.replace("'", "")
        rows = mysql_query(f"SELECT system_prompt FROM ai_agent WHERE id='{agent_id_safe}'")
        if rows:
            cur = rows[0].get("system_prompt", "")
            d = os.path.join(PROMPTS_DIR, agent_id_safe)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = {"agent_id": agent_id_safe, "saved_at": int(time.time()),
                      "saved_at_str": ts, "system_prompt": cur,
                      "note": f"自动备份(回滚到 {filename} 之前)", "size": len(cur)}
            with open(os.path.join(d, f"{ts}.json"), "w", encoding="utf-8") as f:
                json.dump(backup, f, ensure_ascii=False, indent=2)

        escaped = old_prompt.replace("\\", "\\\\").replace("'", "''")
        mysql_exec(f"UPDATE ai_agent SET system_prompt='{escaped}', updated_at=NOW() WHERE id='{agent_id_safe}'")
        return jsonify({"ok": True, "restored_from": filename, "size": len(old_prompt)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompt-history/<agent_id>/<filename>", methods=["DELETE"])
@requires_auth
def delete_prompt_version(agent_id, filename):
    if "/" in filename or ".." in filename:
        return jsonify({"error": "bad filename"}), 400
    p = os.path.join(PROMPTS_DIR, agent_id, filename)
    if os.path.exists(p):
        os.remove(p)
    return jsonify({"ok": True})




# ============= 长期陪伴画像 =============

@app.route("/portrait")
@requires_auth
def portrait_page():
    return send_from_directory("static", "portrait.html")


@app.route("/mood")
@requires_auth
def mood_page():
    return send_from_directory("static", "mood.html")


@app.route("/api/mood")
@requires_auth
def api_mood():
    agent_id = request.args.get("agent_id", "")
    days = int(request.args.get("days", 14))
    if not agent_id:
        return jsonify([])
    rows = mysql_query(f"""SELECT mood_date, dominant_emotion, emotion_scores, summary, msg_count
        FROM rl_mood_daily WHERE agent_id='{agent_id}'
        ORDER BY mood_date DESC LIMIT {days}""")
    for r in rows:
        if r.get("emotion_scores") and r["emotion_scores"] != "NULL":
            try:
                r["emotion_scores"] = json.loads(r["emotion_scores"])
            except Exception:
                pass
        r["msg_count"] = int(r.get("msg_count", 0))
    return jsonify(rows)


@app.route("/api/portrait/<agent_id>")
@requires_auth
def get_portrait(agent_id):
    """返回注入对话用的精简上下文：长期画像 + 近3天摘要 + 今日未完成提醒"""
    try:
        agent_id = agent_id.replace("'", "")
        profile = mysql_query(
            f"SELECT agent_id, schedule_profile, medicine_profile, companion_prefs, "
            f"mood_profile, fraud_profile, health_profile, recent_trends, tomorrow_strategy, "
            f"data_days, last_updated FROM rl_companion_profile WHERE agent_id='{agent_id}'"
        )
        recent = mysql_query(
            f"SELECT summary_date, overall_status, mood_companion, tomorrow_strategy, "
            f"medicine_status, fraud_risk, health_signals, family_note FROM rl_daily_summary "
            f"WHERE agent_id='{agent_id}' ORDER BY summary_date DESC LIMIT 3"
        )
        pending = mysql_query(
            f"SELECT title, remind_time FROM rl_reminders "
            f"WHERE agent_id='{agent_id}' AND enabled=1 "
            f"AND (last_fired_at IS NULL OR DATE(last_fired_at) < CURDATE())"
        )
        return jsonify({
            "profile": profile[0] if profile else None,
            "recent_summaries": recent,
            "pending_reminders": pending,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/portrait/<agent_id>/summaries")
@requires_auth
def list_summaries(agent_id):
    """列出历史每日摘要，供管理页查看"""
    try:
        agent_id = agent_id.replace("'", "")
        days = request.args.get("days", "30")
        rows = mysql_query(
            f"SELECT summary_date, overall_status, mood_companion, tomorrow_strategy, "
            f"medicine_status, fraud_risk, health_signals, family_note, raw_event_count, generated_at "
            f"FROM rl_daily_summary WHERE agent_id='{agent_id}' "
            f"ORDER BY summary_date DESC LIMIT {int(days)}"
        )
        return jsonify({"list": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/portrait/<agent_id>/events")
@requires_auth
def list_care_events(agent_id):
    """列出原始事件日志"""
    try:
        agent_id = agent_id.replace("'", "")
        days = request.args.get("days", "7")
        rows = mysql_query(
            f"SELECT event_type, event_time, summary, risk_level, handled, created_at "
            f"FROM rl_care_events WHERE agent_id='{agent_id}' "
            f"AND event_time >= DATE_SUB(NOW(), INTERVAL {int(days)} DAY) "
            f"ORDER BY event_time DESC LIMIT 200"
        )
        return jsonify({"list": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== 模式管理 ==========

@app.route("/modes")
@requires_auth
def modes_page():
    return send_from_directory("static", "modes.html")


@app.route("/api/knowledge-bases")
@requires_auth
def list_knowledge_bases():
    try:
        rows = mysql_query("SELECT id, name, description, is_active FROM rl_knowledge_base WHERE is_active = 1 ORDER BY create_date")
        for r in rows:
            r["is_active"] = int(r.get("is_active", 1))
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/modes")
@requires_auth
def list_modes():
    try:
        rows = mysql_query(
            "SELECT id, agent_id, mode_name, mode_code, system_prompt, "
            "is_default, sort, context_modules, knowledge_ids FROM ai_agent_mode ORDER BY sort"
        )
        for r in rows:
            if r.get("context_modules") and r["context_modules"] != "NULL":
                r["context_modules"] = json.loads(r["context_modules"])
            else:
                r["context_modules"] = {"time": True, "memory": True, "weather": True, "location": True, "dynamic_context": True}
            if r.get("knowledge_ids") and r["knowledge_ids"] != "NULL":
                r["knowledge_ids"] = json.loads(r["knowledge_ids"])
            else:
                r["knowledge_ids"] = []
            r["is_default"] = int(r.get("is_default", 0))
            r["sort"] = int(r.get("sort", 0))
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/modes/<mode_id>", methods=["PUT"])
@requires_auth
def update_mode(mode_id):
    try:
        data = request.json
        updates = []
        if "system_prompt" in data:
            prompt = data["system_prompt"].replace("'", "\\'").replace("\\", "\\\\")
            updates.append(f"system_prompt = '{prompt}'")
        if "context_modules" in data:
            modules_json = json.dumps(data["context_modules"]).replace("'", "\\'")
            updates.append(f"context_modules = '{modules_json}'")
        if "knowledge_ids" in data:
            kids_json = json.dumps(data["knowledge_ids"]).replace("'", "\\'")
            updates.append(f"knowledge_ids = '{kids_json}'")
        if "mode_name" in data:
            updates.append(f"mode_name = '{data['mode_name']}'")
        if "mode_code" in data:
            updates.append(f"mode_code = '{data['mode_code']}'")
        if not updates:
            return jsonify({"error": "没有要更新的字段"}), 400
        sql = f"UPDATE ai_agent_mode SET {', '.join(updates)} WHERE id = '{mode_id}'"
        mysql_exec(sql)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/modes/<mode_id>/default", methods=["POST"])
@requires_auth
def set_default_mode(mode_id):
    try:
        # 先查 agent_id
        rows = mysql_query(f"SELECT agent_id FROM ai_agent_mode WHERE id = '{mode_id}'")
        if not rows:
            return jsonify({"error": "模式不存在"}), 404
        agent_id = rows[0]["agent_id"]
        # 清除该 agent 所有默认
        mysql_exec(f"UPDATE ai_agent_mode SET is_default = 0 WHERE agent_id = '{agent_id}'")
        # 设置新默认
        mysql_exec(f"UPDATE ai_agent_mode SET is_default = 1 WHERE id = '{mode_id}'")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/modes/<mode_id>", methods=["DELETE"])
@requires_auth
def delete_mode(mode_id):
    try:
        rows = mysql_query(f"SELECT is_default FROM ai_agent_mode WHERE id = '{mode_id}'")
        if rows and int(rows[0].get("is_default", 0)) == 1:
            return jsonify({"error": "不能删除默认模式"}), 400
        mysql_exec(f"DELETE FROM ai_agent_mode WHERE id = '{mode_id}'")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== 时间段调度 ==========

@app.route("/api/schedules")
@requires_auth
def list_schedules():
    try:
        rows = mysql_query(
            "SELECT s.id, s.agent_id, s.mode_id, s.start_time, s.end_time, s.is_active, m.mode_name "
            "FROM rl_mode_schedule s LEFT JOIN ai_agent_mode m ON s.mode_id = m.id "
            "ORDER BY s.start_time"
        )
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/schedules", methods=["POST"])
@requires_auth
def add_schedule():
    try:
        data = request.json
        mode_id = data["mode_id"]
        start = data["start_time"]
        end = data["end_time"]
        # 取 agent_id from mode
        rows = mysql_query(f"SELECT agent_id FROM ai_agent_mode WHERE id = '{mode_id}'")
        if not rows:
            return jsonify({"error": "模式不存在"}), 404
        agent_id = rows[0]["agent_id"]
        mysql_exec(
            f"INSERT INTO rl_mode_schedule (agent_id, mode_id, start_time, end_time) "
            f"VALUES ('{agent_id}', '{mode_id}', '{start}', '{end}')"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/schedules/<int:sched_id>", methods=["DELETE"])
@requires_auth
def delete_schedule(sched_id):
    try:
        mysql_exec(f"DELETE FROM rl_mode_schedule WHERE id = {sched_id}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== 画像优化 Prompt ==========

@app.route("/api/modes/<mode_id>/optimize", methods=["POST"])
@requires_auth
def optimize_mode_prompt(mode_id):
    try:
        # 获取模式信息
        mode_rows = mysql_query(
            f"SELECT mode_name, system_prompt, agent_id FROM ai_agent_mode WHERE id = '{mode_id}'"
        )
        if not mode_rows:
            return jsonify({"error": "模式不存在"}), 404
        mode = mode_rows[0]

        # 获取用户画像
        portrait_rows = mysql_query(
            f"SELECT portrait_text FROM rl_portrait WHERE agent_id = '{mode['agent_id']}' "
            f"ORDER BY update_date DESC LIMIT 1"
        )
        portrait = portrait_rows[0]["portrait_text"] if portrait_rows else "暂无画像数据"

        # 获取基础 prompt
        agent_rows = mysql_query(
            f"SELECT system_prompt FROM ai_agent WHERE id = '{mode['agent_id']}'"
        )
        base_prompt = agent_rows[0]["system_prompt"] if agent_rows else ""

        # 调用智谱 LLM 生成优化建议
        llm_prompt = f"""你是一个 AI 对话系统的 prompt 优化专家。

当前有一个陪伴独居老人的 AI 机器狗"丁一锅"，现在要优化它的"{mode['mode_name']}"模式的 prompt。

基础人设（始终保留，不需要修改）：
{base_prompt[:500]}

当前模式 prompt：
{mode['system_prompt']}

用户画像数据：
{portrait}

请根据画像中的信息（用户习惯、健康状况、性格特点、生活规律等），给出针对性的 prompt 优化建议。
格式：
1. 指出当前 prompt 可以根据画像数据增加的个性化内容
2. 给出具体的修改建议（哪里改、改成什么）
3. 给出优化后的完整模式 prompt

注意：建议要实用、具体，不要泛泛而谈。"""

        r = requests.post(
            f"{ZHIPU_BASE}/chat/completions",
            headers=H,
            json={
                "model": "glm-4-flash",
                "messages": [{"role": "user", "content": llm_prompt}],
            },
            timeout=30,
        )
        result = r.json()
        suggestion = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return jsonify({"suggestion": suggestion or "未能生成建议"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== 调试台 API =====

@app.route("/debug")
@requires_auth
def debug_page():
    return send_from_directory("static", "debug.html")


@app.route("/api/debug/config")
@requires_auth
def api_debug_config():
    rows = mysql_query("SELECT config_key, config_value, description FROM rl_system_config ORDER BY config_key")
    return jsonify(rows)


@app.route("/api/debug/config/<key>", methods=["PUT"])
@requires_auth
def api_debug_config_update(key):
    val = request.json.get("value", "0")
    mysql_exec(f"UPDATE rl_system_config SET config_value='{val}' WHERE config_key='{key}'")
    return jsonify({"ok": True})


@app.route("/api/debug/strategy/today")
@requires_auth
def api_debug_strategy_today():
    today = datetime.now().strftime("%Y-%m-%d")
    rows = mysql_query(f"SELECT strategy_text, created_at FROM rl_daily_strategy WHERE strategy_date='{today}' LIMIT 1")
    if rows:
        return jsonify(rows[0])
    return jsonify({})


@app.route("/api/debug/strategy/history")
@requires_auth
def api_debug_strategy_history():
    rows = mysql_query("SELECT strategy_date, strategy_text, created_at FROM rl_daily_strategy ORDER BY strategy_date DESC LIMIT 14")
    return jsonify(rows)


@app.route("/api/debug/strategy/generate", methods=["POST"])
@requires_auth
def api_debug_strategy_generate():
    try:
        agent_id = "1822c2babf1b44cca6b25d0bdebc796f"
        today = datetime.now().strftime("%Y-%m-%d")

        # Gather data
        portrait_rows = mysql_query(f"SELECT profile_json FROM rl_companion_profile WHERE agent_id='{agent_id}' ORDER BY updated_at DESC LIMIT 1")
        portrait = portrait_rows[0]["profile_json"][:1500] if portrait_rows else "{}"

        mood_rows = mysql_query(f"SELECT mood_date, dominant_emotion, summary FROM rl_mood_daily WHERE agent_id='{agent_id}' ORDER BY mood_date DESC LIMIT 3")
        event_rows = mysql_query(f"SELECT event_type, summary FROM rl_care_events WHERE agent_id='{agent_id}' AND ts >= DATE_SUB(NOW(), INTERVAL 3 DAY) ORDER BY ts DESC LIMIT 15")
        reminder_rows = mysql_query(f"SELECT title, remind_time, type FROM rl_reminders WHERE agent_id='{agent_id}' AND status IN ('active','pending') LIMIT 10")

        import json as jlib
        weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
        weekday = weekdays[datetime.now().weekday()]

        llm_prompt = f"""你是老年陪伴AI的策略引擎。根据以下数据生成"今日陪伴策略"。

要求：
1. 行为指令，不是信息描述。告诉AI"做什么"
2. 200字以内，分条
3. 涵盖：语气/动作频率/重点关注/主动话题/风险防范
4. 不能包含"画像""数据""分析""系统发现"
5. 用"铲屎官"称呼老人

今天 {today} {weekday}

【画像】{portrait[:1200]}
【近期情绪】{jlib.dumps(mood_rows, ensure_ascii=False)[:400]}
【活跃提醒】{jlib.dumps(reminder_rows, ensure_ascii=False)[:400]}
【近期事件】{jlib.dumps(event_rows, ensure_ascii=False)[:600]}

直接输出策略。"""

        r = requests.post(
            f"{ZHIPU_BASE}/chat/completions",
            headers=H,
            json={"model": "glm-4-flash", "messages": [{"role": "user", "content": llm_prompt}], "temperature": 0.7, "max_tokens": 500},
            timeout=30,
        )
        result = r.json()
        strategy = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if strategy:
            safe = strategy.replace("'", "\\'")
            safe_portrait = portrait[:300].replace("'", "\\'")
            mysql_exec(f"""INSERT INTO rl_daily_strategy (agent_id, strategy_date, strategy_text, source_portrait)
                VALUES ('{agent_id}', '{today}', '{safe}', '{safe_portrait}')
                ON DUPLICATE KEY UPDATE strategy_text='{safe}'""")

        return jsonify({"strategy": strategy or "生成失败"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug/prompt-logs")
@requires_auth
def api_debug_prompt_logs():
    rows = mysql_query("SELECT id, device_mac, timestamp, CHAR_LENGTH(system_prompt) as prompt_length FROM rl_prompt_log ORDER BY timestamp DESC LIMIT 30")
    return jsonify(rows)


@app.route("/api/debug/prompt-logs/<int:log_id>")
@requires_auth
def api_debug_prompt_log_detail(log_id):
    rows = mysql_query(f"SELECT id, device_mac, timestamp, system_prompt FROM rl_prompt_log WHERE id={log_id}")
    if rows:
        return jsonify(rows[0])
    return jsonify({}), 404


@app.route("/api/debug/chat-history")
@requires_auth
def api_debug_chat_history():
    rows = mysql_query("SELECT chat_type, content, created_at FROM ai_agent_chat_history ORDER BY created_at DESC LIMIT 50")
    rows.reverse()
    return jsonify(rows)


# ===== 动作编排 API =====

@app.route("/actions")
@requires_auth
def actions_page():
    return send_from_directory("static", "actions.html")


@app.route("/api/actions/groups")
@requires_auth
def api_actions_groups():
    rows = mysql_query("SELECT group_code, group_name, description, default_intensity, sequences, forbidden FROM rl_action_config ORDER BY id")
    for r in rows:
        r["default_intensity"] = int(r.get("default_intensity", 1))
        r["sequences"] = json.loads(r.get("sequences", "[]"))
        r["forbidden"] = json.loads(r["forbidden"]) if r.get("forbidden") and r["forbidden"] != "NULL" else []
    return jsonify(rows)


@app.route("/api/actions/groups/<group_code>", methods=["PUT"])
@requires_auth
def api_actions_group_update(group_code):
    data = request.json
    sequences = json.dumps(data.get("sequences", []), ensure_ascii=False)
    intensity = int(data.get("default_intensity", 1))
    desc = data.get("description", "")
    forbidden = data.get("forbidden")
    forbidden_sql = f"'{json.dumps(forbidden, ensure_ascii=False)}'" if forbidden else "NULL"
    sql = f"""UPDATE rl_action_config SET
        sequences='{sequences}',
        default_intensity={intensity},
        description='{desc}',
        forbidden={forbidden_sql}
        WHERE group_code='{group_code}'"""
    mysql_exec(sql)
    return jsonify({"ok": True})


@app.route("/api/actions/bindings")
@requires_auth
def api_actions_bindings():
    rows = mysql_query("SELECT mode_code, max_intensity, allowed_groups, action_probability FROM rl_action_mode_bind ORDER BY id")
    for r in rows:
        r["max_intensity"] = int(r.get("max_intensity", 2))
        r["action_probability"] = float(r.get("action_probability", 0.3))
        r["allowed_groups"] = json.loads(r["allowed_groups"]) if r.get("allowed_groups") and r["allowed_groups"] != "NULL" else None
    return jsonify(rows)


@app.route("/api/actions/bindings", methods=["PUT"])
@requires_auth
def api_actions_bindings_update():
    data = request.json
    for item in data:
        mode = item["mode_code"]
        intensity = int(item["max_intensity"])
        prob = float(item["action_probability"])
        allowed = item.get("allowed_groups")
        allowed_sql = f"'{json.dumps(allowed, ensure_ascii=False)}'" if allowed else "NULL"
        sql = f"""INSERT INTO rl_action_mode_bind (mode_code, max_intensity, allowed_groups, action_probability)
            VALUES ('{mode}', {intensity}, {allowed_sql}, {prob})
            ON DUPLICATE KEY UPDATE max_intensity={intensity}, allowed_groups={allowed_sql}, action_probability={prob}"""
        mysql_exec(sql)
    return jsonify({"ok": True})


@app.route("/api/actions/test", methods=["POST"])
@requires_auth
def api_actions_test():
    data = request.json
    group = data.get("group", "idle")
    intensity = int(data.get("intensity", 1))
    rows = mysql_query(f"SELECT sequences FROM rl_action_config WHERE group_code='{group}'")
    if not rows:
        return jsonify({"message": f"未找到动作组: {group}"}), 404
    import random
    sequences = json.loads(rows[0]["sequences"])
    seq = random.choice(sequences) if sequences else []
    if intensity < 2 and len(seq) > 2:
        seq = seq[:2]
    return jsonify({"message": f"将执行序列: {' -> '.join(seq)}", "sequence": seq, "group": group, "intensity": intensity})



# ========== 备忘录 ==========

@app.route("/memo")
@requires_auth
def memo_page():
    return send_from_directory("static", "memo.html")


@app.route("/api/memo")
@requires_auth
def api_memo_list():
    agent_id = request.args.get("agent_id", "1822c2babf1b44cca6b25d0bdebc796f")
    agent_id = agent_id.replace("'", "")
    try:
        rows = mysql_query(
            f"SELECT id, title, content, created_at, updated_at FROM rl_memo "
            f"WHERE agent_id='{agent_id}' ORDER BY created_at DESC"
        )
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/memo", methods=["POST"])
@requires_auth
def api_memo_create():
    data = request.get_json(force=True)
    agent_id = data.get("agent_id", "1822c2babf1b44cca6b25d0bdebc796f").replace("'", "")
    title = data.get("title", "").replace("'", "'")
    content = data.get("content", "").replace("'", "'")
    if not title:
        return jsonify({"error": "title 必填"}), 400
    try:
        mysql_exec(
            f"INSERT INTO rl_memo (agent_id, title, content) VALUES ('{agent_id}', '{title}', '{content}')"
        )
        rows = mysql_query("SELECT LAST_INSERT_ID() as id")
        new_id = rows[0]["id"] if rows else "?"
        return jsonify({"ok": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/memo/<int:memo_id>", methods=["DELETE"])
@requires_auth
def api_memo_delete(memo_id):
    agent_id = request.args.get("agent_id", "1822c2babf1b44cca6b25d0bdebc796f").replace("'", "")
    try:
        mysql_exec(f"DELETE FROM rl_memo WHERE id={memo_id} AND agent_id='{agent_id}'")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ========== LLM 调用日志 ==========

@app.route("/llm-logs")
@requires_auth
def llm_logs_page():
    return send_from_directory("static", "llm-logs.html")


@app.route("/api/llm-logs")
@requires_auth
def api_llm_logs():
    try:
        rows = mysql_query(
            "SELECT id, agent_id, device_mac, model_name, duration_ms, created_at, "
            "LEFT(response_text, 100) AS response_preview, "
            "CASE WHEN tool_calls_json IS NOT NULL AND tool_calls_json != '' THEN 1 ELSE 0 END AS has_tool_calls "
            "FROM rl_llm_log ORDER BY created_at DESC LIMIT 50"
        )
        for r in rows:
            r["has_tool_calls"] = int(r.get("has_tool_calls", 0))
            r["duration_ms"] = int(r.get("duration_ms", 0)) if r.get("duration_ms") else 0
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm-logs/<int:log_id>")
@requires_auth
def api_llm_log_detail(log_id):
    try:
        rows = mysql_query(
            f"SELECT id, agent_id, device_mac, model_name, duration_ms, created_at, "
            f"messages_json, response_text, tool_calls_json "
            f"FROM rl_llm_log WHERE id={log_id}"
        )
        if not rows:
            return jsonify({"error": "not found"}), 404
        return jsonify(rows[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ========== 系统设置 ==========

@app.route("/settings")
@requires_auth
def settings_page():
    return send_from_directory("static", "settings.html")


@app.route("/api/settings", methods=["GET"])
@requires_auth
def api_settings_get():
    try:
        rows = mysql_query("SELECT config_key, config_value, description, updated_at FROM rl_system_config ORDER BY config_key")
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings/<config_key>", methods=["PUT"])
@requires_auth
def api_settings_put(config_key):
    # Guard: only allow known keys
    ALLOWED_KEYS = {
        "strategy_enabled", "strategy_auto_generate",
        "reminder_enabled", "end_prompt_enabled",
        "asr_max_sentence_silence", "close_connection_timeout",
        "voiceprint_enabled", "voiceprint_threshold", "voiceprint_reject_text",
        "kid_mode_enabled", "kid_default_age_band",
    }
    if config_key not in ALLOWED_KEYS:
        return jsonify({"error": "unknown key"}), 400
    data = request.get_json(silent=True) or {}
    value = str(data.get("value", "")).replace("'", "")
    try:
        mysql_exec(
            f"INSERT INTO rl_system_config (config_key, config_value) VALUES ('{config_key}', '{value}') "
            f"ON DUPLICATE KEY UPDATE config_value='{value}', updated_at=NOW()"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings/apply-config", methods=["PUT"])
@requires_auth
def api_settings_apply_config():
    """Apply config values to config.yaml inside the Docker container."""
    import subprocess, os
    CONTAINER = "xiaozhi-esp32-server"
    CONFIG_PATH = "/opt/xiaozhi-esp32-server/config.yaml"
    try:
        rows = mysql_query(
            "SELECT config_key, config_value FROM rl_system_config "
            "WHERE config_key IN ('asr_max_sentence_silence', 'close_connection_timeout', 'end_prompt_enabled')"
        )
        kv = {r["config_key"]: r["config_value"] for r in rows}
        applied = []

        script_lines = []
        script_lines.append("import re")
        script_lines.append("path = '" + CONFIG_PATH + "'")
        script_lines.append("with open(path, 'r', encoding='utf-8') as f: text = f.read()")

        if "asr_max_sentence_silence" in kv:
            val = max(200, min(6000, int(kv["asr_max_sentence_silence"])))
            script_lines.append(
                "text = re.sub(r'(max_sentence_silence:\s*)\d+', r'\g<1>" + str(val) + "', text)"
            )
            applied.append("asr_max_sentence_silence=" + str(val))

        if "close_connection_timeout" in kv:
            val = max(30, min(600, int(kv["close_connection_timeout"])))
            script_lines.append(
                "text = re.sub(r'(close_connection_no_voice_time:\s*)\d+', r'\g<1>" + str(val) + "', text)"
            )
            applied.append("close_connection_timeout=" + str(val))

        if "end_prompt_enabled" in kv:
            enable_val = "true" if kv["end_prompt_enabled"] == "1" else "false"
            script_lines.append("lines = text.split(chr(10))")
            script_lines.append("fp = False")
            script_lines.append("for i, ln in enumerate(lines):")
            script_lines.append("  if 'end_prompt:' in ln and not ln.strip().startswith('#'): fp = True")
            script_lines.append("  elif fp and 'enable:' in ln:")
            script_lines.append("    lines[i] = re.sub(r'(enable:\s*)(true|false)', r'\g<1>" + enable_val + "', ln)")
            script_lines.append("    break")
            script_lines.append("text = chr(10).join(lines)")
            applied.append("end_prompt_enabled=" + enable_val)

        script_lines.append("with open(path, 'w', encoding='utf-8') as f: f.write(text)")
        script_lines.append("print('ok')")

        script_text = chr(10).join(script_lines)
        tmp_path = "/tmp/_apply_config.py"
        with open(tmp_path, "w") as f:
            f.write(script_text)

        subprocess.run(["docker", "cp", tmp_path, CONTAINER + ":/tmp/_apply_config.py"],
                       capture_output=True, timeout=5)
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "python3", "/tmp/_apply_config.py"],
            capture_output=True, text=True, timeout=10
        )
        os.remove(tmp_path)

        if result.returncode != 0:
            return jsonify({"error": "apply failed: " + result.stderr}), 500

        return jsonify({"ok": True, "applied": applied, "note": "config.yaml updated, restart container to take effect"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# IoT device routes for kb-admin app.py
# To be appended before `if __name__ == "__main__":`


@app.route("/iot")
@requires_auth
def page_iot():
    return send_from_directory("static", "iot.html")


@app.route("/api/iot/devices", methods=["GET"])
@requires_auth
def api_iot_devices_list():
    rows = mysql_query("SELECT * FROM rl_iot_device ORDER BY room, device_name")
    return jsonify(rows)


@app.route("/api/iot/devices/<int:device_id>", methods=["GET"])
@requires_auth
def api_iot_device_get(device_id):
    rows = mysql_query(f"SELECT * FROM rl_iot_device WHERE id={int(device_id)}")
    if not rows:
        return jsonify({"error": "not found"}), 404
    return jsonify(rows[0])


@app.route("/api/iot/devices", methods=["POST"])
@requires_auth
def api_iot_device_create():
    data = request.get_json(silent=True) or {}
    did = data.get("device_id", "").replace("'", "")
    name = data.get("device_name", "").replace("'", "")
    dtype = data.get("device_type", "other").replace("'", "")
    room = data.get("room", "").replace("'", "")
    protocol = data.get("protocol", "http").replace("'", "")
    endpoint = data.get("endpoint", "").replace("'", "")
    if not did or not name:
        return jsonify({"error": "device_id and device_name required"}), 400
    try:
        mysql_exec(
            f"INSERT INTO rl_iot_device (device_id, device_name, device_type, room, protocol, endpoint) "
            f"VALUES ('{did}', '{name}', '{dtype}', '{room}', '{protocol}', '{endpoint}')"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/iot/devices/<int:device_id>", methods=["PUT"])
@requires_auth
def api_iot_device_update(device_id):
    data = request.get_json(silent=True) or {}
    name = data.get("device_name", "").replace("'", "")
    dtype = data.get("device_type", "other").replace("'", "")
    room = data.get("room", "").replace("'", "")
    protocol = data.get("protocol", "http").replace("'", "")
    endpoint = data.get("endpoint", "").replace("'", "")
    try:
        mysql_exec(
            f"UPDATE rl_iot_device SET device_name='{name}', device_type='{dtype}', "
            f"room='{room}', protocol='{protocol}', endpoint='{endpoint}' "
            f"WHERE id={int(device_id)}"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/iot/devices/<int:device_id>", methods=["DELETE"])
@requires_auth
def api_iot_device_delete(device_id):
    try:
        mysql_exec(f"DELETE FROM rl_iot_device WHERE id={int(device_id)}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/iot/command", methods=["POST"])
@requires_auth
def api_iot_command():
    """Send a command to a device. Logs the command and attempts delivery."""
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id", "").replace("'", "")
    action = data.get("action", "").replace("'", "")
    params = data.get("params", {})
    source = data.get("source", "manual").replace("'", "")
    if not device_id or not action:
        return jsonify({"error": "device_id and action required"}), 400

    import json as _json
    params_str = _json.dumps(params, ensure_ascii=False).replace("'", "\\'")

    try:
        # Log the command
        mysql_exec(
            f"INSERT INTO rl_iot_log (device_id, action, params, result, source) "
            f"VALUES ('{device_id}', '{action}', '{params_str}', 'pending', '{source}')"
        )

        # TODO: Actually send command to device via HTTP/MQTT based on protocol
        # For now just mark as success (device integration will be added later)
        rows = mysql_query(f"SELECT id FROM rl_iot_log WHERE device_id='{device_id}' ORDER BY id DESC LIMIT 1")
        if rows:
            log_id = rows[0]["id"]
            mysql_exec(f"UPDATE rl_iot_log SET result='success' WHERE id={log_id}")

        # Update device state based on command
        state_update = None
        if action == "turn_on":
            state_update = '{"on": true}'
        elif action == "turn_off":
            state_update = '{"on": false}'
        elif action == "set_brightness":
            state_update = _json.dumps({"on": True, "brightness": params.get("brightness", 100)})
        elif action == "set_temp":
            state_update = _json.dumps({"on": True, "temperature": params.get("temperature", 26)})
        elif action == "set_mode":
            state_update = _json.dumps({"on": True, "mode": params.get("mode", "auto")})
        elif action in ("open", "set_position"):
            pos = params.get("position", 100) if action == "set_position" else 100
            state_update = _json.dumps({"position": pos})
        elif action == "close":
            state_update = '{"position": 0}'

        if state_update:
            mysql_exec(
                f"UPDATE rl_iot_device SET state_json='{state_update}', "
                f"is_online=1, last_seen=NOW() WHERE device_id='{device_id}'"
            )

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/iot/report", methods=["POST"])
def api_iot_report():
    """Device reports its state (no auth - called by devices themselves)."""
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id", "").replace("'", "")
    state = data.get("state", {})
    if not device_id:
        return jsonify({"error": "device_id required"}), 400

    import json as _json
    state_str = _json.dumps(state, ensure_ascii=False).replace("'", "\\'")
    try:
        mysql_exec(
            f"UPDATE rl_iot_device SET state_json='{state_str}', "
            f"is_online=1, last_seen=NOW() WHERE device_id='{device_id}'"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/iot/logs", methods=["GET"])
@requires_auth
def api_iot_logs():
    rows = mysql_query("SELECT * FROM rl_iot_log ORDER BY id DESC LIMIT 50")
    return jsonify(rows)


# Health profile routes for kb-admin app.py


@app.route("/health")
@requires_auth
def page_health():
    return send_from_directory("static", "health.html")


@app.route("/api/health/profile", methods=["GET"])
@requires_auth
def api_health_profile_list():
    rows = mysql_query(
        "SELECT * FROM rl_health_profile ORDER BY FIELD(category,'basic','vitals','medical','lifestyle'), id"
    )
    return jsonify(rows)


@app.route("/api/health/profile", methods=["PUT"])
@requires_auth
def api_health_profile_update():
    data = request.get_json(silent=True) or {}
    updates = data.get("updates", [])
    if not updates:
        return jsonify({"error": "no updates"}), 400
    try:
        for item in updates:
            key = item.get("field_key", "").replace("'", "")
            val = item.get("value", "").replace("'", "\\'")
            if key:
                mysql_exec(
                    f"UPDATE rl_health_profile SET field_value='{val}', source='manual' "
                    f"WHERE field_key='{key}'"
                )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health/profile/field", methods=["POST"])
@requires_auth
def api_health_profile_add_field():
    data = request.get_json(silent=True) or {}
    cat = data.get("category", "basic").replace("'", "")
    key = data.get("field_key", "").replace("'", "")
    name = data.get("field_name", "").replace("'", "")
    unit = data.get("unit", "").replace("'", "")
    if not key or not name:
        return jsonify({"error": "field_key and field_name required"}), 400
    try:
        mysql_exec(
            f"INSERT INTO rl_health_profile (category, field_key, field_name, unit) "
            f"VALUES ('{cat}', '{key}', '{name}', '{unit}')"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health/report", methods=["POST"])
def api_health_report():
    """Device/external system reports a single health data point (no auth)."""
    data = request.get_json(silent=True) or {}
    key = data.get("field_key", "").replace("'", "")
    val = data.get("value", "").replace("'", "\\'")
    source = data.get("source", "device").replace("'", "")
    note = data.get("note", "").replace("'", "\\'")
    if not key:
        return jsonify({"error": "field_key required"}), 400
    try:
        mysql_exec(
            f"UPDATE rl_health_profile SET field_value='{val}', source='{source}', "
            f"note='{note}' WHERE field_key='{key}'"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health/report-batch", methods=["POST"])
def api_health_report_batch():
    """Device/external system reports multiple health data points (no auth)."""
    data = request.get_json(silent=True) or {}
    items = data.get("data", [])
    source = data.get("source", "device").replace("'", "")
    if not items:
        return jsonify({"error": "no data"}), 400
    try:
        for item in items:
            key = item.get("field_key", "").replace("'", "")
            val = item.get("value", "").replace("'", "\\'")
            note = item.get("note", "").replace("'", "\\'")
            if key:
                mysql_exec(
                    f"UPDATE rl_health_profile SET field_value='{val}', source='{source}', "
                    f"note='{note}' WHERE field_key='{key}'"
                )
        return jsonify({"ok": True, "count": len(items)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# Voiceprint routes for kb-admin app.py


def _get_vpr_creds():
    rows = mysql_query(
        "SELECT config_key, config_value FROM rl_system_config "
        "WHERE config_key IN ('tencent_vpr_secret_id','tencent_vpr_secret_key','tencent_vpr_region')"
    )
    cfg = {r["config_key"]: r["config_value"] for r in rows}
    sid = cfg.get("tencent_vpr_secret_id", "")
    sk = cfg.get("tencent_vpr_secret_key", "")
    region = cfg.get("tencent_vpr_region", "ap-guangzhou") or "ap-guangzhou"
    return sid, sk, region


def _tencent_vpr_call(action, payload):
    """Call Tencent Cloud VPR API. Returns (ok, data_or_err)."""
    import json as _json
    sid, sk, region = _get_vpr_creds()
    if not sid or not sk:
        return False, "腾讯云VPR凭证未配置（设置页填写 SecretId/SecretKey）"
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.asr.v20190614 import asr_client, models
    except ImportError:
        return False, "未安装 tencentcloud-sdk-python，执行 pip install tencentcloud-sdk-python"

    cred = credential.Credential(sid, sk)
    hp = HttpProfile(); hp.endpoint = "asr.tencentcloudapi.com"
    cp = ClientProfile(); cp.httpProfile = hp
    client = asr_client.AsrClient(cred, region, cp)

    try:
        ReqCls = getattr(models, action + "Request")
        req = ReqCls()
        req.from_json_string(_json.dumps(payload))
        resp = getattr(client, action)(req)
        return True, _json.loads(resp.to_json_string())
    except Exception as e:
        return False, str(e)


@app.route("/voiceprint")
@requires_auth
def page_voiceprint():
    return send_from_directory("static", "voiceprint.html")


@app.route("/api/voiceprint/list", methods=["GET"])
@requires_auth
def api_voiceprint_list():
    rows = mysql_query(
        "SELECT id, user_label, relation, tencent_voice_id, enrolled_at, "
        "last_matched_at, is_active, note FROM rl_voiceprint ORDER BY id DESC"
    )
    return jsonify(rows)


@app.route("/api/voiceprint/enroll", methods=["POST"])
@requires_auth
def api_voiceprint_enroll():
    """Enroll a new voiceprint. Body: {user_label, relation, audio_base64, audio_format}"""
    data = request.get_json(silent=True) or {}
    label = (data.get("user_label") or "").strip().replace("'", "")
    relation = (data.get("relation") or "").strip().replace("'", "")
    audio_b64 = data.get("audio_base64") or ""
    audio_format = int(data.get("audio_format", 1))  # 1=wav, 2=pcm, 3=mp3
    if not label or not audio_b64:
        return jsonify({"error": "user_label 和 audio_base64 必填"}), 400

    ok, result = _tencent_vpr_call("VoicePrintEnroll", {
        "VoiceFormat": audio_format,
        "SampleRate": 16000,
        "Data": audio_b64,
    })
    if not ok:
        return jsonify({"error": result}), 500

    voice_id = result.get("Data", {}).get("VoicePrintId") or result.get("VoicePrintId")
    if not voice_id:
        return jsonify({"error": f"腾讯云未返回VoicePrintId: {result}"}), 500

    note = (data.get("note") or "").replace("'", "")
    try:
        mysql_exec(
            f"INSERT INTO rl_voiceprint (user_label, relation, tencent_voice_id, note) "
            f"VALUES ('{label}', '{relation}', '{voice_id}', '{note}')"
        )
        return jsonify({"ok": True, "voice_id": voice_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/voiceprint/<int:vid>", methods=["DELETE"])
@requires_auth
def api_voiceprint_delete(vid):
    rows = mysql_query(f"SELECT tencent_voice_id FROM rl_voiceprint WHERE id={int(vid)}")
    if not rows:
        return jsonify({"error": "not found"}), 404
    voice_id = rows[0]["tencent_voice_id"]
    _tencent_vpr_call("VoicePrintDelete", {"VoicePrintIdSet": [voice_id]})
    try:
        mysql_exec(f"DELETE FROM rl_voiceprint WHERE id={int(vid)}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/voiceprint/<int:vid>/toggle", methods=["PUT"])
@requires_auth
def api_voiceprint_toggle(vid):
    data = request.get_json(silent=True) or {}
    active = 1 if data.get("is_active") else 0
    try:
        mysql_exec(f"UPDATE rl_voiceprint SET is_active={active} WHERE id={int(vid)}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/voiceprint/verify", methods=["POST"])
def api_voiceprint_verify():
    """Verify audio against all active voiceprints. No auth (called by xiaozhi-server).
    Body: {audio_base64, audio_format}
    Returns: {matched: bool, voice_id, user_label, score, threshold}
    """
    data = request.get_json(silent=True) or {}
    audio_b64 = data.get("audio_base64") or ""
    audio_format = int(data.get("audio_format", 2))  # 2=pcm by default for server-side
    if not audio_b64:
        return jsonify({"error": "audio_base64 required"}), 400

    rows = mysql_query(
        "SELECT id, user_label, relation, tencent_voice_id FROM rl_voiceprint WHERE is_active=1"
    )
    if not rows:
        return jsonify({"matched": False, "reason": "no_enrolled_voiceprint"}), 200

    th_rows = mysql_query(
        "SELECT config_value FROM rl_system_config WHERE config_key='voiceprint_threshold'"
    )
    threshold = float(th_rows[0]["config_value"]) if th_rows else 60.0

    best = {"score": -1, "voice_id": None, "user_label": None, "relation": None, "id": None}
    for r in rows:
        ok, result = _tencent_vpr_call("VoicePrintVerify", {
            "VoiceFormat": audio_format,
            "SampleRate": 16000,
            "Data": audio_b64,
            "VoicePrintId": r["tencent_voice_id"],
        })
        if not ok:
            continue
        score = float(result.get("Data", {}).get("Score") or result.get("Score") or 0)
        if score > best["score"]:
            best = {
                "score": score,
                "voice_id": r["tencent_voice_id"],
                "user_label": r["user_label"],
                "relation": r.get("relation"),
                "id": r["id"],
            }

    matched = best["score"] >= threshold
    if matched:
        try:
            mysql_exec(f"UPDATE rl_voiceprint SET last_matched_at=NOW() WHERE id={best['id']}")
        except Exception:
            pass

    return jsonify({
        "matched": matched,
        "score": best["score"],
        "threshold": threshold,
        "voice_id": best["voice_id"],
        "user_label": best["user_label"],
        "relation": best["relation"],
    })


# ========== 儿童题库 ==========

@app.route("/kid")
@requires_auth
def page_kid():
    return send_from_directory("static", "kid.html")


@app.route("/dingyi-models")
@requires_auth
def page_dingyi_models():
    return send_from_directory("static", "dingyi-models.html")


@app.route("/dingyi-chat")
@requires_auth
def page_dingyi_chat():
    return send_from_directory("static", "dingyi-chat.html")


def _sql_safe(value):
    return str(value).replace("'", "''")


def _load_dingyiguo_llm_binding():
    binding_rows = mysql_query(
        "SELECT a.id AS agent_id, a.agent_name, a.llm_model_id, "
        "m.model_name, m.config_json "
        "FROM ai_agent a "
        "LEFT JOIN ai_model_config m ON a.llm_model_id = m.id "
        f"WHERE a.id='{DINGYIGUO_AGENT_ID}' LIMIT 1"
    )
    if not binding_rows:
        raise RuntimeError("丁一锅 agent 不存在")
    prompt_rows = mysql_query(
        "SELECT HEX(CAST(system_prompt AS BINARY)) AS system_prompt_hex, "
        "HEX(CAST(summary_memory AS BINARY)) AS summary_memory_hex "
        "FROM ai_agent "
        f"WHERE id='{DINGYIGUO_AGENT_ID}' LIMIT 1"
    )
    row = binding_rows[0]
    prompt_row = prompt_rows[0] if prompt_rows else {}
    raw = row.get("config_json") or "{}"
    try:
        cfg = json.loads(raw)
    except Exception:
        cfg = {}

    def _decode_hex(value):
        if not value or value == "NULL":
            return ""
        try:
            return bytes.fromhex(value).decode("utf-8", errors="replace")
        except Exception:
            return ""

    return {
        "agent_id": row.get("agent_id"),
        "agent_name": row.get("agent_name"),
        "llm_model_id": row.get("llm_model_id"),
        "llm_model_name": row.get("model_name"),
        "system_prompt": _decode_hex(prompt_row.get("system_prompt_hex")),
        "summary_memory": _decode_hex(prompt_row.get("summary_memory_hex")),
        "config": cfg,
    }


def _save_dingyiguo_llm_config(binding, cfg):
    safe_cfg = _sql_safe(json.dumps(cfg, ensure_ascii=False))
    safe_model_id = _sql_safe(binding["llm_model_id"])
    mysql_exec(
        "UPDATE ai_model_config "
        f"SET config_json='{safe_cfg}', update_date=NOW() "
        f"WHERE id='{safe_model_id}'"
    )


def _fetch_model_ids(base_url, api_key):
    if not base_url or not api_key:
        return [], "未配置 base_url 或 api_key"

    resp = requests.get(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20,
    )
    body = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {}
    if not resp.ok:
        detail = body or resp.text[:1000]
        return [], f"模型列表请求失败: HTTP {resp.status_code} {detail}"

    model_ids = []
    for item in body.get("data", []):
        model_id = item.get("id")
        if model_id:
            model_ids.append(model_id)
    return model_ids, ""


def _call_dingyiguo_chat(messages):
    binding = _load_dingyiguo_llm_binding()
    cfg = binding["config"]
    base_url = (cfg.get("base_url") or cfg.get("url") or "").strip()
    api_key = (cfg.get("api_key") or "").strip()
    model_name = (cfg.get("model_name") or "").strip()
    if not base_url or not api_key or not model_name:
        raise RuntimeError("丁一锅当前 LLM 配置不完整")

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }

    for key in ("max_tokens", "temperature", "top_p", "frequency_penalty"):
        value = cfg.get(key)
        if value in (None, ""):
            continue
        try:
            payload[key] = int(value) if key == "max_tokens" else float(value)
        except (TypeError, ValueError):
            pass

    resp = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    body = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {}
    if not resp.ok:
        detail = body or resp.text[:1000]
        raise RuntimeError(f"对话请求失败: HTTP {resp.status_code} {detail}")

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("模型返回为空")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return {
        "reply": str(content).strip(),
        "binding": binding,
        "usage": body.get("usage") or {},
        "model": body.get("model") or model_name,
    }


@app.route("/api/dingyi-models", methods=["GET"])
@requires_auth
def api_dingyi_models():
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = binding["config"]
        base_url = (cfg.get("base_url") or cfg.get("url") or "").strip()
        api_key = (cfg.get("api_key") or "").strip()
        current_model_name = (cfg.get("model_name") or "").strip()
        model_ids, models_error = _fetch_model_ids(base_url, api_key)

        return jsonify({
            "binding": binding,
            "source": {
                "base_url": base_url,
                "api_key": api_key,
                "api_key_masked": (api_key[:6] + "..." + api_key[-4:]) if len(api_key) > 12 else api_key,
                "models_url": base_url.rstrip("/") + "/models",
            },
            "models": model_ids,
            "current_model_name": current_model_name,
            "models_error": models_error,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-chat/config", methods=["GET"])
@requires_auth
def api_dingyi_chat_config():
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = binding["config"]
        return jsonify({
            "agent_id": binding["agent_id"],
            "agent_name": binding["agent_name"],
            "llm_model_id": binding["llm_model_id"],
            "llm_model_name": binding["llm_model_name"],
            "model_name": (cfg.get("model_name") or "").strip(),
            "base_url": (cfg.get("base_url") or cfg.get("url") or "").strip(),
            "has_api_key": bool((cfg.get("api_key") or "").strip()),
            "system_prompt": binding.get("system_prompt") or "",
            "summary_memory": binding.get("summary_memory") or "",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-chat/send", methods=["POST"])
@requires_auth
def api_dingyi_chat_send():
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()
    history = data.get("history") or []
    if not user_text:
        return jsonify({"error": "text required"}), 400
    if not isinstance(history, list):
        return jsonify({"error": "history must be a list"}), 400

    try:
        binding = _load_dingyiguo_llm_binding()
        scene = _route_scene_for_text(user_text, history)
        messages = []
        if binding.get("system_prompt"):
            messages.append({"role": "system", "content": binding["system_prompt"]})
        if binding.get("summary_memory"):
            messages.append({
                "role": "system",
                "content": "以下是长期记忆摘要，请作为陪伴上下文参考：\n" + binding["summary_memory"],
            })

        for item in history[-20:]:
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_text})
        result = _call_dingyiguo_chat(messages)
        return jsonify({
            "ok": True,
            "reply": result["reply"],
            "model": result["model"],
            "usage": result["usage"],
            "agent_name": binding["agent_name"],
            "scene": scene,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scene-router/scenes", methods=["GET"])
@requires_auth
def api_scene_router_scenes():
    try:
        return jsonify({
            "ok": True,
            **_load_scene_router_snapshot(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-models/config", methods=["POST"])
@requires_auth
def api_dingyi_models_config():
    data = request.get_json(silent=True) or {}
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = dict(binding["config"])
        if "base_url" in data:
            cfg["base_url"] = (data.get("base_url") or "").strip()
        if "api_key" in data:
            cfg["api_key"] = (data.get("api_key") or "").strip()
        if "model_name" in data:
            cfg["model_name"] = (data.get("model_name") or "").strip()
        _save_dingyiguo_llm_config(binding, cfg)
        return jsonify({
            "ok": True,
            "agent_id": binding["agent_id"],
            "agent_name": binding["agent_name"],
            "llm_model_id": binding["llm_model_id"],
            "config": {
                "base_url": cfg.get("base_url") or cfg.get("url") or "",
                "api_key": cfg.get("api_key") or "",
                "model_name": cfg.get("model_name") or "",
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dingyi-models/switch", methods=["POST"])
@requires_auth
def api_dingyi_models_switch():
    data = request.get_json(silent=True) or {}
    model_name = (data.get("model_name") or "").strip()
    if not model_name:
        return jsonify({"error": "model_name required"}), 400
    try:
        binding = _load_dingyiguo_llm_binding()
        cfg = dict(binding["config"])
        cfg["model_name"] = model_name
        _save_dingyiguo_llm_config(binding, cfg)
        return jsonify({
            "ok": True,
            "agent_id": binding["agent_id"],
            "agent_name": binding["agent_name"],
            "llm_model_id": binding["llm_model_id"],
            "model_name": model_name,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kid/stats", methods=["GET"])
@requires_auth
def api_kid_stats():
    try:
        total_row = mysql_query("SELECT COUNT(*) as cnt FROM rl_kid_content WHERE enabled=1")
        total = int(total_row[0]["cnt"]) if total_row else 0
        type_rows = mysql_query(
            "SELECT content_type, COUNT(*) as cnt FROM rl_kid_content WHERE enabled=1 GROUP BY content_type"
        )
        by_type = {r["content_type"]: int(r["cnt"]) for r in type_rows}
        return jsonify({"total": total, "by_type": by_type})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kid/questions", methods=["GET"])
@requires_auth
def api_kid_questions_list():
    try:
        ctype = request.args.get("type", "")
        age = request.args.get("age", "")
        enabled = request.args.get("enabled", "")
        filters = []
        if ctype:
            filters.append(f"content_type='{ctype}'")
        if age:
            filters.append(f"age_band='{age}'")
        if enabled != "":
            filters.append(f"enabled={int(enabled)}")
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        rows = mysql_query(
            f"SELECT id, content_type, question, answer, age_band, reward_group, comfort_group, enabled "
            f"FROM rl_kid_content {where} ORDER BY id DESC LIMIT 500"
        )
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kid/questions", methods=["POST"])
@requires_auth
def api_kid_question_create():
    data = request.get_json(silent=True) or {}
    q = data.get("question", "").replace("'", "''")
    a = data.get("answer", "").replace("'", "''")
    ct = data.get("content_type", "riddle").replace("'", "")
    age = data.get("age_band", "6-8").replace("'", "")
    rg = data.get("reward_group", "happy").replace("'", "")
    cg = data.get("comfort_group", "comfort").replace("'", "")
    if not q or not a:
        return jsonify({"error": "question and answer required"}), 400
    try:
        mysql_exec(
            f"INSERT INTO rl_kid_content (content_type, question, answer, age_band, reward_group, comfort_group) "
            f"VALUES ('{ct}', '{q}', '{a}', '{age}', '{rg}', '{cg}')"
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kid/questions/<int:qid>", methods=["PUT"])
@requires_auth
def api_kid_question_update(qid):
    data = request.get_json(silent=True) or {}
    sets = []
    field_map = {
        "content_type": "content_type", "question": "question", "answer": "answer",
        "age_band": "age_band", "reward_group": "reward_group", "comfort_group": "comfort_group",
    }
    for key, col in field_map.items():
        if key in data:
            val = str(data[key]).replace("'", "''")
            sets.append(f"{col}='{val}'")
    if "enabled" in data:
        sets.append(f"enabled={int(data['enabled'])}")
    if not sets:
        return jsonify({"error": "nothing to update"}), 400
    try:
        mysql_exec(f"UPDATE rl_kid_content SET {','.join(sets)} WHERE id={qid}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kid/questions/<int:qid>", methods=["DELETE"])
@requires_auth
def api_kid_question_delete(qid):
    try:
        mysql_exec(f"DELETE FROM rl_kid_content WHERE id={qid}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kid/profiles", methods=["GET"])
@requires_auth
def api_kid_profiles():
    try:
        rows = mysql_query(
            "SELECT device_mac, total_questions, total_correct, best_streak, "
            "fav_type, weak_type, active_days, profile_json, updated_at "
            "FROM rl_kid_profile ORDER BY updated_at DESC LIMIT 20"
        )
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not ZHIPU_API_KEY:
        raise SystemExit("env ZHIPU_API_KEY 未设")
    if not ADMIN_PASS:
        raise SystemExit("env KB_ADMIN_PASS 未设")
    app.run(host="0.0.0.0", port=8888)
