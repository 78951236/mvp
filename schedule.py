"""课表的算法层：周次、某天有没有课、冲突判定、坐标轴范围、方块定位。

照 03-数据模型.md 第三/五/六节实现。这里只有纯函数，方便单独自测
（`venv\\Scripts\\python schedule.py`）。
"""

import datetime

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 一门课都没有时的兜底坐标轴：08:00 ~ 22:00
FALLBACK_AXIS = (8 * 60, 22 * 60)


def parse_date(text):
    """'YYYY-MM-DD' -> date"""
    return datetime.date.fromisoformat(text)


def first_monday(start_date):
    """起始日所在那一周的周一（一周以周一开始；起始日是周日时 = 起始日 - 6 天）。"""
    return start_date - datetime.timedelta(days=start_date.weekday())


def week_index(day, start_date):
    """第 x 周：第一周 = 起始日所在的那一周。"""
    return (day - first_monday(start_date)).days // 7 + 1


def total_weeks(start_date, end_date):
    """总周数 = (结束日所在周的周一 - 第一周的周一) // 7 + 1"""
    return (first_monday(end_date) - first_monday(start_date)).days // 7 + 1


def parse_weekdays(text):
    """'1,3,5' -> {1,3,5}（1 = 周一 … 7 = 周日）"""
    out = set()
    for part in str(text or "").split(","):
        part = part.strip()
        if part.isdigit():
            n = int(part)
            if 1 <= n <= 7:
                out.add(n)
    return out


def weekdays_to_text(text):
    return " ".join(WEEKDAY_LABELS[n - 1] for n in sorted(parse_weekdays(text)))


def time_to_min(text):
    """'HH:MM' -> 从 00:00 起的分钟数"""
    h, m = str(text).split(":")[:2]
    return int(h) * 60 + int(m)


def min_to_time(minutes):
    minutes = int(minutes)
    return "%02d:%02d" % (minutes // 60, minutes % 60)


def course_occurs_on(course, day):
    """某门课在日期 D 上课 ⟺ start_date ≤ D ≤ end_date 且 D 的周几 ∈ weekdays"""
    if not (parse_date(course["start_date"]) <= day <= parse_date(course["end_date"])):
        return False
    return day.isoweekday() in parse_weekdays(course["weekdays"])


def courses_conflict(a, b):
    """两门课是否冲突（03 文档第五节）：日期范围有重叠，且存在一天时间段也重叠。"""
    a0, a1 = parse_date(a["start_date"]), parse_date(a["end_date"])
    b0, b1 = parse_date(b["start_date"]), parse_date(b["end_date"])

    lo, hi = max(a0, b0), min(a1, b1)
    if lo > hi:                       # 日期范围无交集
        return False

    # 时间段重叠：A.start < B.end 且 B.start < A.end
    if not (time_to_min(a["start_time"]) < time_to_min(b["end_time"])
            and time_to_min(b["start_time"]) < time_to_min(a["end_time"])):
        return False

    a_days, b_days = parse_weekdays(a["weekdays"]), parse_weekdays(b["weekdays"])
    if not (a_days & b_days):
        return False

    # 在交集范围内逐天找「这一天两门课都要上」
    day = lo
    while day <= hi:
        if day.isoweekday() in a_days and day.isoweekday() in b_days:
            return True
        day += datetime.timedelta(days=1)
    return False


def find_conflicts(courses):
    """-> {课程id: [与之冲突的课程名, ...]}"""
    result = {}
    for i in range(len(courses)):
        for j in range(i + 1, len(courses)):
            a, b = courses[i], courses[j]
            if courses_conflict(a, b):
                result.setdefault(a["id"], []).append(b["name"])
                result.setdefault(b["id"], []).append(a["name"])
    return result


def axis_range(courses, conflicting_ids=()):
    """y 轴范围：该学期所有不冲突课程里最早的 start_time ~ 最晚的 end_time，
    向下/向上取整到整点。一门课都没有就用兜底 08:00 ~ 22:00。"""
    usable = [c for c in courses if c["id"] not in set(conflicting_ids)]
    if not usable:
        return FALLBACK_AXIS
    lo = min(time_to_min(c["start_time"]) for c in usable)
    hi = max(time_to_min(c["end_time"]) for c in usable)
    lo = (lo // 60) * 60              # 向下取整到整点
    hi = -(-hi // 60) * 60            # 向上取整到整点
    if hi <= lo:
        hi = lo + 60
    return lo, hi


def text_color_for(hex_color):
    """浅色方块用深色字，深色方块用白字（02 文档 4.1 已确认）。"""
    raw = str(hex_color or "").lstrip("#")
    if len(raw) != 6:
        return "#1F2937"
    try:
        r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#1F2937"
    # 相对亮度（人眼加权），> 0.6 视为浅色
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1F2937" if luminance > 0.6 else "#FFFFFF"


def short_name(name, limit=4):
    """窄屏下方块里用的短名字（能看出是哪门课就行）。"""
    name = str(name or "")
    return name if len(name) <= limit else name[:limit]


def build_week_view(semester, courses, today=None):
    """给课表页用的完整数据（M5/M6/M7）。

    返回 dict：学期信息、第 x 周、是否在学期范围内、坐标轴、7 天各自的方块。
    冲突的课程不参与绘制，也不参与坐标轴计算（03 文档 / 01 文档 4.2）。
    """
    today = today or datetime.date.today()
    conflicts = find_conflicts(courses)
    conflicting_ids = set(conflicts)

    start, end = parse_date(semester["start_date"]), parse_date(semester["end_date"])
    in_range = start <= today <= end
    week_no = week_index(today, start)
    weeks_total = total_weeks(start, end)
    lo, hi = axis_range(courses, conflicting_ids)
    span = max(hi - lo, 1)

    monday = first_monday(start) + datetime.timedelta(days=(week_no - 1) * 7)

    days = []
    for i in range(7):
        day = monday + datetime.timedelta(days=i)
        blocks = []
        for c in courses:
            if c["id"] in conflicting_ids:
                continue
            if not course_occurs_on(c, day):
                continue
            s, e = time_to_min(c["start_time"]), time_to_min(c["end_time"])
            if e <= s:
                continue
            blocks.append({
                "id": c["id"],
                "name": c["name"],
                "short_name": short_name(c["name"]),
                "teacher": c["teacher"],
                "location": c["location"],
                "note": c.get("note", ""),
                "color": c["color"] or "#FFFFFF",
                "text_color": text_color_for(c["color"]),
                "start_time": c["start_time"],
                "end_time": c["end_time"],
                "top_pct": round((s - lo) / span * 100, 4),
                "height_pct": round((e - s) / span * 100, 4),
            })
        blocks.sort(key=lambda b: b["start_time"])
        days.append({
            "weekday": i + 1,
            "label": WEEKDAY_LABELS[i],
            "date": day.isoformat(),
            "date_text": day.strftime("%Y/%m/%d"),
            "is_today": day == today,
            "blocks": blocks,
        })

    return {
        "semester": dict(semester),
        "today": today.isoformat(),
        "week_index": week_no,
        "weeks_total": weeks_total,
        "in_range": in_range,
        "axis": {"start": min_to_time(lo), "end": min_to_time(hi),
                 "start_min": lo, "end_min": hi, "span_min": span},
        "days": days,
        "conflicts": {str(k): v for k, v in conflicts.items()},
    }


# --------------------------------------------------------------------------
# 自测（M4 验收）：venv\Scripts\python schedule.py
# --------------------------------------------------------------------------

def _self_test():
    ok = True

    def check(label, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print(f"{'✔' if good else '✘'} {label}: got={got!r} want={want!r}")

    # 03 文档算例：学期 2026/09/01（周二）开始 → 第一周的周一 = 2026/08/31
    s = parse_date("2026-09-01")
    check("2026-09-01 的周一", first_monday(s).isoformat(), "2026-08-31")
    # 2026/10/15（周四）→ 第 7 周
    check("2026-10-15 是第几周", week_index(parse_date("2026-10-15"), s), 7)

    # 周日开学：2026-09-06 是周日 → 第一周的周一 = 2026-08-31（起始日 - 6 天）
    s2 = parse_date("2026-09-06")
    check("周日开学时的周一", first_monday(s2).isoformat(), "2026-08-31")
    check("周日开学当天是第几周", week_index(s2, s2), 1)
    check("周日开学次日的周一", week_index(parse_date("2026-09-07"), s2), 2)

    # 周一开学：2026-08-31 → 第一周的周一就是它自己
    s3 = parse_date("2026-08-31")
    check("周一开学时的周一", first_monday(s3).isoformat(), "2026-08-31")

    # 总周数：2026-09-01 ~ 2027-01-15
    check("总周数", total_weeks(s, parse_date("2027-01-15")), 20)

    # 某天有没有课
    c = {"id": 1, "name": "高等数学", "weekdays": "1,3",
         "start_date": "2026-09-01", "end_date": "2027-01-15",
         "start_time": "08:00", "end_time": "09:40", "color": "#2F6FED", "teacher": "张老师", "location": "3-201"}
    check("周一（09-07）有课", course_occurs_on(c, parse_date("2026-09-07")), True)
    check("周二（09-08）没课", course_occurs_on(c, parse_date("2026-09-08")), False)
    check("范围外（08-31）没课", course_occurs_on(c, parse_date("2026-08-31")), False)

    # 冲突：同一时间同一周几
    d = dict(c, id=2, name="英语", weekdays="1", start_time="09:00", end_time="10:00")
    check("重叠一小时的课冲突", courses_conflict(c, d), True)
    e = dict(c, id=3, name="C语言", weekdays="2", start_time="09:00", end_time="10:00")
    check("周几不同不冲突", courses_conflict(c, e), False)
    f = dict(c, id=4, name="体育", weekdays="1", start_time="09:40", end_time="11:00")
    check("首尾相接不算冲突", courses_conflict(c, f), False)
    g = dict(c, id=5, name="旧课", weekdays="1",
             start_date="2026-01-01", end_date="2026-06-30")
    check("日期范围不重叠不算冲突", courses_conflict(c, g), False)

    # 坐标轴：08:00~09:40 → 向下取整 08:00、向上取整 10:00
    check("坐标轴范围", axis_range([c]), (8 * 60, 10 * 60))
    check("空课表的兜底范围", axis_range([]), FALLBACK_AXIS)

    # 方块定位
    sem = {"id": 1, "seq_no": 1, "start_date": "2026-09-01", "end_date": "2027-01-15", "is_default": 1}
    view = build_week_view(sem, [c], today=parse_date("2026-10-14"))   # 2026-10-14 是周三
    check("当周周次", view["week_index"], 7)
    check("在学期范围内", view["in_range"], True)
    monday = view["days"][0]
    check("第 7 周的周一是 10-12", monday["date"], "2026-10-12")
    check("周三那列有 1 个方块", len(view["days"][2]["blocks"]), 1)
    check("周一那列有 1 个方块", len(view["days"][0]["blocks"]), 1)
    blk = view["days"][2]["blocks"][0]
    # 轴 08:00~10:00（120 分），课 08:00~09:40（100 分）→ top 0%，高 83.33%
    check("方块高度占比", blk["height_pct"], round(100 / 120 * 100, 4))
    check("方块顶部", blk["top_pct"], 0.0)
    check("深色方块用白字", blk["text_color"], "#FFFFFF")

    # 学期范围外
    out = build_week_view(sem, [c], today=parse_date("2027-03-01"))
    check("放假时不在范围内", out["in_range"], False)

    # 冲突课程不参与课表绘制，也不算进坐标轴
    both = [c, d]
    cf = find_conflicts(both)
    check("找出冲突对", sorted(cf.keys()), [1, 2])
    view2 = build_week_view(sem, both, today=parse_date("2026-09-07"))
    check("冲突时课表不画这两门", sum(len(x["blocks"]) for x in view2["days"]), 0)
    check("冲突时坐标轴回落到兜底", (view2["axis"]["start_min"], view2["axis"]["end_min"]), FALLBACK_AXIS)

    print("\n结果:", "全部通过" if ok else "有失败项")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
