"""提醒程序（阶段 2）：常驻后台，到点弹 Windows 系统通知。

照 docs/04-提醒规则.md 实现：
    venv\\Scripts\\python notifier.py                 # 常驻；**默认缩到右下角托盘**，不弹窗口打扰你
    venv\\Scripts\\python notifier.py --no-tray       # 不缩托盘，就在当前命令行里跑（看日志用）
    venv\\Scripts\\python notifier.py --now           # 立刻检查一次并退出（测试用）
    venv\\Scripts\\python notifier.py --autostart     # 设置开机自启
    venv\\Scripts\\python notifier.py --no-autostart  # 取消开机自启

不带参数时的默认：**缩到右下角托盘、不设开机自启**（默认值按需求方 2026-10-16 的拍板）。
"""

import argparse
import base64
import datetime
import os
import subprocess
import sys
import time

import models
import schedule as sched

# PowerShell 自己的 AppID —— 用它弹通知不需要注册任何东西
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "ClassScheduleNotifier"
DEFAULT_INTERVAL = 30      # 每 30 秒读一次库
WINDOW_SECONDS = 60        # 「从现在起到下一分钟」（04 文档第六节）


# --------------------------------------------------------------------------
# 系统通知
# --------------------------------------------------------------------------

def _xml_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def notifications_enabled():
    """系统通知总开关（设置 → 系统 → 通知）。查不到就当作开着。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\PushNotifications") as key:
            return winreg.QueryValueEx(key, "ToastEnabled")[0] != 0
    except Exception:
        return True


def show_toast(title, body):
    """弹一条 Windows 系统通知。返回 (是否成功, 出错信息)。"""
    xml = ('<toast duration="long"><visual><binding template="ToastGeneric">'
           '<text>%s</text><text>%s</text>'
           '</binding></visual></toast>' % (_xml_escape(title), _xml_escape(body)))
    ps = (
        '[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n'
        '[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null\n'
        '$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n'
        '$xml.LoadXml(@"\n%s\n"@)\n'
        '$t = [Windows.UI.Notifications.ToastNotification]::new($xml)\n'
        '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("%s").Show($t)\n'
        'Write-Output "TOAST_SENT"\n' % (xml, APP_ID)
    )
    encoded = base64.b64encode(ps.encode("utf-16-le")).decode()
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True, timeout=30)
    except Exception as exc:
        return False, str(exc)
    if result.returncode != 0 or b"TOAST_SENT" not in result.stdout:
        err = (result.stderr or b"").decode("utf-8", "replace")
        return False, err.strip()[:200] or f"powershell 退出码 {result.returncode}"
    return True, None


# --------------------------------------------------------------------------
# 开机自启
# --------------------------------------------------------------------------

def _pythonw():
    """用一个不带控制台窗口的解释器跑常驻程序。"""
    exe = sys.executable
    candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return candidate if os.path.exists(candidate) else exe


def autostart_command():
    return '"%s" "%s"' % (_pythonw(), os.path.abspath(__file__))


def set_autostart(enabled):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
        if enabled:
            winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ,
                              autostart_command() + " --tray")
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_NAME)
            except FileNotFoundError:
                pass


def autostart_state():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            return winreg.QueryValueEx(key, AUTOSTART_NAME)[0]
    except Exception:
        return None


# --------------------------------------------------------------------------
# 读库与检查
# --------------------------------------------------------------------------

def load_state():
    """默认学期 + 该学期里「课表页会画出来」的课（冲突课程提醒里也不算）。"""
    semester = models.get_default_semester()
    if not semester:
        return None, [], []
    courses = models.list_courses(semester["id"])
    conflicts = sched.find_conflicts(courses)
    usable = [c for c in courses if c["id"] not in conflicts]
    return semester, usable, models.list_reminders()


def check_once(now=None, fired=None):
    """检查一次。返回本次要发的通知列表 [{moment, hits, title, body}]。"""
    now = now or datetime.datetime.now()
    fired = fired if fired is not None else set()
    semester, courses, reminders = load_state()

    if not semester:
        return []
    hits = sched.scan_triggers(reminders, courses, semester, now, WINDOW_SECONDS)

    fresh = []
    for hit in hits:
        key = (hit["reminder"]["id"], hit["moment"].isoformat())
        if key in fired:
            continue
        fired.add(key)
        fresh.append(hit)
    if not fresh:
        return []

    # 同一时刻命中的多条合并成一条（04 文档第六节）
    grouped = {}
    for hit in fresh:
        grouped.setdefault(hit["moment"], []).append(hit)

    out = []
    for moment, group in sorted(grouped.items()):
        title, body = sched.build_notification(group, courses)
        if title is None:          # 范围内一门课都没有 → 不发
            continue
        out.append({"moment": moment, "hits": group, "title": title, "body": body})
    return out


def describe(hit):
    r = hit["reminder"]
    return "%s %02d:%02d %s → %s" % (
        sched.EVENT_LABELS.get(r["event"], r["event"]),
        int(r.get("offset_hours") or 0), int(r.get("offset_minutes") or 0),
        "前" if r["direction"] == "before" else "后",
        sched.SCOPE_LABELS.get(r["scope"], r["scope"]))


def emit(notification, quiet=False):
    """把一条通知弹出来，同时打日志。"""
    stamp = notification["moment"].strftime("%m-%d %H:%M")
    if not quiet:
        print("[%s] 合并 %d 条提醒 → 弹出通知" % (stamp, len(notification["hits"])))
        for hit in notification["hits"]:
            print("    · 提醒#%s %s" % (hit["reminder"]["id"], describe(hit)))
        for line in notification["body"].split("\n"):
            print("      %s" % line)
    ok, err = show_toast(notification["title"], notification["body"])
    if not ok and not quiet:
        print("    !! 通知没弹出来：%s" % err)
    return ok


# --------------------------------------------------------------------------
# 主循环
# --------------------------------------------------------------------------

def run_loop(interval=DEFAULT_INTERVAL, tray=True):
    fired = set()
    if not notifications_enabled():
        print("!! 系统通知开关是关着的（HKCU\\...\\PushNotifications\\ToastEnabled = 0），")
        print("   通知不会弹出来。打开：设置 → 系统 → 通知 → 打开「通知」。")
        print()

    stop_flag = {"stop": False}

    if tray:
        tray_handle = _start_tray(stop_flag)
        if tray_handle is None:
            print("（没装 pystray，托盘起不来，就当前台程序跑：Ctrl+C 退出）\n")

    print("提醒程序已启动：每 %d 秒读一次数据库，Ctrl+C 退出。" % interval)
    print("数据库：%s" % models.DB_PATH)
    semester, courses, reminders = load_state()
    if not semester:
        print("（还没有默认学期，暂时不会提醒）")
    else:
        print("默认学期：第 %s 学期；%d 门课（已排除冲突课）；%d 条提醒（其中 %d 条开着）"
              % (semester["seq_no"], len(courses), len(reminders),
                 sum(1 for r in reminders if r.get("enabled"))))
    print()

    try:
        while not stop_flag["stop"]:
            for notification in check_once(fired=fired):
                emit(notification)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n已退出（Ctrl+C）。")
    return 0


def _start_tray(stop_flag):
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    icon_img = Image.new("RGB", (64, 64), "#2F6FED")
    draw = ImageDraw.Draw(icon_img)
    draw.rectangle([10, 12, 54, 52], outline="white", width=4)   # 一个像课表的小方块
    draw.line([10, 26, 54, 26], fill="white", width=4)

    def on_quit(icon, item):
        stop_flag["stop"] = True
        icon.stop()

    icon = pystray.Icon(AUTOSTART_NAME, icon_img, "课表提醒", menu=pystray.Menu(
        pystray.MenuItem("退出", on_quit)))
    icon.run_detached()
    return icon


def main(argv=None):
    parser = argparse.ArgumentParser(description="课表提醒程序")
    parser.add_argument("--now", action="store_true", help="立刻检查一次并退出（测试用）")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help="每隔多少秒读一次数据库（默认 %d）" % DEFAULT_INTERVAL)
    tray = parser.add_mutually_exclusive_group()
    tray.add_argument("--tray", dest="tray", action="store_true", help="缩到右下角托盘（默认）")
    tray.add_argument("--no-tray", dest="tray", action="store_false", help="不缩托盘，在当前命令行里跑")
    parser.set_defaults(tray=True)
    auto = parser.add_mutually_exclusive_group()
    auto.add_argument("--autostart", dest="autostart", action="store_true", help="设置开机自启")
    auto.add_argument("--no-autostart", dest="autostart", action="store_false", help="取消开机自启")
    parser.set_defaults(autostart=None)
    args = parser.parse_args(argv)

    models.init_db()

    if args.autostart is not None:
        set_autostart(args.autostart)
        if args.autostart:
            print("已设置开机自启：%s" % autostart_command())
        else:
            print("已取消开机自启。")
        return 0

    if args.now:
        now = datetime.datetime.now()
        print("检查一下：%s" % now.strftime("%Y-%m-%d %H:%M:%S"))
        print("窗口：%s ~ %s" % (now.strftime("%H:%M:%S"),
                                 (now + datetime.timedelta(seconds=WINDOW_SECONDS)).strftime("%H:%M:%S")))
        semester, courses, reminders = load_state()
        if not semester:
            print("还没有默认学期 → 不提醒。")
            return 0
        print("默认学期：第 %s 学期；%d 门课；%d 条提醒" % (semester["seq_no"], len(courses), len(reminders)))
        todo = check_once(now=now)
        if not todo:
            print("这一分钟内没有到点的提醒。")
            return 0
        if not notifications_enabled():
            print("!! 系统通知开关是关着的，通知不会弹出来。")
        for notification in todo:
            emit(notification)
        return 0

    return run_loop(interval=args.interval, tray=args.tray)


if __name__ == "__main__":
    sys.exit(main())
