# ============================================================
# 任务管理 Skill（task-skill）
# Phase 1.3 / Phase 2
# 功能：创建/查询/更新门店任务
# ============================================================
name: task-skill
description: |
  门店任务管理 Skill，支持创建任务、查询任务状态、更新任务进度。
  用于回答"有什么待办"、"创建一个任务"、"更新任务状态"等问题。
version: "1.0.0"
author: "store-ontology team"

tools:
  - name: create_task
    description: |
      创建新的工作任务（不含折扣任务，折扣任务走 discount-skill）。
    parameters:
      type: object
      properties:
        title:
          type: string
          description: 任务标题
        description:
          type: string
          description: 任务描述
        store_id:
          type: string
          description: 门店编号
        assignee:
          type: string
          description: 负责人员工编号（可选，默认分配给创建者）
        priority:
          type: string
          description: 优先级（high / medium / low）
          default: medium
        deadline:
          type: string
          format: date-time
          description: 截止时间 ISO8601（可选）
      required: ["title", "store_id"]

  - name: query_tasks
    description: |
      查询某门店的任务列表，支持按状态筛选。
    parameters:
      type: object
      properties:
        store_id:
          type: string
          description: 门店编号
        status:
          type: string
          description: 状态过滤（pending / approved / executed / rejected / cancelled）
        assignee:
          type: string
          description: 负责人编号（可选）
      required: ["store_id"]

  - name: update_task_status
    description: |
      更新任务状态（执行中→已完成）。
      店员可更新自己的任务，店长可更新本店任何任务。
    parameters:
      type: object
      properties:
        task_id:
          type: string
          description: 任务编号
        status:
          type: string
          description: 新状态（executed / cancelled）
        store_id:
          type: string
          description: 门店编号
      required: ["task_id", "status", "store_id"]

  - name: assign_task
    description: |
      将任务分配给特定员工。
    parameters:
      type: object
      properties:
        task_id:
          type: string
          description: 任务编号
        assignee:
          type: string
          description: 被分配员工编号
        store_id:
          type: string
          description: 门店编号
      required: ["task_id", "assignee", "store_id"]

triggers:
  - "任务"
  - "待办"
  - "创建任务"
  - "有什么活"
  - "谁负责"
  - "更新任务"
  - "任务状态"

response_template: |
  {% raw %}
  {% if tasks %}
  {% for t in tasks %}
  • **{{ t.title }}** [{{ t.status }}]
    {% if t.assignee %}负责人：{{ t.assignee }}{% endif %}
    {% if t.deadline %}截止：{{ t.deadline }}{% endif %}
  {% endfor %}
  {% else %}
  暂无任务。
  {% endif %}
  {% endraw %}
