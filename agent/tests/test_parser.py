from engine.parser import OntologyParser


def test_parses_all_object_types():
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    ids = set(p.registry.object_types.keys())
    assert {"Store", "Employee", "Task", "Region"}.issubset(ids)


def test_edits_only_flag_parsed():
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    assert p.registry.object_types["Task"].edits_only_via_actions is True
    assert p.registry.object_types["Store"].edits_only_via_actions is False


def test_status_parsed():
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    assert p.registry.object_types["Task"].status == "active"
    assert p.registry.object_types["Task"].visibility == "prominent"


def test_link_count_and_manages_direction():
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    assert len(p.registry.link_types) == 6
    m = p.registry.link_types["manages"]
    assert m.domain == "Store" and m.range == "Employee"  # 修正后方向


def test_new_links_present():
    p = OntologyParser(ttl_path="../workspace/retail/ontology/domains/organization/domain.ttl", data_dir="../workspace/retail/data")
    for name in ["located_in", "has_employee", "manages"]:
        assert name in p.registry.link_types
