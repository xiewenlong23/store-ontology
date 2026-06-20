from engine.action_loader import load_actions, ActionDefinition


def test_loads_eight_actions():
    actions = load_actions("engine/actions")
    names = set(actions.keys())
    expected = {"create_clearance_task", "submit_for_approval", "approve_clearance",
                "accept_task", "print_labels", "deduct_stock",
                "complete_task", "create_loss_report"}
    assert expected.issubset(names)


def test_action_definition_fields():
    actions = load_actions("engine/actions")
    a = actions["create_clearance_task"]
    assert isinstance(a, ActionDefinition)
    assert a.target_object_type == "NearExpiryProduct"
    assert "NearExpiryProduct" in a.edits_object_types
    assert a.submission_criteria["roles"] == ["store_manager", "region_cat_mgr"]


def test_param_constraint_parsed():
    actions = load_actions("engine/actions")
    disc = [p for p in actions["create_clearance_task"].parameters
            if p["name"] == "discount_percent"][0]
    assert disc["constraint"] == "0..100"
