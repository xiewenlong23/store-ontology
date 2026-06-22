class OntologyError(Exception):
    """本体相关错误基类。"""


class EntityNotFoundError(OntologyError):
    pass


class ActionRequiredError(OntologyError):
    """对 edits-only-via-actions 实体直接写时抛出。"""


class ValidationError(OntologyError):
    pass


class PermissionDenied(OntologyError):
    """权限拒绝（v2 WP5）。求值引擎判定 actor 无权访问资源时抛出。"""
    pass
