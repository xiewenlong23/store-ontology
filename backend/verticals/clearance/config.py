"""clearance vertical 的配置注册（兼容层）。

clearance 的实际定义已迁移到 packs/retail/（P2+I-4）。
此 config 保留注册供 bootstrap 发现 + 测试引用 CLEARANCE_CONFIG。
TTL/actions 指向 pack 的 domain TTL（不再用旧 store.ttl）。
"""
import os

from ontology.vertical import VerticalConfig, register_vertical
from ontology.state_machine import TASK_TRANSITIONS, TERMINAL_STATES

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
_ROOT = os.path.dirname(_BASE)

CLEARANCE_CONFIG = VerticalConfig(
    name="clearance",
    ttl_path=os.path.join(_BASE, "packs", "retail", "domains", "marketing", "domain.ttl"),
    actions_dir=os.path.join(_BASE, "packs", "retail", "domains", "marketing", "actions"),
    data_dir=os.path.join(_BASE, "packs", "retail", "data"),
    system_prompt_intro="你是门店临期商品管理助手。",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    # tools_module/skills_dir 不再需要——pack 版本提供了这些
)

register_vertical(CLEARANCE_CONFIG)
