---
name: fad:pr-branch
description: 准备一个过滤掉规划噪音的 review-safe PR 分支
argument-hint: "[目标分支，默认: main]"
allowed-tools:
  - Bash
  - Read
---

<objective>
创建一个干净的分支供 review，避免代码 reviewer 被规划工件干扰。
</objective>

<context>
目标: $ARGUMENTS

References:
- @.planning/audit/
</context>

<process>
1. 确定目标分支（默认 main）
2. 检查当前分支并识别属于以下内容的变更：
   - 代码/产品行为
   - 规划/审计专用工件
3. 准备 review-safe 路径：
   - 如果代码和规划已分离，保持当前分支
   - 否则建议一个专用 PR 分支，仅携带 review 相关变更
4. 不要静默丢弃用户创作的工件
5. 返回：
   - 推荐的分支策略
   - 确切的 git 步骤
   - 有意排除在 review 分支外的文件
</process>
