"""启动时发现并注册所有 pack + vertical（P2 升级）。

P2: 扫描 packs/*/pack.py 注册 IndustryPack + 扫描 verticals/*/config.py 注册 VerticalConfig（兼容）。
main.py 调用 bootstrap() 一次即可。幂等。
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
    """发现并注册所有 pack + vertical（幂等，重复调用安全）。"""
    _discover_packages("packs", "pack", "pack")
    _discover_packages("verticals", "config", "vertical")
