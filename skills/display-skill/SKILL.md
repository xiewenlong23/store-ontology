# ============================================================
# 陈列调整建议 Skill（display-skill）
# Phase 1.3
# 功能：根据销售数据、库存情况给出陈列调整建议
# ============================================================
name: display-skill
description: |
  根据门店销售数据和库存情况，给出陈列位置调整建议。
  用于回答"哪些商品应该调整位置"、"滞销商品怎么处理"等问题。
version: "1.0.0"
author: "store-ontology team"

tools:
  - name: query_low_turnover_products
    description: |
      查询某门店低周转商品（滞销）列表。
    parameters:
      type: object
      properties:
        store_id:
          type: string
          description: 门店编号
        days:
          type: integer
          description: 统计周期天数（默认 30 天）
          default: 30
        limit:
          type: integer
          description: 返回数量上限（默认 10）
          default: 10
      required: ["store_id"]

  - name: query_high_demand_products
    description: |
      查询某门店高需求/热销商品列表。
    parameters:
      type: object
      properties:
        store_id:
          type: string
          description: 门店编号
        days:
          type: integer
          description: 统计周期天数（默认 7 天）
          default: 7
        limit:
          type: integer
          description: 返回数量上限（默认 10）
          default: 10
      required: ["store_id"]

  - name: suggest_display_rearrangement
    description: |
      根据滞销和热销数据，生成陈列调整建议。
    parameters:
      type: object
      properties:
        store_id:
          type: string
          description: 门店编号
      required: ["store_id"]

triggers:
  - "陈列"
  - "摆放"
  - "滞销"
  - "热销"
  - "调整位置"
  - "排面"

response_template: |
  {% raw %}
  {% if suggestions %}
  陈列调整建议：
  {% for s in suggestions %}
  • **{{ s.product_name }}**：{{ s.action }}
    原因：{{ s.reason }}
  {% endfor %}
  {% endif %}
  {% endraw %}
