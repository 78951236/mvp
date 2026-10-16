"""数据层：SQLite 三张表（semesters / courses / reminders）的建档与增删改查。

照 03-数据模型.md 实现。网页（app.py）和提醒程序（notifier.py）读写同一个文件：
data/class_schedule.db
"""

import datetime
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "class_schedule.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS semesters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    seq_no      INTEGER NOT NULL,
    start_date  TEXT    NOT NULL,
    end_date    TEXT    NOT NULL,
    is_default  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    semester_id INTEGER NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    teacher     TEXT    NOT NULL DEFAULT '',
    weekdays    TEXT    NOT NULL DEFAULT '',
    start_date  TEXT    NOT NULL,
    end_date    TEXT    NOT NULL,
    start_time  TEXT    NOT NULL,
    end_time    TEXT    NOT NULL,
    location    TEXT    NOT NULL DEFAULT '',
    color       TEXT    NOT NULL DEFAULT '#FFFFFF',
    note        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event          TEXT    NOT NULL,
    offset_hours   INTEGER NOT NULL DEFAULT 0,
    offset_minutes INTEGER NOT NULL DEFAULT 0,
    direction      TEXT    NOT NULL DEFAULT 'before',
    scope          TEXT    NOT NULL,
    extra_fields   TEXT    NOT NULL DEFAULT '',
    enabled        INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_courses_semester ON courses(semester_id);
"""


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """建表（幂等）。返回建好的表名列表，方便命令行里打印验证。"""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [r["name"] for r in rows]


def row_to_dict(row):
    return dict(row) if row is not None else None


# --------------------------------------------------------------------------
# 学期
# --------------------------------------------------------------------------

def list_semesters():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM semesters ORDER BY seq_no ASC, id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_semester(sid):
    with get_conn() as conn:
        return row_to_dict(conn.execute("SELECT * FROM semesters WHERE id=?", (sid,)).fetchone())


def get_default_semester():
    with get_conn() as conn:
        return row_to_dict(
            conn.execute("SELECT * FROM semesters WHERE is_default=1 LIMIT 1").fetchone()
        )


def create_semester(seq_no, start_date, end_date):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO semesters (seq_no, start_date, end_date, is_default, created_at)"
            " VALUES (?,?,?,0,?)",
            (int(seq_no), start_date, end_date, now_str()),
        )
        return cur.lastrowid


def update_semester(sid, seq_no, start_date, end_date):
    with get_conn() as conn:
        conn.execute(
            "UPDATE semesters SET seq_no=?, start_date=?, end_date=? WHERE id=?",
            (int(seq_no), start_date, end_date, sid),
        )


def delete_semester(sid):
    """删学期，连带删掉该学期下的课程（03 文档规则）。"""
    with get_conn() as conn:
        conn.execute("DELETE FROM courses WHERE semester_id=?", (sid,))
        conn.execute("DELETE FROM semesters WHERE id=?", (sid,))


def set_default_semester(sid):
    """先把所有学期置 0，再把目标置 1 —— 保证全表最多一个默认（03 文档规则）。"""
    with get_conn() as conn:
        conn.execute("UPDATE semesters SET is_default=0")
        conn.execute("UPDATE semesters SET is_default=1 WHERE id=?", (sid,))


# --------------------------------------------------------------------------
# 课程
# --------------------------------------------------------------------------

COURSE_FIELDS = (
    "name", "teacher", "weekdays", "start_date", "end_date",
    "start_time", "end_time", "location", "color", "note",
)


def list_courses(semester_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM courses WHERE semester_id=? ORDER BY start_time ASC, id ASC",
            (semester_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_course(cid):
    with get_conn() as conn:
        return row_to_dict(conn.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone())


def create_course(semester_id, data):
    values = [data.get(f, "") for f in COURSE_FIELDS]
    if not values[9]:
        values[9] = ""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO courses (semester_id, name, teacher, weekdays, start_date, end_date,"
            " start_time, end_time, location, color, note, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (semester_id, *values, now_str()),
        )
        return cur.lastrowid


def update_course(cid, data):
    values = [data.get(f, "") for f in COURSE_FIELDS]
    with get_conn() as conn:
        conn.execute(
            "UPDATE courses SET name=?, teacher=?, weekdays=?, start_date=?, end_date=?,"
            " start_time=?, end_time=?, location=?, color=?, note=? WHERE id=?",
            (*values, cid),
        )


def delete_course(cid):
    with get_conn() as conn:
        conn.execute("DELETE FROM courses WHERE id=?", (cid,))


# --------------------------------------------------------------------------
# 提醒（表结构照 03 文档先建好；界面属阶段 2 · R2）
# --------------------------------------------------------------------------

REMINDER_FIELDS = (
    "event", "offset_hours", "offset_minutes", "direction", "scope", "extra_fields", "enabled",
)


def list_reminders():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM reminders ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]


def create_reminder(data):
    values = [data.get(f) for f in REMINDER_FIELDS]
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (event, offset_hours, offset_minutes, direction, scope,"
            " extra_fields, enabled, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (*values, now_str()),
        )
        return cur.lastrowid


def update_reminder(rid, data):
    values = [data.get(f) for f in REMINDER_FIELDS]
    with get_conn() as conn:
        conn.execute(
            "UPDATE reminders SET event=?, offset_hours=?, offset_minutes=?, direction=?,"
            " scope=?, extra_fields=?, enabled=? WHERE id=?",
            (*values, rid),
        )


def delete_reminder(rid):
    with get_conn() as conn:
        conn.execute("DELETE FROM reminders WHERE id=?", (rid,))


if __name__ == "__main__":
    tables = init_db()
    print("数据库:", DB_PATH)
    print("已建表:", ", ".join(tables))
