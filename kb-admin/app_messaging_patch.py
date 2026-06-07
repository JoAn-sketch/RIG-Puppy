"""消息中心管理路由 - 给 kb-admin app.py 用的扩展模块。

把它 import 到 app.py 顶部:
    from app_messaging_patch import register_messaging_routes
然后在最底部 app.run() 之前调用:
    register_messaging_routes(app, requires_auth)

依赖:
    - pymysql (容器外宿主机 Python 需要装)
    - 复用 kb-admin 已有的 ADMIN_PASS / ADMIN_USER
"""
import subprocess
import pymysql
from flask import request, jsonify, send_from_directory


DB_CONTAINER = "xiaozhi-esp32-server-db"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = "123456"
DB_NAME = "xiaozhi_esp32_server"


def _resolve_db_host():
    """xiaozhi-esp32-server-db 没在 host 暴露 3306,只能用 docker 网桥 IP 直连。"""
    try:
        r = subprocess.run(
            ["docker", "inspect", DB_CONTAINER, "--format",
             "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"],
            capture_output=True, text=True, timeout=5,
        )
        ip = (r.stdout or "").strip()
        if ip:
            return ip
    except Exception:
        pass
    return "127.0.0.1"


_DB_HOST_CACHE = {"ip": None}


def _db_host():
    if not _DB_HOST_CACHE["ip"]:
        _DB_HOST_CACHE["ip"] = _resolve_db_host()
    return _DB_HOST_CACHE["ip"]


def _conn():
    return pymysql.connect(
        host=_db_host(), port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
        connect_timeout=5,
    )


def _agents_with_names():
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, agent_name FROM ai_agent ORDER BY agent_name")
        return list(cur.fetchall())


def register_messaging_routes(app, requires_auth):
    # === 页面入口 ===

    @app.route("/contacts")
    @requires_auth
    def contacts_page():
        return send_from_directory("static", "contacts.html")

    @app.route("/templates")
    @requires_auth
    def templates_page():
        return send_from_directory("static", "templates.html")

    @app.route("/message-log")
    @requires_auth
    def message_log_page():
        return send_from_directory("static", "message_log.html")

    @app.route("/reminders")
    @requires_auth
    def reminders_page():
        return send_from_directory("static", "reminders.html")

    # === 智能体下拉 ===

    @app.route("/api/msg/agents")
    @requires_auth
    def msg_list_agents():
        return jsonify({"list": _agents_with_names()})

    # === 联系人 ===

    @app.route("/api/msg/contacts")
    @requires_auth
    def list_contacts():
        agent_id = request.args.get("agent_id", "")
        with _conn() as c, c.cursor() as cur:
            if agent_id:
                cur.execute(
                    "SELECT * FROM rl_contacts WHERE agent_id=%s ORDER BY id DESC",
                    (agent_id,),
                )
            else:
                cur.execute("SELECT * FROM rl_contacts ORDER BY id DESC")
            rows = list(cur.fetchall())
        for r in rows:
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat(sep=" ", timespec="seconds")
        return jsonify({"list": rows})

    @app.route("/api/msg/contacts", methods=["POST"])
    @requires_auth
    def create_contact():
        b = request.get_json(force=True)
        required = {"agent_id": b.get("agent_id"), "nickname": b.get("nickname")}
        for k, v in required.items():
            if not v:
                return jsonify({"error": f"{k} 必填"}), 400
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO rl_contacts "
                "(agent_id, nickname, relation, phone, wxpusher_uid, channel_pref, remark, enabled) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    b["agent_id"], b["nickname"],
                    b.get("relation") or None,
                    b.get("phone") or None,
                    b.get("wxpusher_uid") or None,
                    (b.get("channel_pref") or "auto").lower(),
                    b.get("remark") or None,
                    1 if b.get("enabled", True) else 0,
                ),
            )
            new_id = cur.lastrowid
        return jsonify({"ok": True, "id": new_id})

    @app.route("/api/msg/contacts/<int:cid>", methods=["PUT"])
    @requires_auth
    def update_contact(cid):
        b = request.get_json(force=True)
        if not b.get("nickname"):
            return jsonify({"error": "nickname 必填"}), 400
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "UPDATE rl_contacts SET nickname=%s, relation=%s, phone=%s, "
                "wxpusher_uid=%s, channel_pref=%s, remark=%s, enabled=%s WHERE id=%s",
                (
                    b["nickname"],
                    b.get("relation") or None,
                    b.get("phone") or None,
                    b.get("wxpusher_uid") or None,
                    (b.get("channel_pref") or "auto").lower(),
                    b.get("remark") or None,
                    1 if b.get("enabled", True) else 0,
                    cid,
                ),
            )
        return jsonify({"ok": True})

    @app.route("/api/msg/contacts/<int:cid>", methods=["DELETE"])
    @requires_auth
    def delete_contact(cid):
        with _conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM rl_contacts WHERE id=%s", (cid,))
        return jsonify({"ok": True})

    # === 模板 ===

    @app.route("/api/msg/templates")
    @requires_auth
    def list_templates():
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT * FROM rl_message_templates ORDER BY id")
            rows = list(cur.fetchall())
        for r in rows:
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat(sep=" ", timespec="seconds")
        return jsonify({"list": rows})

    @app.route("/api/msg/templates", methods=["POST"])
    @requires_auth
    def create_template():
        b = request.get_json(force=True)
        for k in ("template_key", "display_name", "content"):
            if not b.get(k):
                return jsonify({"error": f"{k} 必填"}), 400
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute(
                    "INSERT INTO rl_message_templates "
                    "(template_key, display_name, content, variables, "
                    "tencent_sms_template_id, tencent_sms_sign, sms_supported, enabled) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        b["template_key"], b["display_name"], b["content"],
                        b.get("variables") or None,
                        b.get("tencent_sms_template_id") or None,
                        b.get("tencent_sms_sign") or None,
                        1 if b.get("sms_supported") else 0,
                        1 if b.get("enabled", True) else 0,
                    ),
                )
                new_id = cur.lastrowid
            return jsonify({"ok": True, "id": new_id})
        except pymysql.err.IntegrityError as e:
            return jsonify({"error": f"template_key 重复: {e}"}), 400

    @app.route("/api/msg/templates/<int:tid>", methods=["PUT"])
    @requires_auth
    def update_template(tid):
        b = request.get_json(force=True)
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "UPDATE rl_message_templates SET display_name=%s, content=%s, "
                "variables=%s, tencent_sms_template_id=%s, tencent_sms_sign=%s, "
                "sms_supported=%s, enabled=%s WHERE id=%s",
                (
                    b.get("display_name", ""), b.get("content", ""),
                    b.get("variables") or None,
                    b.get("tencent_sms_template_id") or None,
                    b.get("tencent_sms_sign") or None,
                    1 if b.get("sms_supported") else 0,
                    1 if b.get("enabled", True) else 0,
                    tid,
                ),
            )
        return jsonify({"ok": True})

    @app.route("/api/msg/templates/<int:tid>", methods=["DELETE"])
    @requires_auth
    def delete_template(tid):
        with _conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM rl_message_templates WHERE id=%s", (tid,))
        return jsonify({"ok": True})

    # === 发送日志 ===

    @app.route("/api/msg/logs")
    @requires_auth
    def list_logs():
        agent_id = request.args.get("agent_id", "")
        limit = int(request.args.get("limit", "100"))
        limit = max(1, min(limit, 500))
        with _conn() as c, c.cursor() as cur:
            if agent_id:
                cur.execute(
                    "SELECT * FROM rl_message_log WHERE agent_id=%s "
                    "ORDER BY id DESC LIMIT %s",
                    (agent_id, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM rl_message_log ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
            rows = list(cur.fetchall())
        for r in rows:
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat(sep=" ", timespec="seconds")
        return jsonify({"list": rows})

    # === 提醒计划 ===

    @app.route("/api/msg/reminders")
    @requires_auth
    def list_reminders():
        agent_id = request.args.get("agent_id", "")
        with _conn() as c, c.cursor() as cur:
            if agent_id:
                cur.execute(
                    "SELECT * FROM rl_reminders WHERE agent_id=%s "
                    "ORDER BY type, fire_date, fire_time",
                    (agent_id,),
                )
            else:
                cur.execute("SELECT * FROM rl_reminders ORDER BY id DESC")
            rows = list(cur.fetchall())
        for r in rows:
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat(sep=" ", timespec="seconds")
        return jsonify({"list": rows})

    @app.route("/api/msg/reminders", methods=["POST"])
    @requires_auth
    def create_reminder():
        b = request.get_json(force=True)
        for k in ("agent_id", "type", "title", "fire_time"):
            if not b.get(k):
                return jsonify({"error": f"{k} 必填"}), 400
        type_ = b["type"].lower()
        if type_ not in ("daily", "once"):
            return jsonify({"error": "type 只能 daily/once"}), 400
        if type_ == "once" and not b.get("fire_date"):
            return jsonify({"error": "type=once 必须填 fire_date"}), 400
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO rl_reminders "
                "(agent_id, type, title, content, fire_time, fire_date, enabled) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    b["agent_id"], type_, b["title"],
                    b.get("content") or None,
                    b["fire_time"],
                    b.get("fire_date") or None,
                    1 if b.get("enabled", True) else 0,
                ),
            )
            new_id = cur.lastrowid
        return jsonify({"ok": True, "id": new_id})

    @app.route("/api/msg/reminders/<int:rid>", methods=["PUT"])
    @requires_auth
    def update_reminder(rid):
        b = request.get_json(force=True)
        type_ = (b.get("type") or "daily").lower()
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "UPDATE rl_reminders SET type=%s, title=%s, content=%s, "
                "fire_time=%s, fire_date=%s, enabled=%s WHERE id=%s",
                (
                    type_, b.get("title", ""),
                    b.get("content") or None,
                    b.get("fire_time", ""),
                    b.get("fire_date") or None,
                    1 if b.get("enabled", True) else 0,
                    rid,
                ),
            )
        return jsonify({"ok": True})

    @app.route("/api/msg/reminders/<int:rid>", methods=["DELETE"])
    @requires_auth
    def delete_reminder(rid):
        with _conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM rl_reminders WHERE id=%s", (rid,))
        return jsonify({"ok": True})

    @app.route("/api/msg/reminders/<int:rid>/reset-fired", methods=["POST"])
    @requires_auth
    def reset_fired(rid):
        """清掉 last_fired_at,让"今日"提醒能重新被播报(调试用)。"""
        with _conn() as c, c.cursor() as cur:
            cur.execute("UPDATE rl_reminders SET last_fired_at=NULL WHERE id=%s", (rid,))
        return jsonify({"ok": True})
