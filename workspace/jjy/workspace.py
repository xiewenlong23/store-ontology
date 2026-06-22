"""jjy 工作目录（客户实例）。3 能力域 + 1 价值链流程（clearance）。

从 retail 拷贝初始化，后续客户可自定义本体/数据/skill。
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

PERSONNEL = CapabilityDomain(
    name="personnel", display_name="人员域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "personnel", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "personnel", "actions"))

CATEGORY = CapabilityDomain(
    name="category", display_name="品类域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "category", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "category", "actions"))

FINANCE = CapabilityDomain(
    name="finance", display_name="财务域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "finance", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "finance", "actions"))

IDENTITY = CapabilityDomain(
    name="identity", display_name="身份域",
    ttl_path=os.path.join(_BASE, "ontology", "domains", "identity", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "ontology", "domains", "identity", "actions"))

CLEARANCE = ValueChainProcess(
    name="clearance", display_name="出清",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    skills_dir=os.path.join(_BASE, "skills"),
    tools_module="workspace.jjy.skills.clearance_workflow.tools",
    actions_dir=os.path.join(_BASE, "skills", "clearance_workflow", "actions"),
    system_prompt_intro="你是门店临期商品管理助手。")

JJY_WS = WorkspaceDef(
    name="jjy", display_name="客户 jjy",
    domains=[MARKETING, ORGANIZATION, PERSONNEL, CATEGORY, FINANCE, IDENTITY],
    processes=[CLEARANCE],
    data_dir=os.path.join(_BASE, "data"))

register_workspace_dir(JJY_WS)
