"""测试辅助：从 retail-pack 构建完整的 clearance registry（取代单 TTL 引用）。

P2+I-4 后 clearance 本体拆在 3 个 domain TTL + process actions 里，
不能再从单个 CLEARANCE_CONFIG.ttl_path 构建完整 registry。
此 helper 用 pack_to_registry 合并全 pack 定义。
"""
import os

from engine.parser import OntologyParser
from engine.action_loader import load_actions
from engine.repository import JSONFileRepository
from engine.executor import ActionExecutor
from engine.pack import pack_to_registry, ValueChainProcess
from engine.state_machine import TASK_TRANSITIONS, TERMINAL_STATES
from engine.bootstrap import bootstrap


_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_clearance_registry(data_dir: str):
    """从 retail-pack 构建完整 EntityRegistry（含所有 domain TTL + process actions）。"""
    from engine.pack import get_pack, register_pack
    bootstrap()
    pack = get_pack("retail")
    if pack is None:
        # bootstrap 可能因模块缓存未重新注册——直接 import + 注册
        import workspace.retail.pack  # noqa: F401
        from workspace.retail.pack import RETAIL_PACK
        register_pack(RETAIL_PACK)
        pack = get_pack("retail")
    if pack is None:
        raise RuntimeError("retail pack 未注册")
    return pack_to_registry(pack, data_dir=data_dir)


CLEARANCE_TEST_PROCESS = ValueChainProcess(
    name="clearance",
    display_name="出清",
    workflow_object_type="Task",
    workflow_object_id_field="task_id",
    state_transitions=TASK_TRANSITIONS,
    terminal_states=list(TERMINAL_STATES),
    system_prompt_intro="你是门店临期商品管理助手。",
)


def build_clearance_executor(data_dir: str):
    """构建指向 data_dir 的 clearance executor + repo（测试用）。

    返回 (executor, repo)。
    """
    registry = build_clearance_registry(data_dir)
    repo = JSONFileRepository(data_dir=data_dir, registry=registry)
    ex = ActionExecutor(repository=repo, actions=registry.action_types,
                        registry=registry, config=CLEARANCE_TEST_PROCESS)
    return ex, repo
