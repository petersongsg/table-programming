# 表格编程 (Table Programming)

> 面向机器人与自动化设备的表格编程框架。业务逻辑全部写在 JSON 规则表，硬件 IO 走独立后台线程，线程安全快照同步。告别 if-else 大山、状态机嵌套、硬件阻塞业务循环。

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org) [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Architecture: 4 files](https://img.shields.io/badge/architecture-4%20files-orange.svg)](#核心架构)

[English Version →](README_EN.md) | [开发纲领 →](docs/GUIDELINE.md) | [Guideline (EN) →](docs/GUIDELINE_EN.md)

## 这是什么

传统机器人/工控项目，业务逻辑散落在代码里、状态机嵌套几十层、IO 阻塞主循环、多线程同步踩坑。本框架用 **固定 4 文件架构 + 扁平化规则表 + 后台 IO 线程 + 快照同步**，让代码只做固定载体，业务全部配置化 —— 改配置不改代码。

适合：移动机器人底盘、AGV、自动化设备控制逻辑、传感器联动、工序流转、低代码规则配置。

## 快速开始

```bash
git clone https://github.com/yourname/table-programming.git
cd table-programming

# 1) 调试硬件层（不跑业务规则）
python io_debug.py
# → 每 200ms 打印一次传感器快照,验证 IO + 锁同步

# 2) 跑正式业务
python main.py
# → 后台 IO 线程 + 主控规则循环,规则表 rules.json
```

## 核心架构

```
table-programming/
├── main.py               # 万能固定主控内核 (规则调度 + 锁 + 后台IO线程)
├── source_plugins.py     # 传感器采集插件 (纯硬件读取, 锁外IO)
├── action_plugins.py     # 执行动作插件 (硬件执行 + 状态切换, 主线程独占)
├── rules.json            # 扁平化业务规则表 (业务逻辑唯一入口)
├── io_debug.py           # 独立 IO 调试脚本 (硬件层单独验证)
├── examples/             # 额外示例
│   └── demo_chassis.json # 底盘搬运场景规则
├── tests/                # 单元测试
├── docs/                 # 完整纲领 (中文 + EN)
├── README.md             # 本文件
└── LICENSE               # MIT
```

## 核心特性

| 特性 | 说明 |
|------|------|
| **四文件绝对扁平化** | 固定 4 文件,无分层、无分组、无嵌套,新人 5 分钟看懂架构 |
| **业务配置化** | 所有业务写在 rules.json,非开发人员也能改工况 |
| **优先级抢占调度** | 规则从上到下 = 优先级从高到低,单周期仅执行第一条命中,天然规避动作冲突 |
| **IO 独立后台线程** | 硬件读取、串口、CAN 全部在锁外后台线程,绝不阻塞主循环 |
| **线程安全快照** | 主线程每周期上锁拷贝完整 ctx 快照,规则判断全程使用快照,杜绝脏读 |
| **分层调试** | io_debug.py 独立验证硬件,main.py 跑业务,问题精准定位 |
| **软状态机** | 工序/工况存放在 ctx.task_stage 业务状态变量,通过规则 cond 过滤,无需硬编码状态机 |

## rules.json 格式

```json
[
  {
    "name": "全局急停保护",
    "src":  ["plugin_read_emergency_btn"],
    "cond": "emergency_btn",
    "act":  "action_full_stop"
  },
  {
    "name": "前往拾取点持续前进",
    "src":  ["plugin_read_front_lidar", "plugin_read_pos"],
    "cond": "task_stage=='go_pick' and pos_error>0.15 and front_dist>=0.6",
    "act":  "action_move_forward"
  }
]
```

字段:
- `name`: 规则名 (可读性 + 调试溯源)
- `src`: 依赖的传感器 (文档溯源,不执行采集)
- `cond`: 条件表达式 (Python 原生语法,支持 ctx 字段 + time.time())
- `act`: 命中后执行的动作插件名 (字符串映射,见 `action_plugins.py`)

## 适用场景

| ✅ 适合 | ❌ 不适合 |
|---------|----------|
| 移动机器人底盘控制 (AGV/巡检) | CPU 密集计算 (受 GIL 限制) |
| 自动化设备工控逻辑 (机械臂/传送带) | 高频实时控制 (>1kHz) |
| 传感器联动 + 工序流转 | 大规模规则 (>1000 条,全表扫描有性能损耗) |
| 低代码配置化业务迭代 | 复杂时序逻辑 (用状态机更合适) |
| 学生/工程师快速搭原型 | Web 服务/多用户 (eval 安全风险,见下方) |

## ⚠️ 安全警告 (必读)

**`rules.json` 中的 `cond` 字段使用 `eval()` 解析 Python 表达式。**

- **本项目定位**: `rules.json` 是受信任的本地配置文件,由工程师编写,**不是**外部用户提交
- **不要**从网络/不可信来源加载 `rules.json` —— 有任意代码执行风险
- **不要**在 Web 服务/多用户场景下使用本框架
- 如需对外暴露,先用 `pyparsing`/`simpleeval` 替换 `eval` (留作 TODO)

详见 [GUIDELINE.md §3.2 线程禁止行为](docs/GUIDELINE.md)

## 开发工作流

1. **硬件层适配** → 在 `source_plugins.py` 新增 `plugin_read_xxx()` + 加入 `io_task_all_sensors()` + `main.py` `RobotContext` 加字段
2. **动作层适配** → 在 `action_plugins.py` 编写 `action_xxx(ctx)` + 注册到 `ACTION_PLUGIN_REGISTRY`
3. **配置业务逻辑** → 编辑 `rules.json` 增删规则,调整顺序 = 调整优先级
4. **分层调试** → 先 `io_debug.py` 验硬件,再 `main.py` 验业务

完整纲领见 [docs/GUIDELINE.md](docs/GUIDELINE.md)

## 运行效果示例

```
✅ 后台IO线程启动成功：独立轮询硬件，线程数据同步已锁保护
----- 控制周期 1 -----
状态:idle | 车速:0.00 | 前距:1.00
----- 控制周期 2 -----
状态:idle | 车速:0.00 | 前距:1.00
...
(假设启动按钮按下,start_btn=True)
----- 控制周期 5 -----
状态:idle | 车速:0.00 | 前距:1.00
[命中规则] 待机等待启动指令
 >> 状态切换：前往拾取点
----- 控制周期 6 -----
状态:go_pick | 车速:0.00 | 前距:1.00
[命中规则] 前往拾取点持续前进
 >> 执行动作：底盘匀速前进
...
```

## 测试

```bash
cd tests
python -m unittest test_rule_engine.py -v
```

## 性能与边界

- 单周期扫描: 100 条规则 ~ 0.5ms (Python `eval` 开销)
- IO 线程轮询: 50ms 间隔 (可调)
- 内存占用: ~10MB (取决于传感器数量)
- GIL: 适合 IO 密集,CPU 密集需多进程

## 路线图 (TODO)

- [ ] 表达式沙箱 (`pyparsing`/`simpleeval` 替换 `eval`)
- [ ] Web 可视化规则编辑器
- [ ] 规则热重载 (文件监听,不停机更新)
- [ ] 传感器防抖滤波 (条件连续 N 周期才触发)
- [ ] 日志记录 (每周期匹配规则 + 状态 dump)
- [ ] 嵌入式 C++ 版本 (基于 exprtk,见 `docs/`)

## 贡献

PR / Issue 都欢迎。**架构铁律**(见 GUIDELINE §7)不可改动:
- 4 文件结构
- 单层规则表 (无嵌套无分组)
- 主线程独占动作执行
- 业务逻辑只在 `rules.json`

## 许可证

[MIT](LICENSE) — 宽松开源,商业可用。
