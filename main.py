"""
table-programming / main.py
================================
主控内核：规则调度 + 线程锁 + 后台IO线程管理。

【职责固化，禁止新增业务逻辑】
- 加载 rules.json
- 启动独立后台IO线程
- 线程锁、快照拷贝、数据同步
- 单周期优先级抢占调度、冲突规避
- 规则表达式求值、异常捕获

【线程安全铁律】
- 后台IO线程：所有硬件读取放锁外，锁内仅做瞬时批量赋值
- 主线程：每周期上锁拷贝完整 ctx 快照，规则判断全程使用快照
- 禁止锁内做IO、sleep、耗时运算
"""
import json
import time
import threading
from dataclasses import dataclass, asdict
from typing import List

from context import RobotContext
from source_plugins import io_task_all_sensors
from action_plugins import ACTION_PLUGIN_REGISTRY


@dataclass
class Rule:
    """单条扁平化规则。src 仅用于文档溯源与编辑器关联，不参与实际采集。"""
    name: str
    source_plugins: List[str]
    condition_expr: str
    action_plugin: str


def load_rules(file_path: str) -> List[Rule]:
    """加载扁平化精简规则表（rules.json）。"""
    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    rule_list = []
    for item in raw_data:
        r = Rule(
            name=item["name"],
            source_plugins=item["src"],
            condition_expr=item["cond"],
            action_plugin=item["act"],
        )
        rule_list.append(r)
    return rule_list


def make_snapshot(ctx: RobotContext) -> RobotContext:
    """线程安全：拷贝一份 ctx 快照，主线程规则判断全程使用快照。"""
    return RobotContext(**asdict(ctx))


def io_background_thread(ctx: RobotContext, lock: threading.Lock, poll_interval: float = 0.05):
    """
    独立后台IO线程（线程安全终极修正）。

    核心：耗时硬件读取放锁外，锁内仅做瞬时批量赋值，临界区极致精简。
    """
    while True:
        # 1. 锁外完成所有硬件读取（阻塞、IO耗时不占用锁，不阻塞主线程）
        local_sensor_cache = io_task_all_sensors()
        # 2. 临界区：上锁，一次性批量更新所有传感器变量
        with lock:
            ctx.front_dist = local_sensor_cache["front_dist"]
            ctx.speed = local_sensor_cache["speed"]
            ctx.emergency_btn = local_sensor_cache["emergency_btn"]
            ctx.start_btn = local_sensor_cache["start_btn"]
            ctx.pos_error = local_sensor_cache["pos_error"]
            ctx.ts_io = time.time()
        time.sleep(poll_interval)


def main_loop(ctx: RobotContext, rule_table: List[Rule], lock: threading.Lock, cycle_sleep: float = 0.5):
    """
    主线程规则调度核心（永久固化，不允许写入业务逻辑）。

    - 单控制周期：上锁拷快照 -> 顺序遍历规则表 -> 命中第一条后终止本轮剩余判断
    - 规则顺序 = 优先级（自上而下递减）
    - 安全/急停/保护类规则必须置顶
    """
    tick = 0
    while True:
        tick += 1
        # 线程安全：上锁拷贝完整上下文快照，杜绝脏读、数据撕裂
        with lock:
            ctx_snapshot = make_snapshot(ctx)

        print(f"\n----- 控制周期 {tick} -----")
        print(f"状态:{ctx_snapshot.task_stage} | "
              f"车速:{ctx_snapshot.speed:.2f} | "
              f"前距:{ctx_snapshot.front_dist:.2f}")

        hit_rule = False
        # 扁平化优先级调度：单周期仅执行最高优先级命中规则，规避动作冲突
        for rule in rule_table:
            if hit_rule:
                break
            try:
                # 注入time模块，支持规则内传感器超时判断 (time.time() - ts_io) > 0.2
                eval_namespace = {"time": time}
                condition_ok = eval(rule.condition_expr, eval_namespace, ctx_snapshot.__dict__)
            except Exception as e:
                print(f"[规则异常] {rule.name} 表达式错误: {str(e)}")
                continue
            if condition_ok:
                print(f"[命中规则] {rule.name}")
                # 动作插件修改原始上下文业务状态（主线程独占，无竞争）
                ACTION_PLUGIN_REGISTRY[rule.action_plugin](ctx)
                hit_rule = True
        time.sleep(cycle_sleep)


if __name__ == "__main__":
    # 初始化全局上下文与线程读写锁
    global_ctx = RobotContext()
    data_lock = threading.Lock()

    # 启动独立守护IO线程，主程序退出自动销毁
    io_thread = threading.Thread(
        target=io_background_thread,
        args=(global_ctx, data_lock, 0.05),
        daemon=True,
    )
    io_thread.start()
    print("✅ 后台IO线程启动成功：独立轮询硬件，线程数据同步已锁保护")

    # 加载业务规则并启动主控循环
    rule_list = load_rules("rules.json")
    main_loop(global_ctx, rule_list, data_lock, cycle_sleep=0.5)
