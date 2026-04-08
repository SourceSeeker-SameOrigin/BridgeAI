"""Ecommerce industry plugin — Listing optimization, competitor analysis, etc."""

import json
import logging
from typing import Any

from app.plugins.base import PluginBase, PluginPromptTemplate, PluginTool
from app.plugins.industries.ecommerce.prompts import (
    ANALYZE_COMPETITORS_PROMPT,
    GENERATE_REVIEW_RESPONSE_PROMPT,
    OPTIMIZE_LISTING_PROMPT,
    SYSTEM_PROMPT_EXTENSION,
    TRANSLATE_LISTING_PROMPT,
)
from app.providers.registry import get_provider_registry

logger = logging.getLogger(__name__)

# Preferred provider/model for ecommerce tasks
_PREFERRED_PROVIDER = "deepseek"
_PREFERRED_MODEL = "deepseek-chat"


class EcommercePlugin(PluginBase):
    """Cross-border ecommerce plugin for BridgeAI."""

    name = "ecommerce"
    display_name = "跨境电商助手"
    description = "跨境电商行业插件：Listing 优化、竞品分析、评论回复、多语言翻译"
    version = "1.0.0"
    category = "ecommerce"

    def get_tools(self) -> list[PluginTool]:
        return [
            PluginTool(
                name="optimize_listing",
                description="优化亚马逊产品 Listing（标题、五点描述、详情、关键词）",
                parameters={
                    "type": "object",
                    "properties": {
                        "product_name": {
                            "type": "string",
                            "description": "产品名称",
                        },
                        "features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "产品特点列表",
                        },
                        "target_market": {
                            "type": "string",
                            "description": "目标市场（如：美国、日本、欧洲）",
                            "default": "美国",
                        },
                    },
                    "required": ["product_name", "features"],
                },
            ),
            PluginTool(
                name="analyze_competitors",
                description="分析竞品市场和定价策略，给出差异化建议",
                parameters={
                    "type": "object",
                    "properties": {
                        "product_category": {
                            "type": "string",
                            "description": "产品类别",
                        },
                        "price_range": {
                            "type": "string",
                            "description": "价格区间（如：$20-$50）",
                        },
                    },
                    "required": ["product_category", "price_range"],
                },
            ),
            PluginTool(
                name="generate_review_response",
                description="根据买家评论内容和情绪，生成专业的回复",
                parameters={
                    "type": "object",
                    "properties": {
                        "review_text": {
                            "type": "string",
                            "description": "买家评论原文",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral"],
                            "description": "评论情绪",
                        },
                    },
                    "required": ["review_text", "sentiment"],
                },
            ),
            PluginTool(
                name="translate_listing",
                description="将产品 Listing 翻译并本地化为目标语言",
                parameters={
                    "type": "object",
                    "properties": {
                        "listing_text": {
                            "type": "string",
                            "description": "待翻译的 Listing 文本",
                        },
                        "target_language": {
                            "type": "string",
                            "description": "目标语言（如：English、日本語、Deutsch）",
                        },
                    },
                    "required": ["listing_text", "target_language"],
                },
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name, dispatching to the appropriate handler."""
        handlers = {
            "optimize_listing": self._optimize_listing,
            "analyze_competitors": self._analyze_competitors,
            "generate_review_response": self._generate_review_response,
            "translate_listing": self._translate_listing,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"Unknown tool: {tool_name}", "data": None}

        try:
            result = await handler(arguments)
            return {"success": True, "data": result, "error": None}
        except Exception as e:
            logger.error("Ecommerce plugin tool '%s' failed: %s", tool_name, e, exc_info=True)
            return {"success": False, "error": str(e), "data": None}

    def get_prompt_templates(self) -> list[PluginPromptTemplate]:
        return [
            PluginPromptTemplate(
                name="optimize_listing",
                template=OPTIMIZE_LISTING_PROMPT,
                description="亚马逊 Listing 优化提示词模板",
            ),
            PluginPromptTemplate(
                name="analyze_competitors",
                template=ANALYZE_COMPETITORS_PROMPT,
                description="竞品分析提示词模板",
            ),
            PluginPromptTemplate(
                name="generate_review_response",
                template=GENERATE_REVIEW_RESPONSE_PROMPT,
                description="评论回复提示词模板",
            ),
            PluginPromptTemplate(
                name="translate_listing",
                template=TRANSLATE_LISTING_PROMPT,
                description="Listing 翻译提示词模板",
            ),
        ]

    def get_system_prompt_extension(self) -> str:
        return SYSTEM_PROMPT_EXTENSION

    # ------------------------------------------------------------------
    # Internal tool handlers
    # ------------------------------------------------------------------

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM via provider registry, with fallback."""
        registry = get_provider_registry()

        # Try preferred provider first, then any available
        try:
            provider = registry.get_provider(_PREFERRED_PROVIDER)
            provider_name = _PREFERRED_PROVIDER
            model = _PREFERRED_MODEL
        except ValueError:
            provider_name, provider = registry.get_any_provider()
            model = "deepseek-chat"  # reasonable default

        messages = [
            {"role": "system", "content": "你是一位专业的跨境电商顾问。请严格按照要求的 JSON 格式输出结果。"},
            {"role": "user", "content": prompt},
        ]

        response = await provider.chat(
            messages=messages,
            model=model,
            stream=False,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.content

    def _parse_json_response(self, text: str) -> Any:
        """Extract JSON from LLM response, handling markdown code blocks."""
        cleaned = text.strip()
        # Strip markdown code fence if present
        if cleaned.startswith("```"):
            # Remove first line (```json or ```)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Return raw text wrapped in a dict
            return {"raw_response": text}

    async def _optimize_listing(self, args: dict) -> Any:
        product_name = args.get("product_name", "")
        features = args.get("features", [])
        target_market = args.get("target_market", "美国")

        features_text = "\n".join(f"- {f}" for f in features) if isinstance(features, list) else str(features)

        prompt = OPTIMIZE_LISTING_PROMPT.format(
            product_name=product_name,
            features=features_text,
            target_market=target_market,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)

    async def _analyze_competitors(self, args: dict) -> Any:
        product_category = args.get("product_category", "")
        price_range = args.get("price_range", "")

        prompt = ANALYZE_COMPETITORS_PROMPT.format(
            product_category=product_category,
            price_range=price_range,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)

    async def _generate_review_response(self, args: dict) -> Any:
        review_text = args.get("review_text", "")
        sentiment = args.get("sentiment", "neutral")

        prompt = GENERATE_REVIEW_RESPONSE_PROMPT.format(
            review_text=review_text,
            sentiment=sentiment,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)

    async def _translate_listing(self, args: dict) -> Any:
        listing_text = args.get("listing_text", "")
        target_language = args.get("target_language", "English")

        prompt = TRANSLATE_LISTING_PROMPT.format(
            listing_text=listing_text,
            target_language=target_language,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)
