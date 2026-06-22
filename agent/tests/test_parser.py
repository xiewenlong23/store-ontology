from engine.parser import OntologyParser


def test_parses_all_object_types():
    """v2（WP4）：organization 含 OrgUnit/Store/Task/Region；Employee 移到 personnel。"""
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    ids = set(p.registry.object_types.keys())
    assert {"Store", "Task", "Region", "OrgUnit"}.issubset(ids)


def test_edits_only_flag_parsed():
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    assert p.registry.object_types["Task"].edits_only_via_actions is True
    assert p.registry.object_types["Store"].edits_only_via_actions is False


def test_status_parsed():
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    assert p.registry.object_types["Task"].status == "active"
    assert p.registry.object_types["Task"].visibility == "prominent"


def test_link_count_and_manages_direction():
    """v2（WP4）：organization 的 Link 集合变化（has_employee/manages 移到 personnel；
    新增 parent_of）。本测只验证 organization 域内现存的 located_in。"""
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    # 位于（Store→Region）仍在 organization
    m = p.registry.link_types["located_in"]
    assert m.domain == "Store" and m.range == "Region"
    # parent_of（OrgUnit 自引用）新增
    assert "parent_of" in p.registry.link_types


def test_new_links_present():
    """v2（WP4）：has_employee/manages 移到 personnel domain；
    organization 含 located_in + parent_of。"""
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    for name in ["located_in", "parent_of"]:
        assert name in p.registry.link_types
    # has_employee 不在 organization（已迁移到 personnel）
    assert "has_employee" not in p.registry.link_types


def test_personnel_domain_has_employee():
    """v2（WP4）：Employee 现在在 personnel domain。"""
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/personnel/domain.ttl", data_dir="../workspace/retail/data")
    assert "Employee" in p.registry.object_types
    assert "has_employee" in p.registry.link_types
    assert "manages" in p.registry.link_types
