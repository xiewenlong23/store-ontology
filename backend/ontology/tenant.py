"""双层租户上下文（P1）：customer_id 硬隔离 + org_unit_id 权限范围。

替代旧的单一 tenant_id 字符串。每条数据带 customer_id + org_unit_id；
TenantContext.matches(record) 判断某条数据是否对当前上下文可见。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantContext:
    customer_id: str
    org_unit_id: str = "*"  # '*' = 看该客户所有 OrgUnit（总部角色）

    def sees_all_org_units(self) -> bool:
        return self.org_unit_id == "*"

    def matches(self, record: dict) -> bool:
        """判断一条记录是否对当前上下文可见。

        规则：
        - customer_id 必须匹配（硬隔离）
        - org_unit_id：上下文通配 '*' 则看所有；否则必须精确匹配
        - 旧数据（只有 tenant_id 无 customer_id）视为 customer_default + 通配 org
        """
        rec_customer = record.get("customer_id")
        if rec_customer is None:
            # 旧格式兼容：tenant_id 存在视为 customer_default
            if record.get("tenant_id") is not None:
                rec_customer = "customer_default"
                rec_org = "*"
            else:
                return False
        else:
            rec_org = record.get("org_unit_id", "*")

        if rec_customer != self.customer_id:
            return False
        if self.sees_all_org_units():
            return True
        return rec_org == self.org_unit_id or rec_org == "*"

    @classmethod
    def default(cls) -> "TenantContext":
        return cls(customer_id="customer_default", org_unit_id="*")

    @classmethod
    def from_headers(cls, headers: dict) -> "TenantContext":
        customer = headers.get("X-Customer-ID") or "customer_default"
        org = headers.get("X-Org-Unit-ID") or "*"
        return cls(customer_id=customer, org_unit_id=org)
