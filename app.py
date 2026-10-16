"""课表网页服务（Flask）。

照 04 文档启动方式：
    venv\\Scripts\\python app.py                     # 默认 0.0.0.0:5000，手机连同一个 WiFi 就能打开
    venv\\Scripts\\python app.py --port 8000
    venv\\Scripts\\python app.py --host 127.0.0.1     # 只允许本机访问
"""

import argparse
import datetime
import os
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

def main(argv=None):
    parser = argparse.ArgumentParser(description="课表网页服务")
    parser.add_argument("--port", type=int, default=5000, help="网页服务端口（默认 5000）")
    parser.add_argument("--host", default="0.0.0.0",
                        help="监听地址（默认 0.0.0.0，手机才能连；只给本机用就填 127.0.0.1）")
    args = parser.parse_args(argv)

    tables = models.init_db()
    print("数据库:", models.DB_PATH)
    print("已建表:", ", ".join(tables))
    print(f"服务地址: http://127.0.0.1:{args.port}")
    if args.host == "0.0.0.0":
        print("局域网访问: http://<本机IP>:%d（手机连同一个 WiFi）" % args.port)
    try:
        app.run(host=args.host, port=args.port, debug=False)
    except OSError as exc:
        print(f"\n启动失败：{exc}")
        print(f"端口 {args.port} 可能已被占用，换一个端口试试：python app.py --port {args.port + 1}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
