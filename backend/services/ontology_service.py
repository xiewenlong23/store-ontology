"""本体服务 - 管理 Object Types 实例"""

from typing import List, Optional, Type, TypeVar
from models.schemas import (
    Store, Employee, Product, NearExpiryProduct,
    DiscountRule, Region, ClearanceTask
)
from storage.json_storage import (
    StoreStorage, EmployeeStorage, ProductStorage,
    NearExpiryProductStorage, DiscountRuleStorage,
    ClearanceTaskStorage
)

T = TypeVar('T')


class OntologyService:
    """本体服务 - 管理所有 Object Instances"""

    def __init__(self, data_dir: str = "../data"):
        self.data_dir = data_dir

        # 初始化存储
        self.regions = StoreStorage(f"{data_dir}/regions.json", Region)
        self.stores = StoreStorage(f"{data_dir}/stores.json", Store)
        self.employees = EmployeeStorage(f"{data_dir}/employees.json", Employee)
        self.products = ProductStorage(f"{data_dir}/products.json", Product)
        self.near_expiry_products = NearExpiryProductStorage(
            f"{data_dir}/near_expiry_products.json", NearExpiryProduct
        )
        self.discount_rules = DiscountRuleStorage(
            f"{data_dir}/discount_rules.json", DiscountRule
        )
        self.clearance_tasks = ClearanceTaskStorage(
            f"{data_dir}/clearance_tasks.json", ClearanceTask
        )

    # ============ Region ============

    def get_regions(self) -> List[Region]:
        return self.regions.find_all()

    def get_region(self, region_id: str) -> Optional[Region]:
        return self.regions.find_by_id(region_id)

    # ============ Store ============

    def get_stores(self) -> List[Store]:
        return self.stores.find_all()

    def get_store(self, store_id: str) -> Optional[Store]:
        return self.stores.find_by_id(store_id)

    def get_stores_by_region(self, region_id: str) -> List[Store]:
        return self.stores.find_by_field('region_id', region_id)

    # ============ Employee ============

    def get_employees(self) -> List[Employee]:
        return self.employees.find_all()

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        return self.employees.find_by_id(employee_id)

    def get_employees_by_store(self, store_id: str) -> List[Employee]:
        return self.employees.find_by_field('store_id', store_id)

    # ============ Product ============

    def get_products(self) -> List[Product]:
        return self.products.find_all()

    def get_product(self, product_id: str) -> Optional[Product]:
        return self.products.find_by_id(product_id)

    # ============ NearExpiryProduct ============

    def get_near_expiry_products(self) -> List[NearExpiryProduct]:
        return self.near_expiry_products.find_all()

    def get_near_expiry_product(self, nep_id: str) -> Optional[NearExpiryProduct]:
        return self.near_expiry_products.find_by_id(nep_id)

    def get_near_expiry_products_by_store(self, store_id: str) -> List[NearExpiryProduct]:
        return self.near_expiry_products.find_by_field('store_id', store_id)

    def get_near_expiry_products_by_status(self, status: str) -> List[NearExpiryProduct]:
        return self.near_expiry_products.find_by_field('status', status)

    def update_near_expiry_product(self, nep: NearExpiryProduct) -> Optional[NearExpiryProduct]:
        return self.near_expiry_products.update(nep.id, nep)

    # ============ DiscountRule ============

    def get_discount_rules(self) -> List[DiscountRule]:
        return self.discount_rules.find_all()

    def get_discount_rule(self, rule_id: str) -> Optional[DiscountRule]:
        return self.discount_rules.find_by_id(rule_id)

    # ============ ClearanceTask ============

    def get_clearance_tasks(self) -> List[ClearanceTask]:
        return self.clearance_tasks.find_all()

    def get_clearance_task(self, task_id: str) -> Optional[ClearanceTask]:
        return self.clearance_tasks.find_by_id(task_id)

    def get_clearance_tasks_by_store(self, store_id: str) -> List[ClearanceTask]:
        return self.clearance_tasks.find_by_field('store_id', store_id)

    def get_clearance_tasks_by_status(self, status: str) -> List[ClearanceTask]:
        return self.clearance_tasks.find_by_field('status', status)

    def create_clearance_task(self, task: ClearanceTask) -> ClearanceTask:
        return self.clearance_tasks.create(task)

    def update_clearance_task(self, task: ClearanceTask) -> Optional[ClearanceTask]:
        return self.clearance_tasks.update(task.id, task)

    # ============ Link Traversal ============

    def get_store_for_employee(self, employee: Employee) -> Optional[Store]:
        """Employee -> Store (belongs_to)"""
        return self.get_store(employee.store_id)

    def get_store_for_near_expiry_product(self, nep: NearExpiryProduct) -> Optional[Store]:
        """NearExpiryProduct -> Store (belongs_to)"""
        return self.get_store(nep.store_id)

    def get_product_for_near_expiry_product(self, nep: NearExpiryProduct) -> Optional[Product]:
        """NearExpiryProduct -> Product (is_instance_of)"""
        return self.get_product(nep.product_id)

    def get_employees_for_store(self, store: Store) -> List[Employee]:
        """Store -> Employees (has_employees)"""
        return self.get_employees_by_store(store.id)

    def get_near_expiry_products_for_store(self, store: Store) -> List[NearExpiryProduct]:
        """Store -> NearExpiryProducts (has_near_expiry_product)"""
        return self.get_near_expiry_products_by_store(store.id)
