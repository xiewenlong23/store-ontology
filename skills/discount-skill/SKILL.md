# ============================================================
# 临期折扣 Skill（discount-skill）
# Phase 1.3 / Phase 2 核心技能
# 功能：临期商品折扣推荐 + 店长审批流
# ============================================================
name: discount-skill
description: |
  临期商品折扣推荐与审批 Skill。
  AI 根据商品剩余保质期，推荐对应的折扣层级（T1/T2/T3），
  并自动生成折扣任务，等待店长审批后执行。
version: "1.0.0"
author: "store-ontology team"

# ============================================================
# 工具定义（allowed-tools 由 config/skills.yaml 动态注入）
# ============================================================
tools:
  - name: query_expiring_products
    description: |
      查询门店中剩余保质期 ≤ N 天的商品列表，用于发现需要折扣的商品。
    parameters:
      type: object
      properties:
        days:
          type: integer
          description: 剩余保质期天数上限（默认 7）
          default: 7
        store_id:
          type: string
          description: 门店编号（必填）
      required: ["store_id"]

  - name: calculate_discount_tier
    description: |
      根据商品剩余保质期计算折扣层级和推荐折扣率。
      TBOX 规则：T1 ≤ 7天 → 8折 / T2 ≤ 14天 → 8.5折 / T3 ≤ 30天 → 9折
      豁免商品（烟草/酒类）不参与折扣。
    parameters:
      type: object
      properties:
        product_id:
          type: string
          description: 商品编号
        remaining_days:
          type: integer
          description: 剩余保质期天数
        store_id:
          type: string
          description: 门店编号
      required: ["product_id", "remaining_days", "store_id"]

  - name: create_discount_task
    description: |
      创建折扣任务，等待店长审批。
      审批人自动设为该门店的店长。
    parameters:
      type: object
      properties:
        product_id:
          type: string
          description: 商品编号
        discount_tier:
          type: string
          description: 折扣层级（T1 / T2 / T3）
        suggested_rate:
          type: number
          description: 推荐折扣率（0-1，如 0.20 表示 8折）
        store_id:
          type: string
          description: 门店编号
        priority:
          type: string
          description: 优先级（high / medium / low）
          default: medium
      required: ["product_id", "discount_tier", "suggested_rate", "store_id"]

  - name: approve_discount
    description: |
      店长批准折扣任务，执行折扣操作。
    parameters:
      type: object
      properties:
        task_id:
          type: string
          description: 折扣任务编号
        approved_rate:
          type: number
          description: 店长批准的折扣率
      required: ["task_id", "approved_rate"]

  - name: reject_discount
    description: |
      店长拒绝折扣任务，记录拒绝原因。
    parameters:
      type: object
      properties:
        task_id:
          type: string
          description: 折扣任务编号
        reason:
          type: string
          description: 拒绝原因
      required: ["task_id", "reason"]

  - name: query_discount_task
    description: |
      查询折扣任务详情。
    parameters:
      type: object
      properties:
        task_id:
          type: string
          description: 任务编号
        store_id:
          type: string
          description: 门店编号
      required: ["task_id", "store_id"]

  - name: query_pending_approvals
    description: |
      查询某门店待审批的折扣任务列表。
    parameters:
      type: object
      properties:
        store_id:
          type: string
          description: 门店编号
      required: ["store_id"]

# ============================================================
# 触发条件
# ============================================================
triggers:
  - "临期商品"
  - "折扣"
  - "打折"
  - "快过期"
  - "需要处理"
  - "哪些要打折"
  - "审批折扣"
  - "批准"
  - "拒绝"

# ============================================================
# 响应模板
# ============================================================
response_template: |
  {% raw %}
  {% if tasks %}
  待审批折扣任务：
  {% for t in tasks %}
  • **{{ t.product_name }}**（编号：{{ t.product_id }}）
    - 折扣层级：{{ t.tier }}（剩余 {{ t.remaining_days }} 天）
    - 推荐折扣：{{ t.rate_display }}
    - 状态：{{ t.status }}
  {% endfor %}
  {% endif %}
  {% endraw %}

# ============================================================
# 业务规则（来自 TBOX，不在此文件中硬编码）
# - 折扣层级定义：ontology/tbox/modules/00-enums/ENUMS-MODULE.ttl
# - 折扣规则实例：ontology/tbox/modules/02-discount/DISCOUNT-MODULE.ttl
# - 豁免商品：Category_ExemptTobacco / Category_ExemptAlcohol
# ============================================================
