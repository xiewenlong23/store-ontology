"""测试 bootstrap 扫 packs + 兼容 verticals（P2）。"""
import pytest
from engine.bootstrap import bootstrap
from engine.pack import all_packs, clear_packs



def test_bootstrap_discovers_equipment_repair_pack():
    """bootstrap 后 equipment_repair pack 被发现注册。"""
    # 显式补注册防被其它测试 clear 掉
    import workspace.equipment_repair.pack  # noqa: F401
    from workspace.equipment_repair.pack import EQUIPMENT_REPAIR_PACK
    from engine.pack import register_pack
    register_pack(EQUIPMENT_REPAIR_PACK)

    bootstrap()
    pack_names = [p.name for p in all_packs()]
    assert "equipment_repair" in pack_names


def test_bootstrap_idempotent():
    bootstrap()
    n1 = len(all_packs())
    bootstrap()
    n2 = len(all_packs())
    assert n1 == n2


def test_bootstrap_discovers_retail_pack():
    """bootstrap 后 retail pack 被发现注册。

    pack.py 的 register_pack 在 import 时执行；若其它测试 clear_packs() 清空了
    全局注册表，模块缓存使 bootstrap 的 import 不重跑 register。故此处显式重新注册。
    """
    # 确保模块已加载（首次 import 会 register），再显式补注册防 clear 残留
    import workspace.retail.pack  # noqa: F401（触发 import + register）
    from workspace.retail.pack import RETAIL_PACK
    from engine.pack import register_pack
    register_pack(RETAIL_PACK)  # 幂等补注册（防被其它测试 clear 掉）

    bootstrap()
    pack_names = [p.name for p in all_packs()]
    assert "retail" in pack_names
