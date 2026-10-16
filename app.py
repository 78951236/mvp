"""课表网页服务（Flask）。

照 04 文档启动方式：
    venv\\Scripts\\python app.py                     # 默认 0.0.0.0:5000，手机连同一个 WiFi 就能打开
    venv\\Scripts\\python app.py --port 8000
    venv\\Scripts\\python app.py --host 127.0.0.1     # 只允许本机访问
"""

import argparse
import datetime
import os
import socket
import sqlite3
import sys

from flask import Flask, jsonify, redirect, render_template, request

import models
import schedule as sched

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def norm_date(text):
    """把 2026/09/01、2026-9-1 统一成 2026-09-01；不合法返回 None。"""
    if text is None:
        return None
    text = str(text).strip().replace("/", "-").replace(".", "-")
    if not text:
        return None
    parts = text.split("-")
    if len(parts) != 3:
        return None
    try:
        return datetime.date(int(parts[0]), int(parts[1]), int(parts[2])).isoformat()
    except ValueError:
        return None


def norm_time(text):
    """'8:00' -> '08:00'；不合法返回 None。"""
    if text is None:
        return None
    text = str(text).strip()
    if ":" not in text:
        return None
    h, _, m = text.partition(":")
    try:
        h, m = int(h), int(m)
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return "%02d:%02d" % (h, m)


def norm_weekdays(value):
    """接受 '1,3' / [1,3] / ['1','3'] -> '1,3'（升序去重）；空返回 None。"""
    if value is None:
        return None
    if isinstance(value, str):
        items = value.replace(" ", ",").split(",")
    else:
        items = list(value)
    nums = set()
    for it in items:
        it = str(it).strip()
        if it.isdigit() and 1 <= int(it) <= 7:
            nums.add(int(it))
    if not nums:
        return None
    return ",".join(str(n) for n in sorted(nums))


def bad_request(msg):
    return jsonify({"ok": False, "error": msg}), 400


@app.errorhandler(sqlite3.DatabaseError)
def handle_db_error(exc):
    """数据库半路坏了，也给一句人能看懂的话，不甩堆栈（P2）。"""
    print("数据库出错：%s" % exc)
    return jsonify({
        "ok": False,
        "error": "数据库文件读不出来了（可能坏了）。把 data\\class_schedule.db 改名或删掉，"
                 "重启后会建一个空库；有备份就用备份还原。",
    }), 500


def date_cn(text):
    """2026-09-01 -> 2026/09/01（页面显示用）"""
    return text.replace("-", "/") if text else ""


def semester_payload(sem):
    if not sem:
        return None
    out = dict(sem)
    out["start_text"] = date_cn(sem["start_date"])
    out["end_text"] = date_cn(sem["end_date"])
    out["is_default"] = bool(sem["is_default"])
    return out


def course_payload(course, conflicts=None):
    out = dict(course)
    out["start_text"] = date_cn(course["start_date"])
    out["end_text"] = date_cn(course["end_date"])
    out["weekday_text"] = sched.weekdays_to_text(course["weekdays"])
    out["weekday_list"] = sorted(sched.parse_weekdays(course["weekdays"]))
    out["has_conflict"] = bool(conflicts and course["id"] in conflicts)
    out["conflict_with"] = (conflicts or {}).get(course["id"], [])
    return out


def validate_course(data):
    """校验并整理课程表单。返回 (整理好的 dict, 错误信息)。"""
    cleaned = {}
    for field, label in (("name", "课程名称"), ("teacher", "任课老师"), ("location", "上课地点")):
        val = str(data.get(field) or "").strip()
        if not val:
            return None, f"{label}不能为空"
        cleaned[field] = val

    weekdays = norm_weekdays(data.get("weekdays"))
    if not weekdays:
        return None, "请至少选择一个周几"
    cleaned["weekdays"] = weekdays

    start_date = norm_date(data.get("start_date"))
    end_date = norm_date(data.get("end_date"))
    if not start_date or not end_date:
        return None, "持续时间的起止日期请填完整（年/月/日）"
    if end_date < start_date:
        return None, "持续时间的结束日期不能早于开始日期"
    cleaned["start_date"], cleaned["end_date"] = start_date, end_date

    start_time = norm_time(data.get("start_time"))
    end_time = norm_time(data.get("end_time"))
    if not start_time or not end_time:
        return None, "上下课时间请填完整"
    if sched.time_to_min(end_time) <= sched.time_to_min(start_time):
        return None, "下课时间必须晚于上课时间"
    cleaned["start_time"], cleaned["end_time"] = start_time, end_time

    color = str(data.get("color") or "#FFFFFF").strip().upper()
    if not (len(color) == 7 and color.startswith("#")):
        color = "#FFFFFF"
    cleaned["color"] = color
    cleaned["note"] = str(data.get("note") or "").strip()
    return cleaned, None


def validate_semester(data):
    raw_seq = str(data.get("seq_no") or "").strip()
    if not raw_seq.isdigit() or int(raw_seq) < 1:
        return None, "学期序号请填正整数（第几学期）"
    start_date = norm_date(data.get("start_date"))
    end_date = norm_date(data.get("end_date"))
    if not start_date or not end_date:
        return None, "学期的起止日期请填完整（年/月/日）"
    if end_date < start_date:
        return None, "结束日期不能早于开始日期"
    return {"seq_no": int(raw_seq), "start_date": start_date, "end_date": end_date}, None


# --------------------------------------------------------------------------
# 页面
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect("/schedule")


@app.route("/schedule")
def page_schedule():
    return render_template("schedule.html", nav="")


@app.route("/settings/semesters")
def page_semesters():
    return render_template("semesters.html", nav="semesters")


@app.route("/settings/reminders")
def page_reminders():
    return render_template("reminders.html", nav="reminders")


@app.route("/semesters/<int:sid>/courses")
def page_course_settings(sid):
    sem = models.get_semester(sid)
    if not sem:
        return redirect("/settings/semesters")
    # 课程设置页不属于菜单里任何一页 → nav 传空，左侧不点亮任何一项
    return render_template("course_settings.html", nav="", semester=semester_payload(sem))


# --------------------------------------------------------------------------
# 接口：学期
# --------------------------------------------------------------------------

@app.get("/api/semesters")
def api_list_semesters():
    return jsonify({"ok": True, "semesters": [semester_payload(s) for s in models.list_semesters()]})


@app.post("/api/semesters")
def api_create_semester():
    data, err = validate_semester(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    sid = models.create_semester(**data)
    return jsonify({"ok": True, "semester": semester_payload(models.get_semester(sid))}), 201


@app.put("/api/semesters/<int:sid>")
def api_update_semester(sid):
    if not models.get_semester(sid):
        return jsonify({"ok": False, "error": "学期不存在"}), 404
    data, err = validate_semester(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    models.update_semester(sid, **data)
    return jsonify({"ok": True, "semester": semester_payload(models.get_semester(sid))})


@app.delete("/api/semesters/<int:sid>")
def api_delete_semester(sid):
    if not models.get_semester(sid):
        return jsonify({"ok": False, "error": "学期不存在"}), 404
    models.delete_semester(sid)
    return jsonify({"ok": True})


@app.post("/api/semesters/<int:sid>/default")
def api_set_default(sid):
    if not models.get_semester(sid):
        return jsonify({"ok": False, "error": "学期不存在"}), 404
    models.set_default_semester(sid)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# 接口：课程
# --------------------------------------------------------------------------

@app.get("/api/semesters/<int:sid>/courses")
def api_list_courses(sid):
    if not models.get_semester(sid):
        return jsonify({"ok": False, "error": "学期不存在"}), 404
    courses = models.list_courses(sid)
    conflicts = sched.find_conflicts(courses)
    return jsonify({
        "ok": True,
        "courses": [course_payload(c, conflicts) for c in courses],
        "conflicts": {str(k): v for k, v in conflicts.items()},
    })


@app.post("/api/semesters/<int:sid>/courses")
def api_create_course(sid):
    if not models.get_semester(sid):
        return jsonify({"ok": False, "error": "学期不存在"}), 404
    cleaned, err = validate_course(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    cid = models.create_course(sid, cleaned)
    courses = models.list_courses(sid)
    conflicts = sched.find_conflicts(courses)
    return jsonify({"ok": True, "course": course_payload(models.get_course(cid), conflicts)}), 201


@app.put("/api/courses/<int:cid>")
def api_update_course(cid):
    course = models.get_course(cid)
    if not course:
        return jsonify({"ok": False, "error": "课程不存在"}), 404
    cleaned, err = validate_course(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    models.update_course(cid, cleaned)
    courses = models.list_courses(course["semester_id"])
    conflicts = sched.find_conflicts(courses)
    return jsonify({"ok": True, "course": course_payload(models.get_course(cid), conflicts)})


@app.delete("/api/courses/<int:cid>")
def api_delete_course(cid):
    if not models.get_course(cid):
        return jsonify({"ok": False, "error": "课程不存在"}), 404
    models.delete_course(cid)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# 接口：提醒（阶段 2 · R2）
# --------------------------------------------------------------------------

def reminder_options():
    return {
        "events": [{"value": k, "label": v} for k, v in sched.EVENT_LABELS.items()],
        "scopes": [{"value": k, "label": v} for k, v in sched.SCOPE_LABELS.items()],
        "extras": [{"value": k, "label": v} for k, v in sched.EXTRA_LABELS.items()],
    }


def reminder_payload(r):
    out = dict(r)
    out["enabled"] = bool(r["enabled"])
    out["event_label"] = sched.EVENT_LABELS.get(r["event"], r["event"])
    out["scope_label"] = sched.SCOPE_LABELS.get(r["scope"], r["scope"])
    out["direction_label"] = "前" if r["direction"] == "before" else "后"
    out["offset_text"] = "%02d:%02d" % (r["offset_hours"], r["offset_minutes"])
    out["extra_list"] = [x.strip() for x in str(r["extra_fields"] or "").split(",") if x.strip()]
    out["extra_labels"] = [sched.EXTRA_LABELS[x] for x in out["extra_list"] if x in sched.EXTRA_LABELS]
    return out


def validate_reminder(data):
    event = str(data.get("event") or "").strip()
    if event not in sched.EVENT_LABELS:
        return None, "请选择事件"
    scope = str(data.get("scope") or "").strip()
    if scope not in sched.SCOPE_LABELS:
        return None, "请选择提醒范围"
    direction = str(data.get("direction") or "before").strip()
    if direction not in ("before", "after"):
        return None, "时间差只能选「前」或「后」"
    try:
        hours = int(data.get("offset_hours") or 0)
        minutes = int(data.get("offset_minutes") or 0)
    except (TypeError, ValueError):
        return None, "时间差请填数字"
    if not 0 <= hours <= 23:
        return None, "时间差的「时」只能填 0 ~ 23"
    if not 0 <= minutes <= 59:
        return None, "时间差的「分」只能填 0 ~ 59"

    raw_extras = data.get("extra_fields")
    if isinstance(raw_extras, (list, tuple, set)):
        candidates = [str(x) for x in raw_extras]
    else:
        candidates = str(raw_extras or "").replace(" ", ",").split(",")

    items, bad = [], []
    for raw in candidates:
        raw = raw.strip()
        if not raw:
            continue
        if raw not in sched.EXTRA_LABELS:
            bad.append(raw)
        elif raw not in items:
            items.append(raw)
    if bad:
        return None, "附加信息里有不认识的项：%s" % "、".join(bad)

    enabled = 1 if str(data.get("enabled", 1)).lower() in ("1", "true", "yes") else 0
    return {"event": event, "offset_hours": hours, "offset_minutes": minutes,
            "direction": direction, "scope": scope,
            "extra_fields": ",".join(items), "enabled": enabled}, None


@app.get("/api/reminders")
def api_list_reminders():
    return jsonify({"ok": True, "reminders": [reminder_payload(r) for r in models.list_reminders()],
                    "options": reminder_options()})


@app.post("/api/reminders")
def api_create_reminder():
    cleaned, err = validate_reminder(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    rid = models.create_reminder(cleaned)
    row = next((r for r in models.list_reminders() if r["id"] == rid), None)
    return jsonify({"ok": True, "reminder": reminder_payload(row)}), 201


@app.put("/api/reminders/<int:rid>")
def api_update_reminder(rid):
    rows = [r for r in models.list_reminders() if r["id"] == rid]
    if not rows:
        return jsonify({"ok": False, "error": "提醒不存在"}), 404
    cleaned, err = validate_reminder(request.get_json(silent=True) or {})
    if err:
        return bad_request(err)
    models.update_reminder(rid, cleaned)
    row = next((r for r in models.list_reminders() if r["id"] == rid), None)
    return jsonify({"ok": True, "reminder": reminder_payload(row)})


@app.post("/api/reminders/<int:rid>/toggle")
def api_toggle_reminder(rid):
    rows = [r for r in models.list_reminders() if r["id"] == rid]
    if not rows:
        return jsonify({"ok": False, "error": "提醒不存在"}), 404
    current = dict(rows[0])
    current["enabled"] = 0 if current["enabled"] else 1
    models.update_reminder(rid, current)
    row = next((r for r in models.list_reminders() if r["id"] == rid), None)
    return jsonify({"ok": True, "reminder": reminder_payload(row)})


@app.delete("/api/reminders/<int:rid>")
def api_delete_reminder(rid):
    if not any(r["id"] == rid for r in models.list_reminders()):
        return jsonify({"ok": False, "error": "提醒不存在"}), 404
    models.delete_reminder(rid)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# 接口：课表
# --------------------------------------------------------------------------

@app.get("/api/schedule")
def api_schedule():
    sem = models.get_default_semester()
    if not sem:
        return jsonify({"ok": True, "has_default": False})
    courses = models.list_courses(sem["id"])
    view = sched.build_week_view(sem, courses)
    view["ok"] = True
    view["has_default"] = True
    view["semester"] = semester_payload(sem)
    return jsonify(view)


# --------------------------------------------------------------------------
# 启动
# --------------------------------------------------------------------------

def lan_ip():
    """探一下本机在局域网里的地址（手机要用这个地址连）。探不到返回 None。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))          # 只是让系统挑一条默认路由，不会真的发包
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def port_free(host, port):
    """先探一下端口能不能独占绑上。

    为什么要自己探：Werkzeug 的开发服务器开了 SO_REUSEADDR，而 **Windows 上
    SO_REUSEADDR 允许两个进程同时绑同一个端口**（跟 Linux 不一样），结果是第二个
    服务悄悄起来、和第一个抢请求，还不报错。用 SO_EXCLUSIVEADDRUSE 探一次就能
    提前发现，给一句人能看懂的话。
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):      # 只有 Windows 有
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((host if host != "0.0.0.0" else "0.0.0.0", port))
        return True, None
    except OSError as exc:
        return False, exc
    finally:
        probe.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="课表网页服务")
    parser.add_argument("--port", type=int, default=5000, help="网页服务端口（默认 5000）")
    parser.add_argument("--host", default="0.0.0.0",
                        help="监听地址（默认 0.0.0.0，手机才能连；只给本机用就填 127.0.0.1）")
    args = parser.parse_args(argv)

    # 数据库读不出来时，给一句人能看懂的话，而不是报错堆栈（P2）
    try:
        tables = models.init_db()
    except sqlite3.DatabaseError as exc:
        print("启动失败：数据库文件读不出来。")
        print("  文件：%s" % models.DB_PATH)
        print("  原因：%s" % exc)
        print("  处理：把这个文件改名或删掉，重新启动会建一个空库；")
        print("        要是之前备份过 data 目录，也可以拿备份还原回来。")
        return 1

    # 端口先探一次（P2）：Windows 上 SO_REUSEADDR 会让第二个服务也绑上同一个端口
    ok, why = port_free(args.host, args.port)
    if not ok:
        print("启动失败：端口 %d 用不了。" % args.port)
        print("  原因：%s" % why)
        print("  多半是已经开着一个课表服务了 —— 浏览器直接打开 http://127.0.0.1:%d 就能用，" % args.port)
        print("  想同时再开一个就换个端口：python app.py --port %d" % (args.port + 1))
        return 1

    print("数据库:", models.DB_PATH)
    print("已建表:", ", ".join(tables))
    print("本机访问: http://127.0.0.1:%d" % args.port)

    if args.host == "0.0.0.0":
        ip = lan_ip()
        if ip:
            print("手机访问: http://%s:%d  （手机连同一个 WiFi，地址栏敲这个）" % (ip, args.port))
        else:
            print("手机访问: 没能自动认出本机 IP，命令行里敲 ipconfig 找 IPv4 地址，再用 http://那个地址:%d" % args.port)
    else:
        print("提示: 现在只听 %s，手机连不上；想让手机也能开就加 --host 0.0.0.0" % args.host)

    try:
        app.run(host=args.host, port=args.port, debug=False)
    except (OSError, SystemExit) as exc:
        # Werkzeug 撞端口时是「打印原始错误 + sys.exit(1)」，SystemExit 不是 OSError
        print()
        print("启动失败：服务没起来（%s）。" % (exc or "端口被占"))
        print("  换个端口试试：python app.py --port %d" % (args.port + 1))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
