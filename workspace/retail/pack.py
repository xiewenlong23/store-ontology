"""retail 行业包声明（workspace 重构版）。

import 时注册到 pack 注册表。bootstrap() 自动发现。
retail-pack = 3 能力域（marketing/organization/finance）+ 1 价值链流程（clearance）。

目录结构（workspace 重构后）：
- ontology/domains/<domain>/domain.ttl + actions/  ← 本体声明
- data/                                            ← 种子数据
- skills/clearance_workflow/                       ← 场景单元（SKILL.md + tools.py + automation.py + actions/）
"""
import os

from engine.pack import IndustryPack, CapabilityDomain, ValueChainProcess, register_pack
from engine.state_machine import TASK_TRANSITIONS, TERMINAL_STATES

_BASE = os.path.dirname(os.path.abspath(__file__))  # workspace/retail/

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

RETAIL_PACK = IndustryPack(
    name="retail", display_name="零售行业包",
    domains=[MARKETING, ORGANIZATION, FINANCE],
    processes=[CLEARANCE],
    data_dir=os.path.join(_BASE, "data"))

register_pack(RETAIL_PACK)
