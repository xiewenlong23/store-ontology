"""启动时发现并注册所有 vertical。

扫描 backend/verticals/*/config.py，import 之（每个 config.py 在 import 时调用
register_vertical）。main.py 调用 bootstrap() 一次即可。

这是接入新 vertical 的唯一"接线"动作：放一个 backend/verticals/<name>/config.py，
下次启动自动被发现。无需改任何 kernel 文件。
"""
import importlib
import os
import pkgutil


def bootstrap() -> None:
    """发现并注册所有 vertical（幂等，重复调用安全）。"""
    import verticals  # backend/verticals 包
    pkg_path = os.path.dirname(verticals.__file__)
    for _, name, ispkg in pkgutil.iter_modules([pkg_path]):
        if not ispkg:
            continue
        try:
            importlib.import_module(f"verticals.{name}.config")
        except ModuleNotFoundError:
            # 该 vertical 没有 config.py，跳过
            continue
        except Exception as e:  # noqa: BLE001
            # 注册失败不阻塞其它 vertical，但打印警告
            print(f"[bootstrap] 注册 vertical '{name}' 失败: {e}")
