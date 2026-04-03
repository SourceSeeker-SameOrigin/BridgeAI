"""Tests for app.engine.prompt_optimizer — 5-layer prompt fusion."""

import pytest

from app.engine.prompt_optimizer import (
    ANALYSIS_INSTRUCTION,
    _build_fewshot_section,
    build_optimized_prompt,
)


class TestBuildFewshotSection:
    """Test few-shot section builder."""

    def test_empty_list_returns_empty_string(self) -> None:
        assert _build_fewshot_section([]) == ""

    def test_none_like_empty(self) -> None:
        # The function expects a list; empty list should be safe
        assert _build_fewshot_section([]) == ""

    def test_single_example(self) -> None:
        examples = [{"user_message": "Hello", "ai_response": "Hi there!"}]
        result = _build_fewshot_section(examples)
        assert "Hello" in result
        assert "Hi there!" in result
        assert "示例 1" in result

    def test_multiple_examples_numbered(self) -> None:
        examples = [
            {"user_message": "Q1", "ai_response": "A1"},
            {"user_message": "Q2", "ai_response": "A2"},
        ]
        result = _build_fewshot_section(examples)
        assert "示例 1" in result
        assert "示例 2" in result

    def test_long_response_truncated(self) -> None:
        long_resp = "x" * 1000
        examples = [{"user_message": "Q", "ai_response": long_resp}]
        result = _build_fewshot_section(examples)
        assert "..." in result
        assert len(result) < 1000

    def test_missing_keys_handled(self) -> None:
        examples = [{"user_message": "Q"}]
        result = _build_fewshot_section(examples)
        # Should not crash, ai_response defaults to ""
        assert "Q" in result

    def test_section_header_present(self) -> None:
        examples = [{"user_message": "Q", "ai_response": "A"}]
        result = _build_fewshot_section(examples)
        assert "优质回答示例" in result


class TestBuildOptimizedPrompt:
    """Test the 5-layer prompt fusion."""

    def _get_system_content(self, result: list[dict]) -> str:
        for msg in result:
            if msg["role"] == "system":
                return msg["content"]
        return ""

    # --- Layer 1: Base system prompt ---
    def test_base_system_prompt_always_included(self) -> None:
        result = build_optimized_prompt(None, [{"role": "user", "content": "hi"}])
        system = self._get_system_content(result)
        assert "BridgeAI" in system
        assert "intelligent assistant" in system

    # --- Layer 2: Agent system prompt ---
    def test_agent_prompt_included(self) -> None:
        result = build_optimized_prompt(
            "You are a finance expert.",
            [{"role": "user", "content": "hi"}],
        )
        system = self._get_system_content(result)
        assert "finance expert" in system

    def test_none_agent_prompt_no_extra(self) -> None:
        result = build_optimized_prompt(None, [{"role": "user", "content": "hi"}])
        system = self._get_system_content(result)
        # Should still work without agent prompt
        assert "BridgeAI" in system

    def test_empty_agent_prompt_treated_as_falsy(self) -> None:
        result = build_optimized_prompt("", [{"role": "user", "content": "hi"}])
        system = self._get_system_content(result)
        # Empty string is falsy, so no agent prompt appended
        assert "BridgeAI" in system

    # --- Layer 3: Few-shot examples ---
    def test_fewshot_examples_injected(self) -> None:
        examples = [{"user_message": "What is AI?", "ai_response": "AI is ..."}]
        result = build_optimized_prompt(
            "Agent prompt",
            [{"role": "user", "content": "test"}],
            fewshot_examples=examples,
        )
        system = self._get_system_content(result)
        assert "What is AI?" in system
        assert "优质回答示例" in system

    def test_no_fewshot_no_section(self) -> None:
        result = build_optimized_prompt(
            "Agent prompt",
            [{"role": "user", "content": "test"}],
            fewshot_examples=None,
        )
        system = self._get_system_content(result)
        assert "优质回答示例" not in system

    def test_empty_fewshot_list_no_section(self) -> None:
        result = build_optimized_prompt(
            "Agent prompt",
            [{"role": "user", "content": "test"}],
            fewshot_examples=[],
        )
        system = self._get_system_content(result)
        assert "优质回答示例" not in system

    # --- Layer 4: Intent context hint ---
    def test_intent_hint_question(self) -> None:
        result = build_optimized_prompt(
            None,
            [{"role": "user", "content": "test"}],
            intent="question",
        )
        system = self._get_system_content(result)
        assert "asking a question" in system

    def test_intent_hint_generation(self) -> None:
        result = build_optimized_prompt(
            None,
            [{"role": "user", "content": "test"}],
            intent="generation",
        )
        system = self._get_system_content(result)
        assert "generate content" in system

    def test_intent_hint_debugging(self) -> None:
        result = build_optimized_prompt(
            None,
            [{"role": "user", "content": "test"}],
            intent="debugging",
        )
        system = self._get_system_content(result)
        assert "debugging" in system

    def test_intent_hint_summarization(self) -> None:
        result = build_optimized_prompt(
            None,
            [{"role": "user", "content": "test"}],
            intent="summarization",
        )
        system = self._get_system_content(result)
        assert "summary" in system

    def test_unknown_intent_no_hint(self) -> None:
        result = build_optimized_prompt(
            None,
            [{"role": "user", "content": "test"}],
            intent="unknown_intent",
        )
        system = self._get_system_content(result)
        # Unknown intent not in the mapping → no extra hint appended
        assert "asking a question" not in system

    def test_none_intent_no_hint(self) -> None:
        result = build_optimized_prompt(
            None,
            [{"role": "user", "content": "test"}],
            intent=None,
        )
        system = self._get_system_content(result)
        assert "asking a question" not in system

    # --- Layer 5: Analysis instruction ---
    def test_analysis_instruction_appended(self) -> None:
        result = build_optimized_prompt(None, [{"role": "user", "content": "hi"}])
        system = self._get_system_content(result)
        assert "<analysis>" in system
        assert "emotion" in system
        assert "intent" in system

    # --- Message handling ---
    def test_messages_included_in_output(self) -> None:
        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = build_optimized_prompt(None, msgs)
        # system + 2 messages = 3
        assert len(result) == 3
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"

    def test_context_window_limits_messages(self) -> None:
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        result = build_optimized_prompt(None, msgs, context_window=5)
        # system + 5 recent messages = 6
        assert len(result) == 6
        # Should include last 5 messages
        assert result[-1]["content"] == "msg19"
        assert result[-5]["content"] == "msg15"

    def test_context_window_larger_than_messages(self) -> None:
        msgs = [{"role": "user", "content": "only"}]
        result = build_optimized_prompt(None, msgs, context_window=100)
        assert len(result) == 2  # system + 1 message

    def test_empty_messages(self) -> None:
        result = build_optimized_prompt(None, [])
        assert len(result) == 1  # only system
        assert result[0]["role"] == "system"

    # --- Full fusion ---
    def test_full_fusion_order(self) -> None:
        examples = [{"user_message": "Q", "ai_response": "A"}]
        result = build_optimized_prompt(
            "Custom agent",
            [{"role": "user", "content": "test"}],
            intent="question",
            fewshot_examples=examples,
        )
        system = self._get_system_content(result)

        # Verify order: base → agent → fewshot → intent → analysis
        base_idx = system.index("BridgeAI")
        agent_idx = system.index("Custom agent")
        fewshot_idx = system.index("优质回答示例")
        hint_idx = system.index("asking a question")
        analysis_idx = system.index("<analysis>")

        assert base_idx < agent_idx < fewshot_idx < hint_idx < analysis_idx
