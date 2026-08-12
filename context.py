"""
table-programming / context.py
====================================
Global shared context dataclass (独立模块, 避免 main <-> action_plugins 循环导入).
"""
from dataclasses import dataclass


@dataclass
class RobotContext:
    """
    统一全局上下文（线程共享）。

    【读写铁律】
    1. 外源传感器变量：仅后台IO线程可写入，主线程只读（快照读取）
    2. 内源业务状态变量：仅主线程动作插件可写入，所有线程只读
    """
    # ---- 外源：传感器硬件变量（后台IO线程更新）----
    front_dist: float = 1.0
    speed: float = 0.0
    emergency_btn: bool = False
    start_btn: bool = False
    pos_error: float = 99.0
    ts_io: float = 0.0  # 传感器帧更新时间戳，用于规则内超时校验

    # ---- 内源：业务状态变量（主线程动作插件更新）----
    task_stage: str = "idle"  # idle / go_pick / gripping / go_drop
