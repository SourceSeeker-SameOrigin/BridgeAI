"""Education industry plugin — Question generation, learning analysis, courseware, concept explanation."""

import json
import logging
from typing import Any

from app.plugins.base import PluginBase, PluginPromptTemplate, PluginTool
from app.plugins.industries.education.prompts import (
    ANALYZE_LEARNING_PROMPT,
    EXPLAIN_CONCEPT_PROMPT,
    GENERATE_COURSEWARE_PROMPT,
    GENERATE_QUESTIONS_PROMPT,
    SYSTEM_PROMPT_EXTENSION,
)
from app.providers.registry import get_provider_registry

logger = logging.getLogger(__name__)

# Preferred provider/model for education tasks
_PREFERRED_PROVIDER = "deepseek"
_PREFERRED_MODEL = "deepseek-chat"


class EducationPlugin(PluginBase):
    """Education industry plugin for BridgeAI."""

    name = "education"
    display_name = "智慧教育助手"
    description = "教育行业插件：智能出题、学情分析、课件生成、概念讲解"
    version = "1.0.0"
    category = "education"

    def get_tools(self) -> list[PluginTool]:
        return [
            PluginTool(
                name="generate_questions",
                description="根据学科、知识点和难度智能生成练习题（选择题、填空题、简答题）",
                parameters={
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "学科名称（如：数学、物理、英语）",
                        },
                        "knowledge_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "知识点列表",
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard"],
                            "description": "难度等级",
                            "default": "medium",
                        },
                        "question_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "题型列表（如：选择题、填空题、简答题）",
                            "default": ["选择题"],
                        },
                        "count": {
                            "type": "integer",
                            "description": "题目数量",
                            "default": 5,
                        },
                    },
                    "required": ["subject", "knowledge_points"],
                },
            ),
            PluginTool(
                name="analyze_learning",
                description="分析学生答题记录，生成学情分析报告，包含薄弱环节和学习建议",
                parameters={
                    "type": "object",
                    "properties": {
                        "student_answers": {
                            "type": "string",
                            "description": "学生答题记录（JSON 字符串或文本描述）",
                        },
                    },
                    "required": ["student_answers"],
                },
            ),
            PluginTool(
                name="generate_courseware",
                description="根据课题、年级和课时生成结构化课件大纲",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "课题名称",
                        },
                        "grade_level": {
                            "type": "string",
                            "description": "年级水平（如：小学三年级、高中一年级）",
                        },
                        "duration": {
                            "type": "integer",
                            "description": "课时长度（分钟）",
                            "default": 45,
                        },
                    },
                    "required": ["topic", "grade_level"],
                },
            ),
            PluginTool(
                name="explain_concept",
                description="用通俗易懂的方式解释学科概念，适配不同学生水平",
                parameters={
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "要解释的概念",
                        },
                        "student_level": {
                            "type": "string",
                            "description": "学生水平（如：小学生、初中生、高中生、大学生）",
                            "default": "初中生",
                        },
                    },
                    "required": ["concept"],
                },
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name, dispatching to the appropriate handler."""
        handlers = {
            "generate_questions": self._generate_questions,
            "analyze_learning": self._analyze_learning,
            "generate_courseware": self._generate_courseware,
            "explain_concept": self._explain_concept,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"Unknown tool: {tool_name}", "data": None}

        try:
            result = await handler(arguments)
            return {"success": True, "data": result, "error": None}
        except Exception as e:
            logger.error("Education plugin tool '%s' failed: %s", tool_name, e, exc_info=True)
            return {"success": False, "error": str(e), "data": None}

    def get_prompt_templates(self) -> list[PluginPromptTemplate]:
        return [
            PluginPromptTemplate(
                name="generate_questions",
                template=GENERATE_QUESTIONS_PROMPT,
                description="智能出题提示词模板",
            ),
            PluginPromptTemplate(
                name="analyze_learning",
                template=ANALYZE_LEARNING_PROMPT,
                description="学情分析提示词模板",
            ),
            PluginPromptTemplate(
                name="generate_courseware",
                template=GENERATE_COURSEWARE_PROMPT,
                description="课件生成提示词模板",
            ),
            PluginPromptTemplate(
                name="explain_concept",
                template=EXPLAIN_CONCEPT_PROMPT,
                description="概念讲解提示词模板",
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

        try:
            provider = registry.get_provider(_PREFERRED_PROVIDER)
            model = _PREFERRED_MODEL
        except ValueError:
            _provider_name, provider = registry.get_any_provider()
            model = "deepseek-chat"

        messages = [
            {"role": "system", "content": "你是一位资深的教育专家。请严格按照要求的 JSON 格式输出结果。"},
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
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw_response": text}

    async def _generate_questions(self, args: dict) -> Any:
        subject = args.get("subject", "")
        knowledge_points = args.get("knowledge_points", [])
        difficulty = args.get("difficulty", "medium")
        question_types = args.get("question_types", ["选择题"])
        count = args.get("count", 5)

        kp_text = ", ".join(knowledge_points) if isinstance(knowledge_points, list) else str(knowledge_points)
        qt_text = ", ".join(question_types) if isinstance(question_types, list) else str(question_types)
        kp_json = json.dumps(knowledge_points, ensure_ascii=False) if isinstance(knowledge_points, list) else str(knowledge_points)

        prompt = GENERATE_QUESTIONS_PROMPT.format(
            subject=subject,
            knowledge_points=kp_text,
            difficulty=difficulty,
            question_types=qt_text,
            count=count,
            knowledge_points_json=kp_json,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)

    async def _analyze_learning(self, args: dict) -> Any:
        student_answers = args.get("student_answers", "")

        prompt = ANALYZE_LEARNING_PROMPT.format(
            student_answers=student_answers,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)

    async def _generate_courseware(self, args: dict) -> Any:
        topic = args.get("topic", "")
        grade_level = args.get("grade_level", "")
        duration = args.get("duration", 45)

        prompt = GENERATE_COURSEWARE_PROMPT.format(
            topic=topic,
            grade_level=grade_level,
            duration=duration,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)

    async def _explain_concept(self, args: dict) -> Any:
        concept = args.get("concept", "")
        student_level = args.get("student_level", "初中生")

        prompt = EXPLAIN_CONCEPT_PROMPT.format(
            concept=concept,
            student_level=student_level,
        )
        raw = await self._call_llm(prompt)
        return self._parse_json_response(raw)
