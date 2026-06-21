"""系统 Tool 的共享基础设施（依赖装配层）。

这些 helper 是 @tool 函数与 engine 之间的薄封装层：
- _parser / _get_repo / _get_executor：按 vertical+tenant 构造 engine 对象（测试用 monkeypatch 替换）
- _preview_cache：execute_action/confirm_action 的预览缓存
- build_ontology_prompt：为本体注入 system prompt
- _wrap：工具返回值的统一包装格式（summary + COPILOTKIT_DATA）
- _tc：从工具参数构造 TenantContext

系统 Tool（query/crud/action）与 workspace 业务 Tool 都依赖这些 helper。
"""
import json

from engine.parser import get_ontology_parser
from engine.repository import JSONFileRepository
from engine.executor import ActionExecutor
from engine.preview_cache import PreviewCache
from engine.tenant import TenantContext


# ============ 依赖装配（按 vertical+tenant 构造；测试用 monkeypatch 替换）============

_preview_cache = PreviewCache(ttl_seconds=300)


def _parser(vertical: str = None):
    """获取某 vertical 的 parser。不传则取默认 vertical。"""
    return get_ontology_parser(vertical)


def _get_repo(tenant=None, vertical: str = None) -> JSONFileRepository:
    p = _parser(vertical)
    return JSONFileRepository(data_dir=str(p.data_dir), registry=p.registry)


def _get_executor(vertical: str = None) -> ActionExecutor:
    p = _parser(vertical)
    repo = _get_repo(vertical=vertical)
    return ActionExecutor(repository=repo, actions=p.registry.action_types,
                          registry=p.registry, config=p.config)


def build_ontology_prompt(vertical: str = None) -> str:
    p = _parser(vertical)
    intro = p.config.system_prompt_intro if p.config else ""
    return p.build_system_prompt(intro)


def _wrap(data: dict, summary: str) -> str:
    return f"{summary}\n<!--COPILOTKIT_DATA-->\n{json.dumps(data, ensure_ascii=False)}\n<!--/COPILOTKIT_DATA-->"


def _tc(workspace_name: str, org_unit_id: str) -> TenantContext:
    """从工具参数构造 TenantContext。"""
    return TenantContext(workspace_name=workspace_name, org_unit_id=org_unit_id)
