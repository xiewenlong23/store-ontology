# app/skills/__init__.py
"""
Skill 动态加载器
Phase 2.3 — 运行时从 config/skills.yaml 读取 allowed-tools 配置，
注入到 Skill 实例，不写死在 SKILL.md 中。
"""
import yaml
import os
from pathlib import Path
from typing import Optional

SKILLS_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "skills.yaml"


def load_skills_config() -> dict:
    """加载 skills.yaml 配置"""
    if not SKILLS_CONFIG_PATH.exists():
        return {}
    with open(SKILLS_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_skill_config(skill_name: str) -> Optional[dict]:
    """获取指定 Skill 的配置（allowed-tools / roles 等）"""
    config = load_skills_config()
    return config.get("skills", {}).get(skill_name)


def get_allowed_tools(skill_name: str) -> list[str]:
    """获取 Skill 允许调用的工具列表（动态注入）"""
    skill_cfg = get_skill_config(skill_name)
    if not skill_cfg:
        return []
    return skill_cfg.get("allowed-tools", [])


def get_skill_roles(skill_name: str) -> list[str]:
    """获取 Skill 允许的角色列表"""
    skill_cfg = get_skill_config(skill_name)
    if not skill_cfg:
        return []
    return skill_cfg.get("roles", [])


def is_tool_allowed(skill_name: str, tool_name: str) -> bool:
    """检查某个工具是否在 Skill 的 allowed-tools 列表中"""
    allowed = get_allowed_tools(skill_name)
    return tool_name in allowed


def load_skill_md(skill_name: str) -> Optional[str]:
    """加载 Skill 的 SKILL.md 内容"""
    # skill 目录在项目根目录 skills/
    skills_root = Path(__file__).parent.parent.parent / "skills"
    skill_path = skills_root / f"{skill_name}" / "SKILL.md"
    if not skill_path.exists():
        return None
    with open(skill_path, encoding="utf-8") as f:
        return f.read()
