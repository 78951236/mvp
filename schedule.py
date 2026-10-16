"""课表的算法层：周次、某天有没有课、冲突判定、坐标轴范围、方块定位。

照 docs/03-数据模型.md 第三/五/六节实现。这里只有纯函数，方便单独自测
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
# 提醒（照 docs/04-提醒规则.md）
# --------------------------------------------------------------------------

EVENT_LABELS = {
    "new_week": "新的一周到来",
    "new_day": "新的一天到来",
    "class_start": "每一节课上课",
    "class_end": "每一节课下课",
}

SCOPE_LABELS = {
    "next_class": "下一节课",
    "today_remaining": "今天还没上的课",
    "today_all": "今天的所有课",
    "last_class": "上一节课",
    "today_done": "今天上过的课",
    "tomorrow": "明天的课",
}

EXTRA_LABELS = {
    "name": "名称",
    "teacher": "任课老师",
    "time": "上下课时间",
    "location": "上课地点",
    "weekdays": "周几",
    "note": "备注",
}

# 通知正文里各属性的前缀（04 文档第四节的例子：老师：/时间：/地点：）
EXTRA_PREFIX = {"teacher": "老师", "time": "时间", "location": "地点",
                "weekdays": "周几", "note": "备注"}


def _at(day, hhmm):
    """把 'HH:MM' 贴到某一天上，得到 datetime。"""
    h, m = str(hhmm).split(":")[:2]
    return datetime.datetime.combine(day, datetime.time(int(h), int(m)))


def trigger_delta(reminder):
    """时间差：「前」为负，「后」为正。"""
    minutes = int(reminder.get("offset_hours") or 0) * 60 + int(reminder.get("offset_minutes") or 0)
    return datetime.timedelta(minutes=-minutes if reminder.get("direction") == "before" else minutes)


def anchor_moments(reminder, day, courses):
    """一天的锚点时刻（04 文档第二节）。

    new_week → 该日所在周的周一 00:00；new_day → 该日 00:00；
    class_start / class_end → 当天每节课的上下课时刻（一天多条）。
    """
    event = reminder.get("event")
    if event == "new_week":
        return [datetime.datetime.combine(first_monday(day), datetime.time(0, 0))]
    if event == "new_day":
        return [datetime.datetime.combine(day, datetime.time(0, 0))]
    if event in ("class_start", "class_end"):
        field = "start_time" if event == "class_start" else "end_time"
        return [_at(day, c[field]) for c in courses if course_occurs_on(c, day)]
    return []


def reminder_triggers(reminder, day, courses):
    """某条提醒在某一天上产生的所有触发时刻。"""
    delta = trigger_delta(reminder)
    return [{"moment": a + delta, "anchor": a, "day": day}
            for a in anchor_moments(reminder, day, courses)]


def scan_triggers(reminders, courses, semester, now, window_seconds=60):
    """算出 [now, now+window) 之间该触发的提醒（04 文档第六节）。

    - 只看「默认学期范围内」的日子：假期 / 学期外当天按没课处理，一条都不弹
    - 前后各看一天，覆盖「时间差导致触发时刻跨天」的情况
    - 关掉的提醒（enabled=0）不参与
    """
    lo = now
    hi = now + datetime.timedelta(seconds=window_seconds)
    start = parse_date(semester["start_date"]) if semester else None
    end = parse_date(semester["end_date"]) if semester else None

    hits = []
    for offset in (-1, 0, 1):
        day = now.date() + datetime.timedelta(days=offset)
        if start and not (start <= day <= end):
            continue
        for reminder in reminders:
            if not int(reminder.get("enabled") or 0):
                continue
            for trig in reminder_triggers(reminder, day, courses):
                if lo <= trig["moment"] < hi:
                    hits.append({**trig, "reminder": reminder})

    seen, unique = set(), []
    for hit in hits:                      # 同一提醒同一时刻只算一次（new_week 会被三天重复命中）
        key = (hit["reminder"]["id"], hit["moment"].isoformat())
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    unique.sort(key=lambda h: (h["moment"], h["reminder"]["id"]))
    return unique


def scope_courses(scope, courses, moment):
    """提醒范围：通知里放哪些课，按触发那一刻动态算（04 文档第三节）。"""
    day = moment.date() + datetime.timedelta(days=1) if scope == "tomorrow" else moment.date()
    today = sorted((c for c in courses if course_occurs_on(c, day)),
                   key=lambda c: time_to_min(c["start_time"]))
    now_min = moment.hour * 60 + moment.minute

    if scope in ("tomorrow", "today_all"):
        return today
    if scope == "today_remaining":
        return [c for c in today if time_to_min(c["start_time"]) > now_min]
    if scope == "today_done":
        return [c for c in today if time_to_min(c["end_time"]) <= now_min]
    if scope == "next_class":
        cand = [c for c in today if time_to_min(c["start_time"]) >= now_min]
        return [min(cand, key=lambda c: time_to_min(c["start_time"]))] if cand else []
    if scope == "last_class":
        cand = [c for c in today if time_to_min(c["end_time"]) <= now_min]
        return [max(cand, key=lambda c: time_to_min(c["end_time"]))] if cand else []
    return []


def format_notification(scope, courses, extra_fields):
    """通知正文（04 文档第四节）。不选附加信息 → 只显示范围标题。"""
    title = "【%s】" % SCOPE_LABELS.get(scope, scope)
    if not courses:
        return title
    fields = [f.strip() for f in str(extra_fields or "").split(",") if f.strip() in EXTRA_LABELS]

    blocks = []
    for i, c in enumerate(courses):
        head = title if i == 0 else ""
        if "name" in fields:
            head += str(c["name"])
        lines = [head] if head else []
        for field in ("teacher", "time", "location", "weekdays", "note"):
            if field not in fields:
                continue
            if field == "time":
                value = "%s - %s" % (c["start_time"], c["end_time"])
            elif field == "weekdays":
                value = weekdays_to_text(c["weekdays"])
            else:
                value = str(c.get(field) or "")
            lines.append("%s：%s" % (EXTRA_PREFIX[field], value))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_notification(hits, courses):
    """把同一时刻命中的多条提醒合并成一条通知（04 文档第六节 / 01 文档确认记录）。

    范围内一门课都没有 → 这条提醒不发（04 文档第三节补充规则）。
    返回 (标题, 正文)，没有任何可发内容时返回 (None, None)。
    """
    blocks = []
    for hit in hits:
        reminder = hit["reminder"]
        in_scope = scope_courses(reminder.get("scope"), courses, hit["moment"])
        if not in_scope:
            continue
        block = format_notification(reminder.get("scope"), in_scope, reminder.get("extra_fields"))
        if block not in blocks:           # 同样的话不重复写两遍
            blocks.append(block)
    if not blocks:
        return None, None
    return "课表提醒", "\n\n".join(blocks)


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

    # ---------------------------------------------------------- 提醒（04 文档）
    # 04 文档第三节的算例：现在是 09:50，今天 08:00~09:40 已上完高数，10:00 上 C 语言
    gao = {"id": 1, "name": "高等数学", "teacher": "张老师", "weekdays": "1",
           "start_date": "2026-09-01", "end_date": "2027-01-15",
           "start_time": "08:00", "end_time": "09:40", "location": "3号教学楼201",
           "note": "带计算器"}
    cyy = {"id": 2, "name": "C语言程序设计", "teacher": "李老师", "weekdays": "1",
           "start_date": "2026-09-01", "end_date": "2027-01-15",
           "start_time": "10:00", "end_time": "11:40", "location": "实验楼B302", "note": ""}
    monday = parse_date("2026-10-12")                 # 2026-10-12 是周一
    M = datetime.datetime(2026, 10, 12, 9, 50)        # 09:50

    check("下一节课 = C语言", [c["name"] for c in scope_courses("next_class", [gao, cyy], M)], ["C语言程序设计"])
    check("今天还没上的课", [c["name"] for c in scope_courses("today_remaining", [gao, cyy], M)], ["C语言程序设计"])
    check("今天的所有课（按时间排序）",
          [c["name"] for c in scope_courses("today_all", [gao, cyy], M)], ["高等数学", "C语言程序设计"])
    check("上一节课 = 高数", [c["name"] for c in scope_courses("last_class", [gao, cyy], M)], ["高等数学"])
    check("今天上过的课", [c["name"] for c in scope_courses("today_done", [gao, cyy], M)], ["高等数学"])
    check("明天的课（周二没课 → 空）", scope_courses("tomorrow", [gao, cyy], M), [])
    check("今天的课都上完了 → 没有下一节课",
          scope_courses("next_class", [gao, cyy], datetime.datetime(2026, 10, 12, 12, 0)), [])

    # 触发时刻（04 文档第二节的表）
    def one_trigger(event, h, m, direction, day=monday):
        r = {"id": 1, "event": event, "offset_hours": h, "offset_minutes": m,
             "direction": direction, "scope": "today_all", "extra_fields": "", "enabled": 1}
        return [t["moment"] for t in reminder_triggers(r, day, [gao, cyy])]

    check("新的一天到来 6:00后 → 每天 06:00",
          one_trigger("new_day", 6, 0, "after"), [datetime.datetime(2026, 10, 12, 6, 0)])
    check("新的一周到来 0:00后 → 周一 00:00",
          one_trigger("new_week", 0, 0, "after"), [datetime.datetime(2026, 10, 12, 0, 0)])
    check("周日算同一条周一锚点（10-18 周日 → 10-12 周一）",
          one_trigger("new_week", 0, 0, "after", parse_date("2026-10-18")),
          [datetime.datetime(2026, 10, 12, 0, 0)])
    check("每一节课上课 0:30前 → 每节课前 30 分钟",
          one_trigger("class_start", 0, 30, "before"),
          [datetime.datetime(2026, 10, 12, 7, 30), datetime.datetime(2026, 10, 12, 9, 30)])
    check("每一节课下课 0:10后 → 每节课后 10 分钟",
          one_trigger("class_end", 0, 10, "after"),
          [datetime.datetime(2026, 10, 12, 9, 50), datetime.datetime(2026, 10, 12, 11, 50)])

    sem_real = {"id": 1, "seq_no": 1, "start_date": "2026-09-01", "end_date": "2027-01-15", "is_default": 1}
    sem_holiday = {"id": 2, "seq_no": 2, "start_date": "2027-02-20", "end_date": "2027-07-10", "is_default": 0}

    def scan_reminders(hour, minute, second=0, day=(2026, 10, 12), enabled=1, sem=None, direction="before"):
        r = {"id": 7, "event": "class_start", "offset_hours": 0, "offset_minutes": 30,
             "direction": direction, "scope": "next_class", "extra_fields": "name,location",
             "enabled": enabled}
        now = datetime.datetime(day[0], day[1], day[2], hour, minute, second)
        return scan_triggers([r], [gao, cyy], sem or sem_real, now)

    check("07:29:40 扫一分钟 → 命中 07:30 的课前提醒", len(scan_reminders(7, 29, 40)), 1)
    check("命中时刻正确", scan_reminders(7, 29, 40)[0]["moment"], datetime.datetime(2026, 10, 12, 7, 30))
    check("07:30:00 那一刻也算命中（左闭右开）", len(scan_reminders(7, 30, 0)), 1)
    check("07:30:59 不重复命中（窗口已过）", scan_reminders(7, 30, 59), [])
    check("放假当天一条都不弹（学期 2027-02-20 起）", scan_reminders(7, 29, 40, sem=sem_holiday), [])
    check("关掉的提醒不触发", scan_reminders(7, 29, 40, enabled=0), [])

    # 跨天：新的一天到来 3:00 前 → 前一天 21:00
    r_cross = {"id": 8, "event": "new_day", "offset_hours": 3, "offset_minutes": 0,
               "direction": "before", "scope": "today_all", "extra_fields": "name", "enabled": 1}
    cross = scan_triggers([r_cross], [gao, cyy], sem_real,
                          datetime.datetime(2026, 10, 11, 20, 59, 40))
    check("跨天触发：10-11 21:00 命中 10-12 的「新的一天」", len(cross), 1)
    check("跨天触发时刻", cross[0]["moment"], datetime.datetime(2026, 10, 11, 21, 0))

    # 通知正文（04 文档第五节的两条例子的结构）
    check("只选名称+地点（例1 的形状）",
          format_notification("next_class", [gao], "name,location"),
          "【下一节课】高等数学\n地点：3号教学楼201")
    check("选时间+名称（例2 的形状，两门课）",
          format_notification("today_all", [gao, cyy], "time,name"),
          "【今天的所有课】高等数学\n时间：08:00 - 09:40\n\n"
          "C语言程序设计\n时间：10:00 - 11:40")
    check("不选附加信息 → 只显示范围标题", format_notification("next_class", [gao], ""), "【下一节课】")

    # 合并 + 范围内没课不发
    hit_early = {"moment": datetime.datetime(2026, 10, 12, 7, 30), "reminder": {
        "id": 1, "scope": "next_class", "extra_fields": "name,location"}}
    hit_late = {"moment": datetime.datetime(2026, 10, 12, 7, 30), "reminder": {
        "id": 2, "scope": "today_all", "extra_fields": "name"}}
    title, body = build_notification([hit_early, hit_late], [gao, cyy])
    check("同一时刻两条提醒合并成一条（标题）", title, "课表提醒")
    check("合并后的正文块数", body.count("【"), 2)
    empty_title, empty_body = build_notification(
        [{"moment": datetime.datetime(2026, 10, 13, 20, 0), "reminder": {
            "id": 3, "scope": "tomorrow", "extra_fields": "name"}}], [gao, cyy])
    check("范围内一门课都没有 → 不发通知", (empty_title, empty_body), (None, None))
    check("两条一模一样的提醒不重复写",
          build_notification([hit_early, hit_early], [gao, cyy])[1].count("【"), 1)

    print("\n结果:", "全部通过" if ok else "有失败项")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)
