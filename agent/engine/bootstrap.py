"""启动时发现并注册所有 workspace 工作目录。

扫描 workspace/*/workspace.py（新）注册工作目录（WorkspaceDef）。
兼容尚未改名的 workspace/*/pack.py。main.py 调用 bootstrap() 一次即可。幂等。
"""
import importlib
import os
import pkgutil


def _discover_packages(pkg_name: str, file_name: str, label: str) -> None:
    """通用发现：扫描 <pkg_name>/*/<file_name>，import 之。"""
    try:
        pkg = importlib.import_module(pkg_name)
    except ImportError:
        return
    pkg_path = os.path.dirname(pkg.__file__)
    names = sorted(name for _, name, ispkg in pkgutil.iter_modules([pkg_path]) if ispkg)
    for name in names:
        try:
            importlib.import_module(f"{pkg_name}.{name}.{file_name}")
        except ModuleNotFoundError:
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[bootstrap] 注册 {label} '{name}' 失败: {e}")


def bootstrap() -> None:
    """发现并注册所有 workspace 工作目录（幂等，重复调用安全）。

    优先扫 workspace.py（新），兼容 pack.py（旧）。两者都 import 触发自注册。
    """
    _discover_packages("workspace", "workspace", "workspace")
    _discover_packages("workspace", "pack", "workspace")  # 兼容尚未改名的工作目录
