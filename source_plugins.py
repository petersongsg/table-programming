"""
table-programming / source_plugins.py
==========================================
传感器采集插件合集（线程安全适配）。

【规范】
1. 纯硬件读取，无业务逻辑、无状态修改
2. 所有耗时IO、硬件阻塞全部在此完成
3. 不直接操作共享ctx，统一返回局部缓存字典，由后台IO线程批量刷入

【新增传感器流程】
1. 在本文件新增 plugin_read_xxx() 函数
2. 加入 io_task_all_sensors() 字典返回值
3. 在 main.py 的 RobotContext 中新增对应字段
"""
import time


def plugin_read_emergency_btn() -> bool:
    """读取急停按钮IO（实机替换为硬件读取逻辑）"""
    return False


def plugin_read_front_lidar() -> float:
    """读取前方激光雷达距离（米）"""
    return 1.0


def plugin_read_speed() -> float:
    """读取底盘实时车速（m/s）"""
    return 0.0


def plugin_read_start_btn() -> bool:
    """读取设备启动按钮状态"""
    return False


def plugin_read_pos() -> float:
    """读取定位位置偏差（米）"""
    return 99.0


def io_task_all_sensors() -> dict:
    """
    后台IO线程批量采集入口。
    返回局部传感器缓存字典（不触碰共享ctx，绝对线程安全）。
    """
    return {
        "front_dist": plugin_read_front_lidar(),
        "speed": plugin_read_speed(),
        "emergency_btn": plugin_read_emergency_btn(),
        "start_btn": plugin_read_start_btn(),
        "pos_error": plugin_read_pos(),
    }
