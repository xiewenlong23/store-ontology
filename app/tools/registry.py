#!/usr/bin/env python3
"""
门店大脑工具注册表 — Hermes 风格

核心设计：
- 每个工具模块在导入时调用 registry.register() 注册自身
- ToolRegistry 单例收集所有工具的 schema + handler
- discover_tools() 通过 AST 扫描自动发现所有工具模块

导入链：
    registry.py（无依赖）
        ↑
    store_tools.py（调用 registry.register()）
        ↑
    agent_executor.py（调用 registry）
        ↑
    unified-chat router（调用 agent_executor）
"""

import ast
import importlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_registry_register_call(node: ast.AST) -> bool:
    """检查 node 是否为 registry.register(...) 调用表达式。"""
    if not isinstance(node, ast.Expr):
        return False
    if not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "register"
        and isinstance(func.value, ast.Name)
        and func.value.id == "registry"
    )


def _module_registers_tools(module_path: Path) -> bool:
    """检查模块是否在顶层调用了 registry.register()。"""
    try:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))
    except (OSError, SyntaxError):
        return False
    return any(_is_registry_register_call(stmt) for stmt in tree.body)


class ToolEntry:
    """单个工具的元数据。"""

    __slots__ = (
        "name",
        "toolset",
        "schema",
        "handler",
        "description",
    )

    def __init__(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        description: str = "",
    ):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.description = description or schema.get("description", "")


class ToolRegistry:
    """工具注册表单例 — 收集所有已注册工具的 schema 和 handler。"""

    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}
        self._logger = logging.getLogger(__name__ + ".ToolRegistry")

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        description: str = "",
    ):
        """
        注册一个工具。

        Args:
            name: 工具唯一名称
            toolset: 工具集名称（如 "store"）
            schema: OpenAI 格式的工具 schema（须含 description）
            handler: 工具执行函数，签名由 schema 定义
            description: 工具的中文描述，用于 LLM 理解工具能力
        """
        self._tools[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            description=description or schema.get("description", ""),
        )
        self._logger.info("Registered tool: %s (toolset=%s)", name, toolset)

    def get(self, name: str) -> Optional[ToolEntry]:
        """根据名称获取工具条目。"""
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolEntry]:
        """获取所有已注册工具。"""
        return dict(self._tools)

    def get_toolset_tools(self, toolset: str) -> Dict[str, ToolEntry]:
        """获取指定工具集下的所有工具。"""
        return {
            name: entry
            for name, entry in self._tools.items()
            if entry.toolset == toolset
        }

    def get_schemas(self, tool_names: List[str]) -> List[dict]:
        """
        返回指定工具的 OpenAI 格式 schema 列表。

        只返回已注册的工具，未注册的工具名会被忽略。
        """
        result = []
        for name in tool_names:
            entry = self._tools.get(name)
            if entry:
                schema_with_name = {**entry.schema, "name": entry.name}
                result.append({"type": "function", "function": schema_with_name})
        return result

    def dispatch(self, name: str, args: dict) -> dict:
        """
        执行指定工具。

        Args:
            name: 工具名称
            args: 工具参数（由 schema 定义）

        Returns:
            执行结果 dict，固定包含 "success" 字段
            失败时返回 {"success": False, "error": "..."}
        """
        entry = self._tools.get(name)
        if not entry:
            return {"success": False, "error": f"Unknown tool: {name}"}
        try:
            result = entry.handler(**args)
            return result if isinstance(result, dict) else {"success": True, "data": result}
        except TypeError as e:
            # 参数不匹配
            return {"success": False, "error": f"参数错误: {e}"}
        except Exception as e:
            logger.exception("Tool %s dispatch error", name)
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    def list_tools(self) -> List[dict]:
        """列出所有工具的基本信息（名称、工具集、描述）。"""
        return [
            {
                "name": entry.name,
                "toolset": entry.toolset,
                "description": entry.description,
            }
            for entry in self._tools.values()
        ]


# 模块级单例
registry = ToolRegistry()


def discover_tools(tools_dir: Optional[Path] = None) -> List[str]:
    """
    发现并导入所有工具模块。

    扫描 tools_dir 目录（含 __init__.py 的子目录），找出在模块顶层
    调用了 registry.register() 的 .py 文件并导入。

    Args:
        tools_dir: 工具目录路径，默认为 app/tools/

    Returns:
        已成功导入的工具模块名列表
    """
    tools_path = Path(tools_dir) if tools_dir else Path(__file__).resolve().parent
    module_names = []
    for path in sorted(tools_path.glob("*.py")):
        if path.name in {"__init__.py", "registry.py"}:
            continue
        if _module_registers_tools(path):
            mod_name = f"app.tools.{path.stem}"
            try:
                importlib.import_module(mod_name)
                module_names.append(mod_name)
            except Exception as e:
                logger.warning("Could not import tool module %s: %s", mod_name, e)
    return module_names
