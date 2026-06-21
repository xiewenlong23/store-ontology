class OntologyError(Exception):
    """本体相关错误基类。"""


class EntityNotFoundError(OntologyError):
    pass


class ActionRequiredError(OntologyError):
    """对 edits-only-via-actions 实体直接写时抛出。"""


class ValidationError(OntologyError):
    pass
