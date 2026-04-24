"""Finance (财税) industry plugin — accounting vouchers, tax risk, policy Q&A, reports."""

import logging
from typing import Any

from app.config import settings
from app.plugins.base import PluginBase, PluginTool
from app.plugins.industries.finance.prompts import (
    POLICY_QA_SYSTEM,
    POLICY_QA_USER_TEMPLATE,
    REPORT_SYSTEM,
    REPORT_USER_TEMPLATE,
    TAX_RISK_SYSTEM,
    TAX_RISK_USER_TEMPLATE,
    VOUCHER_SYSTEM,
    VOUCHER_USER_TEMPLATE,
)
from app.providers.deepseek_provider import DeepSeekProvider

logger = logging.getLogger(__name__)

# DeepSeek model used for finance tasks
_DEFAULT_MODEL = "deepseek-v4-pro"


class FinancePlugin(PluginBase):
    """财税助手插件 — 智能记账、税务风险检测、政策问答、报表生成。"""

    name = "finance"
    display_name = "财税助手"
    description = "提供智能记账凭证生成、税务风险检测、财税政策问答、财务报表生成等财税领域专业能力"
    version = "1.0.0"
    category = "finance"

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    def get_tools(self) -> list[PluginTool]:
        return [
            PluginTool(
                name="generate_voucher",
                description="根据交易描述生成会计凭证（借贷分录），遵循中国企业会计准则",
                parameters={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "交易描述，如'购买办公用品'",
                        },
                        "amount": {
                            "type": "number",
                            "description": "交易金额（人民币元）",
                        },
                        "date": {
                            "type": "string",
                            "description": "交易日期，格式 YYYY-MM-DD",
                        },
                        "extra": {
                            "type": "string",
                            "description": "补充信息（如纳税人类型、税率等），可选",
                            "default": "",
                        },
                    },
                    "required": ["description", "amount", "date"],
                },
            ),
            PluginTool(
                name="tax_risk_check",
                description="根据企业财务摘要数据进行税务风险检测，输出风险报告",
                parameters={
                    "type": "object",
                    "properties": {
                        "revenue": {
                            "type": "number",
                            "description": "营业收入（元）",
                        },
                        "costs": {
                            "type": "number",
                            "description": "营业成本（元）",
                        },
                        "tax_paid": {
                            "type": "number",
                            "description": "已缴税额（元）",
                        },
                        "extra": {
                            "type": "string",
                            "description": "补充信息（如行业类型、进项税额等），可选",
                            "default": "",
                        },
                    },
                    "required": ["revenue", "costs", "tax_paid"],
                },
            ),
            PluginTool(
                name="policy_qa",
                description="回答中国财税政策相关问题，引用具体法规条款",
                parameters={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "财税政策问题",
                        },
                    },
                    "required": ["question"],
                },
            ),
            PluginTool(
                name="generate_report",
                description="根据关键数据生成财务报表（利润表/资产负债表/现金流量表）",
                parameters={
                    "type": "object",
                    "properties": {
                        "report_type": {
                            "type": "string",
                            "description": "报表类型：利润表、资产负债表、现金流量表",
                            "enum": ["利润表", "资产负债表", "现金流量表"],
                        },
                        "period": {
                            "type": "string",
                            "description": "报告期间，如'2026年第一季度'",
                        },
                        "key_figures": {
                            "type": "string",
                            "description": "关键财务数据描述",
                        },
                        "extra": {
                            "type": "string",
                            "description": "补充信息，可选",
                            "default": "",
                        },
                    },
                    "required": ["report_type", "period", "key_figures"],
                },
            ),
        ]

    # ------------------------------------------------------------------
    # System prompt extension
    # ------------------------------------------------------------------

    def get_system_prompt_extension(self) -> str:
        return (
            "【财税助手插件已启用】\n"
            "你现在具备专业的中国财税能力，包括：会计凭证生成、税务风险检测、"
            "财税政策问答、财务报表生成。请在需要时调用对应的插件工具。"
        )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        dispatch = {
            "generate_voucher": self._generate_voucher,
            "tax_risk_check": self._tax_risk_check,
            "policy_qa": self._policy_qa,
            "generate_report": self._generate_report,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"未知工具: {tool_name}"}
        try:
            result = await handler(arguments)
            return {"success": True, "data": result}
        except Exception as e:
            logger.exception("Finance tool '%s' failed", tool_name)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    async def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法调用财税插件")

        provider = DeepSeekProvider(api_key=api_key)
        try:
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=_DEFAULT_MODEL,
                temperature=0.3,
                max_tokens=4096,
            )
            return response.content  # type: ignore[union-attr]
        finally:
            await provider.close()

    async def _generate_voucher(self, args: dict[str, Any]) -> str:
        user_prompt = VOUCHER_USER_TEMPLATE.format(
            description=args["description"],
            amount=args["amount"],
            date=args["date"],
            extra=args.get("extra", ""),
        )
        return await self._call_deepseek(VOUCHER_SYSTEM, user_prompt)

    async def _tax_risk_check(self, args: dict[str, Any]) -> str:
        user_prompt = TAX_RISK_USER_TEMPLATE.format(
            revenue=args["revenue"],
            costs=args["costs"],
            tax_paid=args["tax_paid"],
            extra=args.get("extra", ""),
        )
        return await self._call_deepseek(TAX_RISK_SYSTEM, user_prompt)

    async def _policy_qa(self, args: dict[str, Any]) -> str:
        user_prompt = POLICY_QA_USER_TEMPLATE.format(question=args["question"])
        return await self._call_deepseek(POLICY_QA_SYSTEM, user_prompt)

    async def _generate_report(self, args: dict[str, Any]) -> str:
        user_prompt = REPORT_USER_TEMPLATE.format(
            report_type=args["report_type"],
            period=args["period"],
            key_figures=args["key_figures"],
            extra=args.get("extra", ""),
        )
        return await self._call_deepseek(REPORT_SYSTEM, user_prompt)
