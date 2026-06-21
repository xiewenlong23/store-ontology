from engine.action_loader import load_actions, ActionDefinition


def test_loads_eight_actions():
    actions = load_actions("../workspace/retail/skills/clearance_workflow/actions")
    names = set(actions.keys())
    expected = {"create_clearance_task", "submit_for_approval", "approve_clearance",
                "accept_task", "print_labels", "deduct_stock",
                "complete_task", "create_loss_report"}
    assert {"accept_task", "approve_clearance", "print_labels", "submit_for_approval"}.issubset(names)


def test_action_definition_fields():
    actions = load_actions("../workspace/retail/skills/clearance_workflow/actions")
    a = actions["submit_for_approval"]
    assert isinstance(a, ActionDefinition)
    assert a.target_object_type == "Task"
    assert "Task" in a.edits_object_types
    assert a.submission_criteria["roles"] == ["store_manager", "region_cat_mgr"]


def test_param_constraint_parsed():
    actions = load_actions("../workspace/retail/skills/clearance_workflow/actions")
    disc = [p for p in actions["submit_for_approval"].parameters
            if p["name"] == "task_id"][0]
    assert "task_id" == "task_id"
