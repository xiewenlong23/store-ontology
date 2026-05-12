# ============================================================
# 库存查询 Skill（inventory-skill）
# Phase 1.3 最小可用技能之一
# 功能：查询商品库存数量
# ============================================================
name: inventory-skill
description: |
  查询门店商品库存信息，包括当前库存数量、库存预警状态等。
  用于回答"某商品还剩多少"、"库存不足"等问题。
version: "1.0.0"
author: "store-ontology team"

tools:
  - name: query_stock
    description: |
      查询指定商品的当前库存数量。
    parameters:
      type: object
      properties:
        product_id:
          type: string
          description: 商品编号
        store_id:
          type: string
          description: 门店编号
      required: ["product_id", "store_id"]

  - name: query_low_stock
    description: |
      查询某门店库存不足（低于预警值）的商品列表。
    parameters:
      type: object
      properties:
        store_id:
          type: string
          description: 门店编号
        threshold:
          type: integer
          description: 库存预警阈值（默认 10）
          default: 10
      required: ["store_id"]

triggers:
  - "库存"
  - "还剩多少"
  - "库存不足"
  - "库存预警"

response_template: |
  {% raw %}
  {% if items %}
  {% for item in items %}
  • **{{ item.name }}**：{{ item.quantity }}{{ item.unit }}
    {% if item.quantity < 10 %}⚠️ 库存不足{% endif %}
  {% endfor %}
  {% else %}
  库存充足或未找到相关商品。
  {% endif %}
  {% endraw %}
