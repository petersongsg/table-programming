"""
table-programming / action_plugins.py
=========================================
执行动作插件合集（主线程独占，线程安全）。

【规范】
1. 仅主线程执行，无多线程竞争
2. 可输出硬件指令、修改业务状态变量 task_stage
3. 禁止写入传感器外源变量，禁止编写业务if-else逻辑
4. 所有业务判断统一交由 rules.json 规则表实现

【两类动作】
- 硬件执行动作：刹车、前进、夹爪、报警、输出IO
- 状态迁移动作：仅修改 task_stage，无硬件输出，用于工序流转

【新增动作流程】
1. 编写函数（接 ctx: RobotContext）
2. 注册到 ACTION_PLUGIN_REGISTRY 字典
3. 在 rules.json 中引用函数名字符串
"""
from typing import Dict, Callable

from context import RobotContext


# ============================================================
# 硬件执行动作
# ============================================================

def action_full_stop(ctx: RobotContext) -> None:
    """全局急停（最高优先级保护）。"""
    ctx.speed = 0.0
    ctx.task_stage = "idle"
    print(" >> 执行动作：全局紧急停机")


def action_brake(ctx: RobotContext) -> None:
    """障碍物紧急刹车。"""
    ctx.speed = 0.0
    print(" >> 执行动作：障碍刹车")


def action_move_forward(ctx: RobotContext) -> None:
    """底盘持续前进。"""
    ctx.speed = 0.4
    print(" >> 执行动作：底盘匀速前进")


def action_gripper_close(ctx: RobotContext) -> None:
    """夹爪闭合抓取物料。"""
    print(" >> 执行动作：夹爪闭合抓取")


# ============================================================
# 业务状态迁移动作（仅修改 task_stage，无硬件输出）
# ============================================================

def action_set_go_pick(ctx: RobotContext) -> None:
    """状态切换：前往拾取点。"""
    ctx.task_stage = "go_pick"
    print(" >> 状态切换：前往拾取点")


def action_set_gripping(ctx: RobotContext) -> None:
    """状态切换：执行物料抓取。"""
    ctx.task_stage = "gripping"
    print(" >> 状态切换：执行物料抓取")


def action_set_go_drop(ctx: RobotContext) -> None:
    """状态切换：前往卸料点。"""
    ctx.task_stage = "go_drop"
    print(" >> 状态切换：前往卸料点")


# ============================================================
# 动作注册表（字符串映射函数，支持规则表动态调用）
# ============================================================

ACTION_PLUGIN_REGISTRY: Dict[str, Callable[[RobotContext], None]] = {
    "action_full_stop":     action_full_stop,
    "action_brake":         action_brake,
    "action_move_forward":  action_move_forward,
    "action_gripper_close":  action_gripper_close,
    "action_set_go_pick":    action_set_go_pick,
    "action_set_gripping":   action_set_gripping,
    "action_set_go_drop":    action_set_go_drop,
}
