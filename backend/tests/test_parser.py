from ontology.parser import OntologyParser


def test_parses_all_object_types():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    ids = set(p.registry.object_types.keys())
    assert {"Store", "NearExpiryProduct", "Task", "LossReport"}.issubset(ids)


def test_edits_only_flag_parsed():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    assert p.registry.object_types["NearExpiryProduct"].edits_only_via_actions is True
    assert p.registry.object_types["Store"].edits_only_via_actions is False


def test_status_parsed():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    assert p.registry.object_types["Task"].status == "active"
    assert p.registry.object_types["Task"].visibility == "prominent"


def test_link_count_and_manages_direction():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    assert len(p.registry.link_types) == 10
    m = p.registry.link_types["manages"]
    assert m.domain == "Store" and m.range == "Employee"  # 修正后方向


def test_new_links_present():
    p = OntologyParser(ttl_path="ontology/store.ttl", data_dir="../data")
    for name in ["assigned_to", "has_loss_report", "written_off"]:
        assert name in p.registry.link_types
