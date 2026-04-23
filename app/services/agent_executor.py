#!/usr/bin/env python3
"""
Agent Executor — LLM Agent 多步工作流调度器

核心职责：
- 维护对话历史（用户消息 + 工具调用 + 执行结果）
- LLM 根据历史决定下一步：调用工具 or 结束
- 循环执行直到 LLM 判断"完成"（最多 MAX_STEPS 步）
- 工具执行结果回流 LLM，支撑下一步推理

架构参考 Hermes ReAct 模式：
    用户 → LLM理解本体 → 调用查询工具 → LLM基于查询结果 → 调用操作工具 → ... → LLM组织最终回答
"""

import json
import logging
from typing import Any, Optional

from app.tools.registry import registry
from app.services.llm_service import get_minimax_llm
from app.services.context import ToolContext, ContextManager
from app.services.reasoning_engine import FastPathRuleEngine

logger = logging.getLogger(__name__)

MAX_STEPS = 6


SYSTEM_PROMPT = """你是一个门店大脑 AI 助手，负责帮助店长管理临期商品出清流程。

你的工作方式：
1. 先理解店长的需求，必要时查询本体数据（商品信息、库存、到期日、品类）
2. 根据查询结果，决定是否需要调用更多工具
3. 所有工具调用完成后，用自然语言向店长报告结果

可用工具：
{tool_descriptions}

重要原则：
- 每次决策都要基于已有的上下文，不要重复查询相同信息
- 如果用户问"嫩豆腐要打几折"，你不知道嫩豆腐的到期日和库存，必须先查询商品信息
- 如果用户说"帮我创建出清任务"，你需要先确认商品信息完整，不完整就先查
- 操作类工具（create_task/confirm_task/execute_task/review_task）执行后，继续向店长确认下一步

回复格式：
- 当你完成所有工具调用，只需要直接回答店长的问题，不需要再调用工具
- 用自然语言组织最终回复，不要输出 JSON 或 continue 字段
- 当需要生成柱状图时，使用以下 ASCII 格式：
  商品数量(种)
  3 ┤   █
  2 ┤   █   █ █
  1 ┤ █ █ █ █ █
  0 ┼─────────────────────
    0天  1天  2天  3天  4天及以上
  每个█代表1个商品，Y轴是"商品数量(种)"
"""


def _build_tool_descriptions(tools: dict) -> str:
    lines = []
    for name, entry in tools.items():
        schema = entry.schema
        desc = schema.get("description", "")
        props = schema.get("parameters", {}).get("properties", {})
        required = schema.get("parameters", {}).get("required", [])

        param_lines = []
        for pname, pinfo in props.items():
            ptype = pinfo.get("type", "string")
            pdesc = pinfo.get("description", "")
            req_mark = "（必填）" if pname in required else "（可选）"
            param_lines.append(f"  - {pname}: {ptype} {req_mark} {pdesc}")

        params_str = "\n".join(param_lines) if param_lines else "  （无参数）"
        lines.append(f"工具：{name}\n  说明：{desc}\n  参数：\n{params_str}")

    return "\n\n".join(lines)


class AgentExecutor:
    """
    LLM Agent 调度器 — 支持多步循环执行。

    LLM 输出结构化 JSON：{tool, args, reasoning, continue}
    - continue=true: 执行工具，结果注入历史，LLM 再决策
    - continue=false: reasoning 就是最终回答，结束循环
    """

    def __init__(self):
        self._tools = registry.get_all_tools()
        self._tool_descs = _build_tool_descriptions(self._tools)
        self._fast_path = FastPathRuleEngine()

    def execute(self, user_message: str, context: Optional[dict] = None) -> dict:
        """
        执行用户消息 — LLM Agent 循环直到完成。

        Args:
            user_message: 用户消息
            context: 可选的上下文信息，包含 store_id, user_id, user_role 等

        Returns:
            {
                "success": bool,
                "tool_name": str,
                "tool_result": dict,
                "response": str,  # LLM 最终的自然语言回答
                "steps": int,
                "conversation": list,
            }
        """
        # 构建 ToolContext（用于工具执行时的上下文隔离）
        tool_ctx = ToolContext(
            store_id=context.get("store_id") if context else "STORE-001",
            user_id=context.get("user_id"),
            user_role=context.get("user_role"),
            product_id=context.get("product_id"),
            product_name=context.get("product_name"),
            category=context.get("category"),
            expiry_date=context.get("expiry_date"),
            stock=context.get("stock"),
        )

        # 构建初始消息列表
        system_content = SYSTEM_PROMPT.format(tool_descriptions=self._tool_descs)
        messages = [{"role": "system", "content": system_content}]

        if context:
            ctx_lines = [f"- {k}: {v}" for k, v in context.items() if v is not None]
            if ctx_lines:
                messages.append({
                    "role": "system",
                    "content": "附加上下文（已知信息）：\n" + "\n".join(ctx_lines),
                })

        messages.append({"role": "user", "content": user_message})

        final_response = None
        final_tool_name = None
        final_tool_result = None
        step_count = 0
        unknown_tool_retries = 0
        MAX_UNKNOWN_TOOL_RETRIES = 2

        while step_count < MAX_STEPS:
            step_count += 1

            # LLM 决策
            decision = self._llm_decide(messages)
            tool_name = decision.get("tool_name")
            tool_args = decision.get("tool_args", {})
            reasoning = decision.get("reasoning", "")
            should_continue = decision.get("continue", False)

            # LLM 标记结束：reasoning 就是最终回答
            # 尊重 LLM 的决策，不要用 Python 格式化覆盖 LLM 的自然语言推理
            if not should_continue:
                if reasoning:
                    final_response = reasoning
                elif decision.get("response"):
                    final_response = decision.get("response")
                else:
                    final_response = self._build_response_from_result(
                        final_tool_name, final_tool_result, user_message
                    ) if final_tool_result else "处理完成。"
                break

            # LLM 无法决策（unknown tool 后会 continue），最多重试 MAX_UNKNOWN_TOOL_RETRIES 次
            if not tool_name:
                unknown_tool_retries += 1
                if unknown_tool_retries >= MAX_UNKNOWN_TOOL_RETRIES:
                    final_response = "无法识别您的意图，请重新描述需求。"
                    break
                continue

            # 执行工具（设置上下文）
            with ContextManager(tool_ctx):
                entry = registry.get(tool_name)
                if not entry:
                    tool_result = {"success": False, "error": f"未知工具: {tool_name}"}
                else:
                    schema_props = entry.schema.get("parameters", {}).get("properties", {})
                    filtered_args = {k: v for k, v in tool_args.items() if k in schema_props}
                    tool_result = registry.dispatch(tool_name, filtered_args)

            # 把 LLM 的决策 + 执行结果都加入历史，供下一步使用
            messages.append({
                "role": "assistant",
                "content": json.dumps(
                    {"tool": tool_name, "args": tool_args, "reasoning": reasoning},
                    ensure_ascii=False,
                ),
            })
            messages.append({
                "role": "system",
                "content": f"工具执行结果：\n{json.dumps(tool_result, ensure_ascii=False, indent=2)}",
            })

            final_tool_name = tool_name
            final_tool_result = tool_result

        # 循环结束，生成最终回答
        if final_response is None:
            final_response = self._build_response_from_result(
                final_tool_name, final_tool_result, user_message
            )

        # 过滤掉 <tool_call>...</tool_call> 标签（LLM 输出的原始工具调用标记）
        import re
        final_response = re.sub(
            r'<tool_call>\s*\{[^}]*"tool"[^}]*\}\s*</tool_call>',
            '',
            final_response,
            flags=re.DOTALL
        ).strip()

        return {
            "success": bool(final_tool_result.get("success", False)) if final_tool_result else False,
            "tool_name": final_tool_name,
            "tool_result": final_tool_result,
            "response": final_response,
            "steps": step_count,
            "conversation": messages,
        }

    def _llm_decide(self, messages: list) -> dict:
        """
        调用 LLM，让它根据对话历史决定下一步行动。
        """
        try:
            llm = get_minimax_llm()
            # 传递工具定义给 LLM（Anthropic 格式）
            tool_schemas = self._get_tool_schemas()
            response = llm.chat(messages, tools=tool_schemas)
        except ValueError as e:
            logger.warning("[AgentExecutor] LLM not available: %s", e)
            return {"tool_name": None, "tool_args": {}, "reasoning": "LLM 未配置", "continue": False}
        except Exception as e:
            logger.error("[AgentExecutor] LLM call failed: %s", e)
            return {"tool_name": None, "tool_args": {}, "reasoning": f"LLM 错误: {e}", "continue": False}

        # 如果 LLM 返回了结构化工具调用（MiniMax 原生 tool_use）
        if isinstance(response, dict) and response.get("type") == "tool_call":
            tool_name = response.get("tool_name")
            tool_args = response.get("tool_args", {})
            reasoning = response.get("text", "")
            return {
                "tool_name": tool_name,
                "tool_args": tool_args,
                "reasoning": reasoning,
                "continue": True,
            }

        # 否则按原有逻辑解析文本响应
        return self._parse_llm_decision(response)

    def _get_tool_schemas(self) -> list:
        """获取所有工具的 Anthropic 格式 schema 列表（从 OpenAI 格式转换）。"""
        schemas = []
        for name, entry in self._tools.items():
            schema = entry.schema.copy()
            # OpenAI 格式: {name, description, parameters: {type, properties, ...}}
            # Anthropic 格式: {name, description, input_schema: {type, properties, ...}}
            anthropic_schema = {
                "name": entry.name,
                "description": schema.get("description", ""),
                "input_schema": schema.get("parameters", {"type": "object", "properties": {}}),
            }
            schemas.append(anthropic_schema)
        return schemas

    def _parse_llm_decision(self, llm_response: str) -> dict:
        """
        解析 LLM 返回的决策。

        支持格式：
        1. JSON: {"tool": "xxx", "args": {...}, "reasoning": "...", "continue": true/false}
        2. 纯文本字符串 → 认为是最终回答，continue=False
        """
        import re

        response = llm_response.strip()

        # 尝试 JSON 解析（可能包含在 <tool_call> 标签内）
        obj = None
        try:
            obj = json.loads(response)
        except (json.JSONDecodeError, ValueError):
            # 尝试从 <tool_call> 或 <invoke> 标签内提取 JSON
            match = re.search(r'<(?:tool_call|invoke)[^>]*>([\s\S]*?)</(?:tool_call|invoke)>', response, re.IGNORECASE)
            if match:
                inner = match.group(1)
                # 去掉转义引号（如 \" -> "）
                inner = inner.replace('\\"', '"').replace('\\n', ' ')
                try:
                    obj = json.loads(inner)
                except (json.JSONDecodeError, ValueError):
                    pass

        if obj and isinstance(obj, dict):
            tool_name = obj.get("name") or obj.get("tool") or obj.get("tool_name")
            # MiniMax 格式: "parameters" 而不是 "args"
            tool_args = obj.get("parameters") or obj.get("args") or obj.get("tool_args") or {}
            reasoning = obj.get("reasoning", "")
            continue_flag = obj.get("continue", True if tool_name else False)
            final_response = obj.get("response", "")

            # 检查工具名是否合法
            if tool_name and tool_name not in self._tools:
                logger.warning("[AgentExecutor] LLM returned unknown tool: %s", tool_name)
                return {
                    "tool_name": None,
                    "tool_args": {},
                    "reasoning": f"工具 {tool_name} 不存在，请基于已有信息重新选择工具或直接回答用户。",
                    "continue": True,
                }

            return {
                "tool_name": tool_name,
                "tool_args": tool_args,
                "reasoning": reasoning or final_response,
                "continue": continue_flag,
                "response": final_response,
            }

        # 非 JSON：检查是否包含工具名（JSON格式）
        m = re.search(r'tool\s*[=:\s]+["\']?([a-zA-Z_][a-zA-Z0-9_]*)', response, re.IGNORECASE)
        if m:
            tool_name = m.group(1)
            if tool_name in self._tools:
                tool_args = self._extract_args_from_message_text(response, tool_name)
                return {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "reasoning": response,
                    "continue": True,
                }

        # MiniMax XML 格式工具调用: <invoke name="tool_name">...<parameter name="x">value</parameter>...</invoke>
        # 或 <tool_call>tool_name\nparam="value"\n</tool_call>
        xml_match = re.search(r'<invoke\s+name=["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']', response, re.IGNORECASE)
        if not xml_match:
            # 尝试 <tool_call>tool_name\nparams...</tool_call> 格式
            xml_match = re.search(r'<tool_call>\s*([a-zA-Z_][a-zA-Z0-9_]*)', response, re.IGNORECASE)
        
        if xml_match:
            tool_name = xml_match.group(1)
            if tool_name in self._tools:
                tool_args = self._extract_args_from_xml(response, tool_name)
                return {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "reasoning": response,
                    "continue": True,
                }
            else:
                logger.warning("[AgentExecutor] LLM returned unknown tool: %s", tool_name)
                return {
                    "tool_name": None,
                    "tool_args": {},
                    "reasoning": f"工具 {tool_name} 不存在，请基于已有信息重新选择工具或直接回答用户。",
                    "continue": True,
                }

        # 真的没有工具调用，是最终回答
        return {
            "tool_name": None,
            "tool_args": {},
            "reasoning": response,
            "continue": False,
        }

    def _extract_args_from_message_text(self, text: str, tool_name: str) -> dict:
        import re
        args = {}

        entry = registry.get(tool_name)
        if not entry:
            return args

        schema_props = entry.schema.get("parameters", {}).get("properties", {})
        msg = text

        if "product_name" in schema_props:
            patterns = [r"嫩豆腐", r"鲜牛奶", r"面包", r"([\u4e00-\u9fff]{2,8})商品"]
            for p in patterns:
                m = re.search(p, msg)
                if m:
                    args["product_name"] = m.group(1) if m.lastindex else m.group(0)
                    break

        if "category" in schema_props:
            if "日配" in msg or "牛奶" in msg or "酸奶" in msg:
                args["category"] = "daily_fresh"
            elif "烘焙" in msg or "面包" in msg:
                args["category"] = "bakery"
            elif "冷冻" in msg:
                args["category"] = "frozen"

        if "discount_rate" in schema_props:
            m = re.search(r"([0-9]{1,3})折", msg)
            if m:
                rate = int(m.group(1))
                args["discount_rate"] = rate / 10

        return args

    def _extract_args_from_xml(self, text: str, tool_name: str) -> dict:
        """从 MiniMax XML 格式中提取工具参数。"""
        import re
        args = {}

        entry = registry.get(tool_name)
        if not entry:
            return args

        schema_props = entry.schema.get("parameters", {}).get("properties", {})

        # 提取 <parameter name="x">value</parameter> 格式的参数
        param_matches = re.findall(r'<parameter\s+name=["\']([^"\']+)["\']>([^<]*)</parameter>', text)
        for param_name, param_value in param_matches:
            if param_name in schema_props:
                # 类型转换
                prop_type = schema_props[param_name].get("type", "string")
                if prop_type == "integer" or prop_type == "number":
                    try:
                        args[param_name] = int(param_value.strip())
                    except ValueError:
                        args[param_name] = param_value.strip()
                else:
                    args[param_name] = param_value.strip()

        return args

    def _build_response_from_result(
        self, tool_name: Optional[str], tool_result: Optional[dict], user_message: str, wants_chart: bool = False
    ) -> str:
        if not tool_result:
            return "处理完成，但没有返回结果。"

        if not tool_result.get("success", False):
            return f"操作失败：{tool_result.get('error', '未知错误')}"

        if not tool_name:
            return str(tool_result.get("message", tool_result))

        # 生成柱状图（如果有商品列表且用户要求图表）
        chart = ""
        if wants_chart and tool_name in ("query_pending_products", "query_pending_with_discount"):
            products = tool_result.get("products", [])
            if products:
                chart = self._generate_bar_chart(products)

        if tool_name == "query_pending_products":
            products = tool_result.get("products", [])
            count = tool_result.get("count", len(products))
            if count == 0:
                return "当前没有临期商品，库存都很新鲜。"

            # 使用 Fast Path 规则引擎为每个商品计算折扣建议
            enriched = self._enrich_products_with_fastpath(products)

            lines = [f"当前共有 {count} 件临期商品："]
            for p in enriched[:5]:
                fast_info = p.get("_fast_path", {})
                if fast_info:
                    action = fast_info.get("action", "")
                    rate = fast_info.get("discount_rate")
                    tier = fast_info.get("tier")
                    if action == "EXEMPTED":
                        info = f"（豁免: {fast_info.get('exemption_type', '未知')}）"
                    elif action == "APPLY_DISCOUNT" and rate:
                        info = f"（建议{rate*10:.0f}折/T{tier}）"
                    elif action == "NEEDS_APPROVAL" and rate:
                        info = f"（需审批: {rate*10:.0f}折/T{tier}）"
                    else:
                        info = ""
                else:
                    info = ""
                lines.append(
                    f"- {p.get('name', '未知')}，"
                    f"剩余 {p.get('days_left', '?')} 天，"
                    f"库存 {p.get('stock', '?')} 件{info}"
                )
            if count > 5:
                lines.append(f"...还有 {count - 5} 件商品")
            result = "\n".join(lines)
            if chart:
                result += "\n\n" + chart
            return result

        if tool_name == "query_pending_with_discount":
            products = tool_result.get("products", [])
            count = tool_result.get("count", len(products))
            if count == 0:
                return "当前没有临期商品，库存都很新鲜。"
            lines = [f"当前共有 {count} 件临期商品："]
            for p in products[:5]:
                name = p.get('name', '未知')
                days = p.get('days_left', '?')
                stock = p.get('stock', '?')
                disc = p.get('recommended_discount', 0)
                disc_display = f"{disc*10:.0f}折" if disc < 1 else f"{disc:.0f}折"
                risk = p.get('risk_level', '?')
                risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪️")
                lines.append(
                    f"- {name}，剩余 {days} 天，库存 {stock} 件，"
                    f"建议 {disc_display} {risk_emoji}"
                )
            if count > 5:
                lines.append(f"...还有 {count - 5} 件商品")
            result = "\n".join(lines)
            if chart:
                result += "\n\n" + chart
            return result

        if tool_name == "query_tasks":
            tasks = tool_result.get("tasks", [])
            count = tool_result.get("count", len(tasks))
            if count == 0:
                return "当前没有任何出清任务。"
            by_status = {}
            for t in tasks:
                status = t.get("status", "unknown")
                by_status[status] = by_status.get(status, 0) + 1
            lines = [f"当前共有 {count} 个任务："]
            for status, num in by_status.items():
                status_text = {
                    "pending": "待确认",
                    "confirmed": "已确认",
                    "executed": "已执行",
                    "reviewed": "已复核",
                    "completed": "已完成",
                }.get(status, status)
                lines.append(f"- {status_text}：{num} 个")
            return "\\n".join(lines)

        if tool_name == "query_discount":
            if tool_result.get("discount_rate") is not None:
                rate = tool_result.get("discount_rate", 0)
                reason = tool_result.get("reasoning", "")
                return f"这件商品当前折扣率是 {rate*100:.0f}%。{reason}"
            else:
                rate = tool_result.get("recommended_discount", 0)
                tier_name = tool_result.get("tier_name", "")
                reasoning = tool_result.get("reasoning", "")
                return f"建议折扣率：{rate*100:.0f}%（{tier_name}）。{reasoning}"

        if tool_name == "query_discount_rules":
            rules = tool_result.get("rules", [])
            if not rules:
                return "该品类暂无折扣规则。"
            lines = ["折扣规则如下："]
            for r in rules:
                tier = r.get("tier", "?")
                rec = r.get("recommended_discount", 0)
                disc_range = r.get("discount_range", [])
                range_str = f"{disc_range[0]*100:.0f}%-{disc_range[1]*100:.0f}%" if disc_range else "?"
                lines.append(f"- Tier{tier}：建议 {rec*100:.0f}%（范围 {range_str}）")
            return "\\n".join(lines)

        if tool_name in ("create_task", "confirm_task", "execute_task", "review_task"):
            return tool_result.get("message", "操作完成。")

        return tool_result.get("message", json.dumps(tool_result, ensure_ascii=False, indent=2)[:500])


    def _enrich_products_with_fastpath(self, products: list) -> list[dict]:
        """
        使用 Fast Path 规则引擎为商品列表添加折扣建议。

        Args:
            products: 商品列表

        Returns:
            商品列表，每个商品包含 _fast_path 字段（Fast Path 评估结果）
        """
        if not products:
            return products

        # 转换为 Fast Path 评估格式
        products_for_eval = []
        for p in products:
            product = {
                "product_id": p.get("product_id") or p.get("sku", "UNKNOWN"),
                "name": p.get("name", "商品"),
                "expiry_date": p.get("expiry_date", ""),
                "category": p.get("category", ""),
                "stock": p.get("stock", 0),
                "is_imported": p.get("is_imported", False),
                "is_organic": p.get("is_organic", False),
                "is_promoted": p.get("is_promoted", False),
                "arrival_days": p.get("arrival_days"),
                "days_left": p.get("days_left"),
            }
            products_for_eval.append(product)

        # 批量评估
        rules = self._fast_path.evaluate_batch(products_for_eval)

        # 合并结果
        enriched = []
        for p, rule in zip(products, rules):
            enriched_item = {**p, "_fast_path": rule.to_dict()}
            enriched.append(enriched_item)

        return enriched

    def _generate_bar_chart(self, products: list) -> str:
        """生成临期商品柱状图（ASCII 艺术风格）。"""
        from collections import Counter
        days_counts = Counter()
        for p in products:
            days = p.get("days_left", 0)
            if days <= 0:
                label = "0天"
            elif days == 1:
                label = "1天"
            elif days == 2:
                label = "2天"
            elif days == 3:
                label = "3天"
            else:
                label = "4天及以上"
            days_counts[label] += 1
        ordered_labels = ["0天", "1天", "2天", "3天", "4天及以上"]
        counts = [days_counts.get(label, 0) for label in ordered_labels]
        max_count = max(counts) if counts else 1
        lines = ["📊 临期商品柱状图（按临期天数）", "", "商品数量(种)"]
        for y in range(max_count, 0, -1):
            row = f"{y} ┤"
            for c in counts:
                row += "  ██" if c >= y else "   "
            lines.append(row)
        lines.append("0 ┼" + "─" * (len(counts) * 4))
        lines.append("  " + "  ".join(ordered_labels))
        return "\n".join(lines)
