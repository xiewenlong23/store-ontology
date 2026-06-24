"""Action Log 条目数据模型 + 失败分类 + 敏感字段掩码（spec §3.3/§3.4/§7.1）。

每笔 Action 执行物化为一条 ActionLogEntry，由 executor 写入 action_logs 存储。
- outcome/failure_type 对齐 executor 现有 raise 点（8 类，spec §3.3）
- affected_objects 从 _run_side_effects 的 changes 提取（spec §3.4）
- params 敏感字段掩码（审计完整性 vs 隐私，MVP 硬编码字段集，spec §7.1）

P1 预留字段（llm_model/skill_id/session_id）：schema 占位，P1 注入 agent 运行时上下文。
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# 敏感字段名（MVP 硬编码，spec §7.1；远期从 ontology 元数据推导）
_SENSITIVE_FIELDS = {"password", "password_hash", "token", "secret"}


@dataclass
class ActionLogEntry:
    """单笔 Action 执行的审计记录（决策即数据）。"""
    log_id: str
    workspace_name: str
    timestamp: str  # ISO，init 时定
    action_type: str
    outcome: str = ""  # "success" / "failure" / ""（pending）
    failure_type: Optional[str] = None
    error_message: Optional[str] = None
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    actor_type: str = "user"  # "user" / "agent"
    trigger_source: str = "llm_session"
    edits_object_types: list = field(default_factory=list)
    affected_objects: dict = field(default_factory=dict)
    params: Optional[dict] = None
    duration_ms: Optional[int] = None
    # P1 预留 agent 运行时上下文（spec D3）
    llm_model: Optional[str] = None
    skill_id: Optional[str] = None
    session_id: Optional[str] = None

    @classmethod
    def init(cls, action_type, actor: dict, workspace_name: str,
             trigger_source: str = "llm_session") -> "ActionLogEntry":
        """构造待填充的 entry。从 actor dict 推导 actor_type/id/role。

        actor 兼容两种 key：user_id（v2 auth）/ id（legacy executor 风格）。
        actor_type 推导（spec §12.1 agent 身份）：
        - llm_session 且有 user_id → user
        - 其它（automation/webhook/admin_api，或匿名）→ agent
        """
        role = actor.get("role") or ""
        # 兼容 user_id（v2 auth_ctx）与 id（legacy executor actor 风格）
        user_id = actor.get("user_id") or actor.get("id")
        if trigger_source == "llm_session" and user_id:
            actor_type = "user"
            actor_id = user_id
        else:
            # automation/webhook/admin_api 视为 agent 自动触发（spec §12.1）
            actor_type = "agent"
            actor_id = f"agent:{trigger_source}"
        return cls(
            log_id=uuid.uuid4().hex,
            workspace_name=workspace_name,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            action_type=action_type,
            actor_id=actor_id,
            actor_role=role,
            actor_type=actor_type,
            trigger_source=trigger_source,
        )

    def update_success(self, changes: dict) -> None:
        """从 _run_side_effects 的 changes 提取 affected_objects 并标记 success。

        changes 形如 {"created": {obj_type: [rec]}, "updated": {obj_type: [rec]}}。
        """
        self.outcome = "success"
        self.affected_objects = {}
        for obj_type, recs in changes.get("created", {}).items():
            self.affected_objects.setdefault(obj_type, []).extend(
                r.get("id") for r in recs if r.get("id"))
        for obj_type, recs in changes.get("updated", {}).items():
            existing = self.affected_objects.setdefault(obj_type, [])
            existing.extend(r.get("id") for r in recs if r.get("id"))

    def update_failure(self, failure_type: str, error_message: str) -> None:
        self.outcome = "failure"
        self.failure_type = failure_type
        self.error_message = error_message


def classify_failure(exc: Exception) -> str:
    """基于异常类型 + 消息文本启发式分类（spec §3.3，8 类对齐 executor raise 点）。

    顺序：EntityNotFoundError → ValidationError（按消息分支）→ OntologyError 兜底
    → 非 OntologyError → unclassified。
    """
    from engine.errors import EntityNotFoundError, OntologyError, ValidationError

    if isinstance(exc, EntityNotFoundError):
        return "entity_not_found"
    if isinstance(exc, ValidationError):
        msg = str(exc)
        if "未知 Action Type" in msg or "未知 Action" in msg:
            return "unknown_action"
        if "角色" in msg and "无权提交" in msg:
            return "permission_denied"
        if "非法状态迁移" in msg:
            return "illegal_transition"
        if "缺少必填" in msg or "不满足约束" in msg:
            return "invalid_param"
        # 剩余 ValidationError 多为 submission 条件不满足
        return "submission_failed"
    if isinstance(exc, OntologyError):
        return "side_effect_error"
    return "unclassified"


def mask_sensitive_params(params: Optional[dict]) -> Optional[dict]:
    """对 params 中的敏感字段值替换为 '***'（MVP 硬编码字段集，spec §7.1）。"""
    if not params:
        return params
    return {k: ("***" if k in _SENSITIVE_FIELDS else v) for k, v in params.items()}
