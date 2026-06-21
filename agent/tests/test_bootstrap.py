"""测试 bootstrap 发现工作目录。"""
import pytest

from engine import bootstrap as bootstrap_mod
from engine.pack import all_workspace_dirs


def test_bootstrap_registers_customerA():
    bootstrap_mod.bootstrap()
    names = [p.name for p in all_workspace_dirs()]
    assert "customerA" in names


def test_bootstrap_registers_retail():
    bootstrap_mod.bootstrap()
    names = [p.name for p in all_workspace_dirs()]
    assert "retail" in names


def test_bootstrap_is_idempotent():
    bootstrap_mod.bootstrap()
    n1 = len(all_workspace_dirs())
    bootstrap_mod.bootstrap()
    n2 = len(all_workspace_dirs())
    assert n1 == n2
