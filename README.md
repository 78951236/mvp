# 课表 · Class_schedule

自己用的课程表 Web 应用：**打开浏览器就能看当周课表**，外加一个常驻的提醒程序，按你自己设的规则**到点弹通知**。

> 当前状态：**能用了**。阶段 0 ~ 阶段 3 全部做完并实测通过（tag `v0.1-mvp` → `v0.2-notify` → `v0.3-polish`）。
> 这份 README 只管「怎么装、怎么用」；要做什么、怎么设计的，看 `docs/` 下的设计文档。

---

## 一、这是什么

- **网页**：看当周课表。电脑 / 平板 / 手机都能开，不同分辨率都正常显示
- **提醒**：电脑上挂一个后台程序，按你自己设的规则（什么时候、提醒什么）到点弹 Windows 通知
- **学期与课程**：学期可以设默认；课程 8 个属性（名称、老师、周几可多选、持续时间、上下课时间、地点、颜色、备注）
- **冲突检测**：时间撞车的课，课程设置页会标红提示，课表页不画它们

---

## 二、需要什么

| 项目 | 要求 | 说明 |
| --- | --- | --- |
| 系统 | Windows 10 / 11 | **提醒程序只能在 Windows 上跑**（用了注册表和 PowerShell 通知）；只要网页的话，mac / Linux 也能跑 |
| Python | **3.10 或更高** | 实测用的是 3.12.10。装的时候**一定勾上 Add Python to PATH** |
| 浏览器 | 任意 | Chrome / Edge 都行 |
| 手机（可选） | 跟电脑**连同一个 WiFi** | 不部署公网，所以手机只能在局域网里开 |

一次都没装过 Python 的话，这是唯一一个需要点耐心的步骤：去 python.org 下载安装包，安装第一屏勾上 **Add Python to PATH**，然后一路下一步。

---

## 三、装（只做一次）

1. 把这个文件夹放到你想放的位置（路径里最好别有中文和空格）

2. 打开命令行，进到文件夹：

```
cd /d 你的路径\Class_schedule
```

3. 建虚拟环境、装依赖：

```
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```

> 装依赖时如果卡住或者报 SSL / 连接错误，换国内镜像再来一次：
> `venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

4. 验证一下装好了：

```
venv\Scripts\python schedule.py
```

最后一行应该打印 **「结果: 全部通过」**（里面是 55 项算法自测）。

---

## 四、用

### 最省事的方式：双击

| 文件 | 作用 |
| --- | --- |
| **启动课表.bat** | 启动网页服务 + 提醒程序，并自动打开浏览器 |
| **停止课表.bat** | 两个都停掉 |

启动出来的进程**不挂在命令行窗口上**——双击后窗口会自己关，服务照常在后台跑。

### 或者用命令行

```
venv\Scripts\python service.py start      # 启动两个（加 --no-browser 就不自动开浏览器）
venv\Scripts\python service.py stop       # 停掉两个
venv\Scripts\python service.py status     # 看看现在什么在跑
```

两个服务也可以单独控制：`--web-only` / `--notifier-only`。

### 开机自启（可选，建议开）

想让电脑一登录就自动跑起来，不用每次双击：

```
venv\Scripts\python service.py autostart on     # 网页服务 + 提醒程序 都设成开机自启
venv\Scripts\python service.py autostart        # 看当前状态
venv\Scripts\python service.py autostart off    # 取消
```

- 写的是**当前用户**的启动项（注册表 Run 键），**不需要管理员权限**
- 登录 Windows 时两个都在后台起来，**不会弹任何窗口**
- 只想要其中一个：加 `--web-only` 或 `--notifier-only`

### 打开网页

```
本机：http://127.0.0.1:5000
手机：http://<电脑的局域网IP>:5000     ← 启动时会打印出来，比如 http://192.168.1.100:5000
```

### 第一次打开页面的顺序

1. 页面中间会写着「你还没有设置默认学期」→ 点 **前往设置**
2. **设置 → 学期** → 右上角 **+ 添加学期** → 填学期序号和起止日期 → 确定
3. 卡片上点 **设为默认**（同时只能有一个默认学期）
4. 回**课表**页，就能看到「第 x 学期 / 第 x 周」
5. 录课：学期卡片上点 **设置** → 进课程设置页 → **+ 添加课程**
   （周几可以多选，比如一门课同时选「周一 + 周三」）

---

## 五、提醒程序

它跟着 `启动课表.bat` 一起启动，缩在**右下角托盘**里（任务栏那个 `^` 展开能看到），右键图标可以退出。

单独用：

```
venv\Scripts\python notifier.py                # 常驻，默认缩托盘
venv\Scripts\python notifier.py --no-tray      # 不缩托盘，日志打在屏幕上（排查问题用）
venv\Scripts\python notifier.py --now          # 立刻检查一次就退出，看这一分钟有没有该弹的
venv\Scripts\python notifier.py --autostart    # 设置开机自启
venv\Scripts\python notifier.py --no-autostart # 取消开机自启
```

提醒怎么配：**设置 → 提醒**。一条提醒 = 事件 + 时间差 + 提醒范围 + 附加信息，完整语义见 [`docs/04-提醒规则.md`](docs/04-提醒规则.md)。示例（也是需求文档里那两条）：

> 每一节课上课　00:30 前　提醒下一节课　名称 地点
> 新的一天到来　06:00 后　提醒今天的所有的课　上下课时间 名称

---

## 六、常见问题

**1. 提醒不弹通知**

按顺序查：

- 设置 → 系统 → 通知，确认最上面的「通知」总开关是开的，也没开免打扰
- 还不行，多半是**通知数据库卡死了**（症状：开关都开着、程序也说发送成功，但一条都不弹，通知中心历史永远是 0）。修法（不用管理员、不用重启电脑）：

```
powershell -Command "Stop-Service WpnUserService*"
# 然后把下面这个目录里的 wpndatabase.db / -shm / -wal 改名备份（加个 .bak 后缀）
#   %LOCALAPPDATA%\Microsoft\Windows\Notifications\
powershell -Command "Start-Service WpnUserService*"
```

服务重新起来后会自己重建数据库，通知立刻恢复。

**2. 启动时说「端口 5000 用不了」**

多半是已经开着一个课表服务了——浏览器直接打开 http://127.0.0.1:5000 就能用。真要同时再开一个就换端口：`venv\Scripts\python app.py --port 5001`。

**3. 手机打不开**

- 确认手机和电脑连的是**同一个 WiFi**
- 确认启动时打印的那个地址敲对了（`venv\Scripts\python service.py status` 也能看到）
- 还不行大概是 Windows 防火墙拦了 Python：第一次启动时如果弹过防火墙提示，要选**允许访问**（专用网络）

**4. 数据库坏了 / 想重来**

数据库就是一个文件：`data\class_schedule.db`。改名或删掉它，重启服务会建一个空库。

**5. 备份**

```
venv\Scripts\python backup.py
```

会在 `data\backup\` 下生成一份带日期的副本（服务开着也能备份）。还原就是把副本拷回 `data\class_schedule.db`，拷之前先把服务停掉。

---

## 七、这个项目不做什么

免得期待错位，这几条是**明确不做**的：

- **不部署到公网**，只在局域网里自己用
- **没有登录、没有账号系统**，一台电脑一份数据（`data\class_schedule.db`）
- 手机必须和电脑在**同一个 WiFi**

想让两个人各用各的：各放一个文件夹、各起一个端口，天然就分开了。

---

## 八、目录结构

```
Class_schedule/
├─ README.md                    ← 本文件（怎么装、怎么用）
├─ docs/                        ← 设计文档
│  ├─ 01-需求说明.md             ← 要做什么功能
│  ├─ 02-界面与交互设计.md        ← 长什么样、怎么点
│  ├─ 03-数据模型.md             ← 数据怎么存
│  ├─ 04-提醒规则.md             ← 提醒怎么算、怎么弹
│  └─ 05-开发计划.md             ← 分几个阶段做，MVP 放在哪
├─ app.py                       ← Flask 入口：页面 + 接口
├─ models.py                    ← 数据层（SQLite 三张表）
├─ schedule.py                  ← 算法层：周次 / 冲突 / 课表坐标 / 提醒触发时刻（自带 55 项自测）
├─ notifier.py                  ← 常驻提醒程序（Windows 通知 + 托盘 + 开机自启）
├─ service.py                   ← 一键启停（给两个 .bat 当后端）
├─ backup.py                    ← 数据备份
├─ 启动课表.bat / 停止课表.bat     ← 双击就能用
├─ requirements.txt             ← 依赖清单（版本已钉死）
├─ templates/                   ← 页面模板
├─ static/                      ← css / js
├─ venv/                        ← 虚拟环境（装的时候生成，不进版本库）
└─ data/                        ← 运行时生成（不进版本库）
   ├─ class_schedule.db         ← SQLite 数据库
   └─ backup/                   ← 备份副本
```

技术栈：Python 3 + Flask + SQLite，前端是原生 HTML / CSS / JavaScript，**不引入前端框架、没有构建步骤**。

---

## 九、文档索引

| 文档 | 内容 |
| --- | --- |
| [01-需求说明](docs/01-需求说明.md) | 四个页面 + 功能清单 + 已确认的规则 |
| [02-界面与交互设计](docs/02-界面与交互设计.md) | 配色、布局、每个页面的元素摆放、手机端适配 |
| [03-数据模型](docs/03-数据模型.md) | 学期 / 课程 / 提醒 三张表 + 周次与冲突的计算方式 |
| [04-提醒规则](docs/04-提醒规则.md) | 提醒的完整语义表 + 后台程序 + 命令行参数 |
| [05-开发计划](docs/05-开发计划.md) | 阶段划分（阶段 0 骨架 → 阶段 1 MVP → 阶段 2 提醒 → 阶段 3 打磨）+ 任务清单 + 验收场景 |

---

## 十、版本

| tag | 内容 |
| --- | --- |
| `v1.0` | **项目正式完工**：加 README 使用说明、一键启停脚本（含开机自启）、依赖版本钉死 |
| `v0.1-mvp` | 能看当周课表、能录课改课删课 |
| `v0.2-notify` | 提醒程序 + 提醒设置界面 |
| `v0.3-polish` | 冲突标红、异常兜底、界面细节、备份脚本 |
