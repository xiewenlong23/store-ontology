# ============================================================
# 商品查询 Skill（product-skill）
# Phase 1.3 最小可用技能之一
# 功能：查询商品信息、保质期、品类
# ============================================================
name: product-skill
description: |
  查询门店商品信息，包括商品名称、品类、保质期、到期日期等。
  用于回答"这个商品保质期多久"、"某商品属于哪个品类"等问题。
version: "1.0.0"
author: "store-ontology team"

tools:
  - name: query_product
    description: |
      通过商品名称或商品编号查询商品信息。
      返回商品编号、名称、品类、保质期天数、生产日期、到期日期、是否豁免折扣等信息。
    parameters:
      type: object
      properties:
        query:
          type: string
          description: 商品名称或商品编号
        store_id:
          type: string
          description: 门店编号（必填，所有查询必须带 store_id）
      required: ["store_id"]

  - name: query_products_by_category
    description: |
      查询某门店指定品类的所有商品。
    parameters:
      type: object
      properties:
        category:
          type: string
          description: 品类名称
        store_id:
          type: string
          description: 门店编号
      required: ["store_id"]

  - name: query_expiring_products
    description: |
      查询即将到期（剩余保质期 ≤ N 天）的商品列表。
    parameters:
      type: object
      properties:
        days:
          type: integer
          description: 剩余保质期天数上限（默认 7 天）
          default: 7
        store_id:
          type: string
          description: 门店编号
      required: ["store_id"]

triggers:
  - "查一下.{0,6}(商品|产品)"
  - ".{0,6}(保质期|到期|有效期)"
  - ".{0,6}(品类|分类)"
  - "这个商品"
  - "商品列表"

response_template: |
  {% raw %}
  {% if products %}
  {% for p in products %}
  • **{{ p.name }}**（编号：{{ p.id }}）
    - 品类：{{ p.category }}
    - 保质期：{{ p.shelf_date }}天
    - {% if p.is_exempt %}⚠️ 豁免折扣{% else %}可参与折扣{% endif %}
  {% endfor %}
  {% else %}
  未找到相关商品。
  {% endif %}
  {% endraw %}
