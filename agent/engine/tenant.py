"""双层租户上下文（架构 spec §3.3/§5.5）：workspace_name 硬隔离 + org_unit_id 权限范围。

每条数据带 workspace_name + org_unit_id；
TenantContext.matches(record) 判断某条数据是否对当前上下文可见。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    workspace_name: str
    org_unit_id: str = "*"  # '*' = 看该 workspace 所有 OrgUnit（总部角色）

    def sees_all_org_units(self) -> bool:
        return self.org_unit_id == "*"

    def matches(self, record: dict) -> bool:
        """判断一条记录是否对当前上下文可见。

        规则：
        - workspace_name 必须匹配（硬隔离）
        - org_unit_id：上下文通配 '*' 则看所有；否则必须精确匹配
        - 旧数据（只有 customer_id 无 workspace_name）视为 jjy + 通配 org（向后兼容）
        """
        # 兼容：新格式读 workspace_name，旧格式读 customer_id（数据迁移期）
        rec_workspace = record.get("workspace_name")
        if rec_workspace is None:
            # 旧格式兼容：customer_id 存在则读取；完全无租户字段视为默认 workspace
            rec_workspace = record.get("customer_id", "jjy")
        rec_org = record.get("org_unit_id", "*")

        if rec_workspace != self.workspace_name:
            return False
        if self.sees_all_org_units():
            return True
        return rec_org == self.org_unit_id or rec_org == "*"

    @classmethod
    def default(cls) -> "TenantContext":
        return cls(workspace_name="jjy", org_unit_id="*")

    @classmethod
    def from_headers(cls, headers: dict) -> "TenantContext":
        # 兼容：X-Workspace 优先（架构 spec §3.4），回退 X-Customer-ID（旧前端）
        workspace = headers.get("X-Workspace") or headers.get("X-Customer-ID") or "jjy"
        org = headers.get("X-Org-Unit-ID") or "*"
        return cls(workspace_name=workspace, org_unit_id=org)
