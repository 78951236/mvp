"""数据备份（阶段 3 · P4）：把 data\\class_schedule.db 存成一份带日期的副本。

    venv\\Scripts\\python backup.py

备份落到 `data\\backup\\class_schedule-<年月日-时分秒>.db`。
还原：把备份文件拷回 `data\\class_schedule.db` 就行 —— 拷之前先把 app.py 和 notifier.py 停掉。

用的是 SQLite 自带的在线备份接口（不是直接拷文件），所以服务正开着你也能备份，
不会拷到半个事务。
"""

import datetime
import os
import sqlite3
import sys

import models

BACKUP_DIR = os.path.join(os.path.dirname(models.DB_PATH), "backup")


def main(argv=None):
    if not os.path.exists(models.DB_PATH):
        print("还没有数据库文件：%s" % models.DB_PATH)
        print("（服务跑起来之后才会建，现在不用备份。）")
        return 1

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, "class_schedule-%s.db" % stamp)

    src = sqlite3.connect(models.DB_PATH)
    dst = sqlite3.connect(dest)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()

    # 备份出来核一遍：里面到底有多少东西
    check = sqlite3.connect(dest)
    try:
        semesters = check.execute("SELECT COUNT(*) FROM semesters").fetchone()[0]
        courses = check.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        reminders = check.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
    finally:
        check.close()

    print("备份完成：%s" % dest)
    print("  大小：%.1f KB" % (os.path.getsize(dest) / 1024))
    print("  内容：%d 个学期、%d 门课、%d 条提醒" % (semesters, courses, reminders))
    print()
    print("还原方法：停掉 app.py 和 notifier.py，把这个文件拷回 %s" % models.DB_PATH)
    print("要是懒得挑，用最新的那份：")
    newest = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith(".db"))[-1]
    print("  copy \"%s\" \"%s\"" % (os.path.join(BACKUP_DIR, newest), models.DB_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
