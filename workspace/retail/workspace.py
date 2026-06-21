"""retail 工作目录（示例）。3 能力域 + 1 价值链流程（clearance）。

目录结构：ontology/domains/<域>/ + data/ + skills/。
"""
import os

from engine.pack import WorkspaceDef, CapabilityDomain, ValueChainProcess, register_workspace_dir
from engine.state_machine import TASK_TRANSITIONS, TERMINAL_STATES

_BASE = os.path.dirname(os.path.abspath(__file__))

MARKETING = CapabilityDomain(
    name="marketing", display_name="营销域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "marketing", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "marketing", "actions"),
    rules_dir=os.path.join(_BASE, "ontology", "domains", "marketing", "rules"))

ORGANIZATION = CapabilityDomain(
    name="organization", display_name="组织域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "organization", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "organization", "actions"))

FINANCE = CapabilityDomain(
    name="finance", display_name="财务域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "finance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "finance", "actions"))

CLEARANCE = ValueChainProcess(
    name="clearance", display_name="出清",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "skills"),
    tools_module="workspace.retail.skills.clearance_workflow.tools",
    actions_dir=os.path.join(_BASE, "skills", "clearance_workflow", "actions"),
    system_prompt_intro="你是门店临期商品管理助手。")

RETAIL_WS = WorkspaceDef(
    name="retail", display_name="零售（示例）",
    domains=[MARKETING, ORGANIZATION, FINANCE],
    processes=[CLEARANCE],
    data_dir=os.path.join(_BASE, "data"))

register_workspace_dir(RETAIL_WS)
