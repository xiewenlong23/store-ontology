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

    def execute(self, user_message: str, context: Optional[dict] = None) -> dict:
        """
        执行用户消息 — LLM Agent 循环直到完成。

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
            if not should_continue:
                final_response = reasoning if reasoning else decision.get("response", "")
                break

            # LLM 无法决策（unknown tool 后会 continue），最多重试 MAX_UNKNOWN_TOOL_RETRIES 次
            if not tool_name:
                unknown_tool_retries += 1
                if unknown_tool_retries >= MAX_UNKNOWN_TOOL_RETRIES:
                    final_response = "无法识别您的意图，请重新描述需求。"
                    break
                continue

            # 执行工具
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
            response = llm.chat(messages)
        except ValueError as e:
            logger.warning("[AgentExecutor] LLM not available: %s", e)
            return {"tool_name": None, "tool_args": {}, "reasoning": "LLM 未配置", "continue": False}
        except Exception as e:
            logger.error("[AgentExecutor] LLM call failed: %s", e)
            return {"tool_name": None, "tool_args": {}, "reasoning": f"LLM 错误: {e}", "continue": False}

        return self._parse_llm_decision(response)

    def _parse_llm_decision(self, llm_response: str) -> dict:
        """
        解析 LLM 返回的决策。

        支持格式：
        1. JSON: {"tool": "xxx", "args": {...}, "reasoning": "...", "continue": true/false}
        2. 纯文本字符串 → 认为是最终回答，continue=False
        """
        import re

        response = llm_response.strip()

        # 尝试 JSON 解析
        try:
            obj = json.loads(response)
            if isinstance(obj, dict):
                tool_name = obj.get("tool") or obj.get("tool_name")
                tool_args = obj.get("args") or obj.get("tool_args") or {}
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
        except (json.JSONDecodeError, ValueError):
            pass

        # 非 JSON：检查是否包含工具名
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

    def _build_response_from_result(
        self, tool_name: Optional[str], tool_result: Optional[dict], user_message: str
    ) -> str:
        if not tool_result:
            return "处理完成，但没有返回结果。"

        if not tool_result.get("success", False):
            return f"操作失败：{tool_result.get('error', '未知错误')}"

        if not tool_name:
            return str(tool_result.get("message", tool_result))

        if tool_name == "query_pending_products":
            products = tool_result.get("products", [])
            count = tool_result.get("count", len(products))
            if count == 0:
                return "当前没有临期商品，库存都很新鲜。"
            lines = [f"当前共有 {count} 件临期商品："]
            for p in products[:5]:
                lines.append(
                    f"- {p.get('name', '未知')}，"
                    f"剩余 {p.get('days_left', '?')} 天，"
                    f"库存 {p.get('stock', '?')} 件"
                )
            if count > 5:
                lines.append(f"...还有 {count - 5} 件商品")
            return "\n".join(lines)

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
            return "\n".join(lines)

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
            return "\n".join(lines)

        if tool_name in ("create_task", "confirm_task", "execute_task", "review_task"):
            return tool_result.get("message", "操作完成。")

        return tool_result.get("message", json.dumps(tool_result, ensure_ascii=False, indent=2)[:500])
