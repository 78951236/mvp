"""课表服务的一键启停（给「启动课表.bat / 停止课表.bat」当后端，也可以自己敲）。

    venv\\Scripts\\python service.py status      # 看看现在什么在跑
    venv\\Scripts\\python service.py start       # 启动网页服务 + 提醒程序（浏览器会自动打开）
    venv\\Scripts\\python service.py start --no-browser
    venv\\Scripts\\python service.py stop        # 两个都停
    venv\\Scripts\\python service.py stop --web-only

启动出来的进程是**独立进程**：不挂在命令行窗口上，关掉窗口它们照样跑。
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(BASE, "venv", "Scripts", "python.exe")
PYW = os.path.join(BASE, "venv", "Scripts", "pythonw.exe")

sys.path.insert(0, BASE)

DEFAULT_PORT = 5000


# --------------------------------------------------------------------------
# 进程探测
# --------------------------------------------------------------------------

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace")


def port_pids(port):
    """谁在监听这个端口（从 netstat 里捞 PID，不用命令名去匹配，免得误伤自己）。"""
    out = _run(["netstat", "-ano"]).stdout
    pids = set()
    for line in out.splitlines():
        if "LISTENING" in line and re.search(r":%d\s" % port, line):
            pid = line.split()[-1]
            if pid.isdigit() and pid != "0":
                pids.add(int(pid))
    return sorted(pids)


def pids_by_command(fragment):
    """按命令行片段找 python 进程。只看 python* 进程名，不会匹配到 powershell 自己。"""
    ps = ("Get-CimInstance Win32_Process | "
          "Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*%s*' } | "
          "ForEach-Object { $_.ProcessId }" % fragment)
    out = _run(["powershell", "-NoProfile", "-Command", ps]).stdout
    return sorted(int(x) for x in out.split() if x.strip().isdigit())


def notifier_pids():
    return pids_by_command("notifier[.]py")


def web_pids(port):
    return port_pids(port)


def http_ok(port, timeout=5):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/schedule" % port, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


# --------------------------------------------------------------------------
# 开机自启（HKCU 的 Run 键，不需要管理员权限）
# --------------------------------------------------------------------------

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WEB_AUTOSTART_NAME = "ClassScheduleWeb"


def web_autostart_command():
    """网页服务的自启命令。

    这里必须用 pythonw：Run 键是在登录时直接拉起进程的，用 python.exe 会**弹一个黑窗口**出来。
    pythonw 没有控制台，app.py 的那些 print 会变成静默无操作（不会报错），
    网页服务和请求日志都照常工作，只是没有窗口。
    """
    return '"%s" "%s"' % (PYW, os.path.join(BASE, "app.py"))


def _read_run_value(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            return winreg.QueryValueEx(key, name)[0]
    except Exception:
        return None


def _write_run_value(name, command):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
        if command is None:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)


def web_autostart_state():
    return _read_run_value(WEB_AUTOSTART_NAME)


def set_web_autostart(enabled):
    _write_run_value(WEB_AUTOSTART_NAME, web_autostart_command() if enabled else None)


def notifier_autostart_state():
    import notifier
    return notifier.autostart_state()


def set_notifier_autostart(enabled):
    import notifier
    notifier.set_autostart(enabled)


# --------------------------------------------------------------------------
# 启动
# --------------------------------------------------------------------------

def spawn(exe, script_args, hidden=True):
    """起一个独立进程（不挂在本窗口上）。"""
    cmd = ["powershell", "-NoProfile", "-Command",
           "Start-Process -FilePath '%s' -ArgumentList %s -WorkingDirectory '%s'%s"
           % (exe,
              ",".join("'%s'" % a for a in script_args),
              BASE,
              " -WindowStyle Hidden" if hidden else "")]
    return _run(cmd)


def start_web(port, quiet=False):
    pids = web_pids(port)
    if pids:
        if not quiet:
            print("  网页服务：已经在跑了（PID %s），没有再起第二个。" % ", ".join(map(str, pids)))
        return True

    if not os.path.exists(PY):
        print("  网页服务：找不到 %s" % PY)
        print("  先按 README 里的「装」那几步把虚拟环境建好。")
        return False

    # 端口被别人占着就先说清楚，别让新用户对着一个白屏猜
    import app as app_module
    free, why = app_module.port_free("0.0.0.0", port)
    if not free:
        print("  网页服务：端口 %d 起不来 —— %s" % (port, why))
        print("  换个端口：venv\\Scripts\\python app.py --port %d" % (port + 1))
        return False

    spawn(PY, ["app.py", "--port", str(port)])
    for _ in range(20):
        time.sleep(0.5)
        if http_ok(port):
            if not quiet:
                print("  网页服务：已启动（端口 %d）" % port)
            return True
    print("  网页服务：没能起来，等一下看看，或者手动跑 venv\\Scripts\\python app.py 看报什么错。")
    return False


def start_notifier(quiet=False):
    pids = notifier_pids()
    if pids:
        if not quiet:
            print("  提醒程序：已经在跑了（PID %s），没有再起第二个。" % ", ".join(map(str, pids)))
        return True

    if not os.path.exists(PYW):
        print("  提醒程序：找不到 %s" % PYW)
        return False

    spawn(PYW, ["notifier.py"])
    time.sleep(2.5)
    if notifier_pids():
        if not quiet:
            print("  提醒程序：已启动（缩在右下角托盘里，右键图标可以退出）")
        return True
    print("  提醒程序：没能起来，手动跑 venv\\Scripts\\python notifier.py --no-tray 看报什么错。")
    return False


# --------------------------------------------------------------------------
# 停止
# --------------------------------------------------------------------------

def stop_pids(pids, what):
    if not pids:
        print("  %s：本来就没在跑。" % what)
        return True
    ps = "Stop-Process -Id %s -Force -ErrorAction SilentlyContinue" % ",".join(str(p) for p in pids)
    _run(["powershell", "-NoProfile", "-Command", ps])
    time.sleep(1.5)
    print("  %s：已停掉（PID %s）。" % (what, ", ".join(map(str, pids))))
    return True


# --------------------------------------------------------------------------
# 命令
# --------------------------------------------------------------------------

def cmd_status(port):
    wpids = web_pids(port)
    if wpids:
        print("  网页服务：跑着（PID %s）" % ", ".join(map(str, wpids)))
        print("    本机：http://127.0.0.1:%d" % port)
        ip = lan_ip()
        if ip:
            print("    手机：http://%s:%d（要跟电脑同一个 WiFi）" % (ip, port))
        print("    页面响应：%s" % ("正常" if http_ok(port) else "连上了但不响应，可能正在启动"))
    else:
        print("  网页服务：没在跑")

    npids = notifier_pids()
    print("  提醒程序：%s" % ("跑着（PID %s，在右下角托盘里）" % ", ".join(map(str, npids)) if npids else "没在跑"))

    try:
        import notifier
        print("  系统通知：%s" % ("开着" if notifier.notifications_enabled() else "关着（收不到通知，去 设置 → 系统 → 通知 打开）"))
    except Exception:
        pass
    return 0


def cmd_start(port, web_only, notifier_only, no_browser):
    print("正在启动课表……")
    ok = True
    if not notifier_only:
        ok = start_web(port) and ok
    if not web_only:
        ok = start_notifier() and ok

    if not notifier_only:
        print()
        print("  本机打开：http://127.0.0.1:%d" % port)
        ip = lan_ip()
        if ip:
            print("  手机打开：http://%s:%d（要跟电脑同一个 WiFi）" % (ip, port))
        if not no_browser and http_ok(port):
            import webbrowser
            webbrowser.open("http://127.0.0.1:%d" % port)
            print("  已经帮你把浏览器打开了。")
    return 0 if ok else 1


def cmd_stop(port, web_only, notifier_only):
    print("正在停止课表……")
    if not notifier_only:
        stop_pids(web_pids(port), "网页服务")
    if not web_only:
        stop_pids(notifier_pids(), "提醒程序")
    return 0


def cmd_autostart(value, web_only, notifier_only):
    if value == "status":
        print("  网页服务自启：%s" % (web_autostart_state() or "没开"))
        print("  提醒程序自启：%s" % (notifier_autostart_state() or "没开"))
        return 0

    enable = value == "on"
    if not notifier_only:
        set_web_autostart(enable)
        print("  网页服务自启：%s" % ("已打开" if enable else "已关闭"))
    if not web_only:
        set_notifier_autostart(enable)
        print("  提醒程序自启：%s" % ("已打开" if enable else "已关闭"))

    print()
    if enable:
        if web_only:
            who = "网页服务"
        elif notifier_only:
            who = "提醒程序"
        else:
            who = "两个"
        print("  下次登录 Windows 时%s会自己起来（没有窗口，不会弹东西）。" % who)
        print("  现在想立刻用，还是跑一遍：venv\\Scripts\\python service.py start")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="课表服务的一键启停")
    parser.add_argument("action", choices=["start", "stop", "status", "autostart"], help="要做的事")
    parser.add_argument("value", nargs="?", default=None,
                        help="autostart 用：on / off（不填就是看状态）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="网页服务端口（默认 %d）" % DEFAULT_PORT)
    parser.add_argument("--web-only", action="store_true", help="只动网页服务")
    parser.add_argument("--notifier-only", action="store_true", help="只动提醒程序")
    parser.add_argument("--no-browser", action="store_true", help="启动后不要自动开浏览器")
    args = parser.parse_args(argv)

    if not os.path.exists(PY):
        print("找不到虚拟环境：%s" % PY)
        print("先按 README 的「装」那几步建好 venv 再回来。")
        return 1

    if args.action == "status":
        return cmd_status(args.port)
    if args.action == "start":
        return cmd_start(args.port, args.web_only, args.notifier_only, args.no_browser)
    if args.action == "autostart":
        if args.value not in (None, "on", "off", "status"):
            print("autostart 只认 on / off（不填就是看状态），你写的是：%s" % args.value)
            return 2
        return cmd_autostart(args.value or "status", args.web_only, args.notifier_only)
    return cmd_stop(args.port, args.web_only, args.notifier_only)


if __name__ == "__main__":
    sys.exit(main())
