"""Legal (法律) industry plugin — contract review, document generation, case analysis, legal Q&A."""

import logging
from typing import Any

from app.config import settings
from app.plugins.base import PluginBase, PluginTool
from app.plugins.industries.legal.prompts import (
    CASE_SEARCH_SYSTEM,
    CASE_SEARCH_USER_TEMPLATE,
    CONTRACT_REVIEW_SYSTEM,
    CONTRACT_REVIEW_USER_TEMPLATE,
    DOCUMENT_GEN_SYSTEM,
    DOCUMENT_GEN_USER_TEMPLATE,
    LEGAL_QA_SYSTEM,
    LEGAL_QA_USER_TEMPLATE,
)
from app.providers.deepseek_provider import DeepSeekProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "deepseek-v4-pro"


class LegalPlugin(PluginBase):
    """法律助手插件 — 合同审查、文书生成、案例检索、法律问答。"""

    name = "legal"
    display_name = "法律助手"
    description = "提供合同风险审查、法律文书生成、案例法律分析、法律问题问答等法律领域专业能力"
    version = "1.0.0"
    category = "legal"

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    def get_tools(self) -> list[PluginTool]:
        return [
            PluginTool(
                name="review_contract",
                description="对合同文本进行逐条审查，评估风险等级并给出修改建议",
                parameters={
                    "type": "object",
                    "properties": {
                        "contract_text": {
                            "type": "string",
                            "description": "合同文本或关键条款内容",
                        },
                        "extra": {
                            "type": "string",
                            "description": "补充要求（如重点关注的条款），可选",
                            "default": "",
                        },
                    },
                    "required": ["contract_text"],
                },
            ),
            PluginTool(
                name="generate_document",
                description="根据案情要素生成规范的法律文书（起诉状/答辩状/律师函/合同）",
                parameters={
                    "type": "object",
                    "properties": {
                        "document_type": {
                            "type": "string",
                            "description": "文书类型",
                            "enum": ["起诉状", "答辩状", "律师函", "合同"],
                        },
                        "key_facts": {
                            "type": "string",
                            "description": "案情要素或关键事实描述",
                        },
                        "extra": {
                            "type": "string",
                            "description": "补充信息，可选",
                            "default": "",
                        },
                    },
                    "required": ["document_type", "key_facts"],
                },
            ),
            PluginTool(
                name="search_cases",
                description="根据案情和法律问题进行法律分析，提供相关法律原则和建议方案",
                parameters={
                    "type": "object",
                    "properties": {
                        "case_description": {
                            "type": "string",
                            "description": "案情描述",
                        },
                        "legal_issue": {
                            "type": "string",
                            "description": "需要分析的法律问题",
                        },
                        "extra": {
                            "type": "string",
                            "description": "补充信息，可选",
                            "default": "",
                        },
                    },
                    "required": ["case_description", "legal_issue"],
                },
            ),
            PluginTool(
                name="legal_qa",
                description="回答法律问题，引用具体法律条款",
                parameters={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "法律问题",
                        },
                    },
                    "required": ["question"],
                },
            ),
        ]

    # ------------------------------------------------------------------
    # System prompt extension
    # ------------------------------------------------------------------

    def get_system_prompt_extension(self) -> str:
        return (
            "【法律助手插件已启用】\n"
            "你现在具备专业的中国法律能力，包括：合同风险审查、法律文书生成、"
            "案例法律分析、法律问题问答。请在需要时调用对应的插件工具。"
        )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        dispatch = {
            "review_contract": self._review_contract,
            "generate_document": self._generate_document,
            "search_cases": self._search_cases,
            "legal_qa": self._legal_qa,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"未知工具: {tool_name}"}
        try:
            result = await handler(arguments)
            return {"success": True, "data": result}
        except Exception as e:
            logger.exception("Legal tool '%s' failed", tool_name)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    async def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法调用法律插件")

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

    async def _review_contract(self, args: dict[str, Any]) -> str:
        user_prompt = CONTRACT_REVIEW_USER_TEMPLATE.format(
            contract_text=args["contract_text"],
            extra=args.get("extra", ""),
        )
        return await self._call_deepseek(CONTRACT_REVIEW_SYSTEM, user_prompt)

    async def _generate_document(self, args: dict[str, Any]) -> str:
        user_prompt = DOCUMENT_GEN_USER_TEMPLATE.format(
            document_type=args["document_type"],
            key_facts=args["key_facts"],
            extra=args.get("extra", ""),
        )
        return await self._call_deepseek(DOCUMENT_GEN_SYSTEM, user_prompt)

    async def _search_cases(self, args: dict[str, Any]) -> str:
        user_prompt = CASE_SEARCH_USER_TEMPLATE.format(
            case_description=args["case_description"],
            legal_issue=args["legal_issue"],
            extra=args.get("extra", ""),
        )
        return await self._call_deepseek(CASE_SEARCH_SYSTEM, user_prompt)

    async def _legal_qa(self, args: dict[str, Any]) -> str:
        user_prompt = LEGAL_QA_USER_TEMPLATE.format(question=args["question"])
        return await self._call_deepseek(LEGAL_QA_SYSTEM, user_prompt)
