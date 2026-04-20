---
name: fad:map-codebase
description: 构建 brownfield 项目架构、约定、关注点和测试信号地图
argument-hint: "[可选专注领域]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

<objective>
在现有项目中编码前生成所需的项目基线。
</objective>

<context>
专注: $ARGUMENTS

Outputs:
- `.planning/codebase/ARCHITECTURE.md`
- `.planning/codebase/CONVENTIONS.md`
- `.planning/codebase/CONCERNS.md`
- `.planning/codebase/TESTING.md`
</context>

<process>
1. 检查项目结构、入口点、模块和测试布局
2. 总结：
   - 架构边界
   - 值得遵循的命名和风格约定
   - 危险的遗留区域和热点
   - 现有测试策略和差距
3. 偏重当前良好模式，而非最常见的糟糕模式
4. 在 `.planning/codebase/` 下写入/更新输出文件
5. 以以下内容结束：
   - brownfield 编码就绪状态
   - 需要人工指导的模糊区域
   - 推荐下一步命令
</process>
