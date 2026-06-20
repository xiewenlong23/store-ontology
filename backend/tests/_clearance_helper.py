"""测试辅助：从 retail-pack 构建完整的 clearance registry（取代单 TTL 引用）。

P2+I-4 后 clearance 本体拆在 3 个 domain TTL + process actions 里，
不能再从单个 CLEARANCE_CONFIG.ttl_path 构建完整 registry。
此 helper 用 pack_to_registry 合并全 pack 定义。
"""
import os

from ontology.parser import OntologyParser
from ontology.action_loader import load_actions
from ontology.repository import JSONFileRepository
from ontology.executor import ActionExecutor
from ontology.pack import pack_to_registry
from ontology.state_machine import TASK_TRANSITIONS, TERMINAL_STATES
from ontology.vertical import VerticalConfig
from ontology.bootstrap import bootstrap


_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_clearance_registry(data_dir: str):
    """从 retail-pack 构建完整 EntityRegistry（含所有 domain TTL + process actions）。"""
    from ontology.pack import get_pack
    bootstrap()
    pack = get_pack("retail")
    if pack is None:
        raise RuntimeError("retail pack 未注册")
    return pack_to_registry(pack, data_dir=data_dir)


CLEARANCE_TEST_CONFIG = VerticalConfig(
    name="clearance",
    ttl_path="",  # 不再用单 TTL
    actions_dir="",  # 不再用单 actions dir
    data_dir="",
    system_prompt_intro="你是门店临期商品管理助手。",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
)


def build_clearance_executor(data_dir: str):
    """构建指向 data_dir 的 clearance executor + repo（测试用）。

    返回 (executor, repo)。
    """
    registry = build_clearance_registry(data_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=registry)
    ex = ActionExecutor(repository=repo, actions=registry.action_types,
                        registry=registry, config=CLEARANCE_TEST_CONFIG)
    return ex, repo
