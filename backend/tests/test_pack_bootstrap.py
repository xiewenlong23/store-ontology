"""测试 bootstrap 扫 packs + 兼容 verticals（P2）。"""
import pytest
from ontology.bootstrap import bootstrap
from ontology.pack import all_packs, clear_packs
from ontology.vertical import all_verticals


@pytest.fixture(autouse=True)
def _clean():
    clear_packs()
    yield
    clear_packs()


def test_bootstrap_still_discovers_verticals():
    """兼容：verticals 仍被发现（equipment_repair + clearance）。"""
    bootstrap()
    vert_names = [v.name for v in all_verticals()]
    assert "equipment_repair" in vert_names


def test_bootstrap_idempotent():
    bootstrap()
    n1 = len(all_packs()) + len(all_verticals())
    bootstrap()
    n2 = len(all_packs()) + len(all_verticals())
    assert n1 == n2


def test_bootstrap_discovers_retail_pack():
    """bootstrap 后 retail pack 被发现注册（T3 建好后）。"""
    bootstrap()
    pack_names = [p.name for p in all_packs()]
    assert "retail" in pack_names
