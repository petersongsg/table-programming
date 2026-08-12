"""
table-programming / io_debug.py
=====================================
IO线程独立调试工具（不加载任何业务规则、不运行控制逻辑）。

【用途】
- 单独验证所有传感器读取是否正常
- 验证线程锁同步是否正常、无数据撕裂
- 查看传感器刷新频率、数据稳定性
- 排查硬件阻塞、卡死、数据不更新问题

【运行】
    python io_debug.py

【特点】
不加载规则、不执行业务动作、纯硬件数据监测。调试通过后，
再运行正式 main.py，可彻底排除硬件层问题，专注调试业务规则。
"""
import time
import threading

from main import RobotContext, make_snapshot
from source_plugins import io_task_all_sensors


# 全局变量初始化
ctx = RobotContext()
data_lock = threading.Lock()
POLL_INTERVAL = 0.05  # 与正式工程一致：50ms硬件刷新周期


def io_background_debug_thread():
    """完全复刻正式工程的IO后台线程逻辑（锁外IO、锁内批量赋值）。"""
    while True:
        # 1. 锁外读取所有传感器（耗时IO不占用锁）
        local_cache = io_task_all_sensors()
        # 2. 临界区批量更新共享上下文，线程安全
        with data_lock:
            ctx.front_dist = local_cache["front_dist"]
            ctx.speed = local_cache["speed"]
            ctx.emergency_btn = local_cache["emergency_btn"]
            ctx.start_btn = local_cache["start_btn"]
            ctx.pos_error = local_cache["pos_error"]
            ctx.ts_io = time.time()
        time.sleep(POLL_INTERVAL)


def print_sensor_status():
    """周期打印完整传感器状态，模拟主控快照读取逻辑。"""
    with data_lock:
        snap = make_snapshot(ctx)
    print("=" * 60)
    print(f"更新时间戳: {snap.ts_io:.2f}")
    print(f"前方距离: {snap.front_dist:.2f} m")
    print(f"底盘速度: {snap.speed:.2f} m/s")
    print(f"急停按钮: {snap.emergency_btn}")
    print(f"启动按钮: {snap.start_btn}")
    print(f"位置偏差: {snap.pos_error:.2f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # 启动IO守护线程
    t = threading.Thread(target=io_background_debug_thread, daemon=True)
    t.start()
    print("【IO调试模式启动成功】")
    print("后台传感器线程运行中，开始实时打印数据...\n")

    # 主线程循环打印数据（模拟主控快照读取）
    while True:
        print_sensor_status()
        time.sleep(0.2)
