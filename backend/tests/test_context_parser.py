"""Tests for app.engine.context_parser."""

import pytest

from app.engine.context_parser import normalize_analysis, parse_analysis, strip_analysis


class TestParseAnalysis:
    """Tests for parse_analysis function."""

    def test_valid_analysis_block(self) -> None:
        content = (
            'Hello!\n<analysis>\n{"intent": "question", "emotion": "neutral"}\n</analysis>\nWorld'
        )
        result = parse_analysis(content)
        assert result is not None
        assert result["intent"] == "question"
        assert result["emotion"] == "neutral"

    def test_no_analysis_block(self) -> None:
        content = "Just a normal response without any analysis tags."
        result = parse_analysis(content)
        assert result is None

    def test_empty_analysis_block(self) -> None:
        content = "<analysis>\n\n</analysis>"
        result = parse_analysis(content)
        assert result is None

    def test_invalid_json_in_analysis(self) -> None:
        content = "<analysis>\n{invalid json here}\n</analysis>"
        result = parse_analysis(content)
        assert result is None

    def test_analysis_with_extra_whitespace(self) -> None:
        content = '<analysis>   \n  {"confidence": 0.9, "intent": "test"}  \n   </analysis>'
        result = parse_analysis(content)
        assert result is not None
        assert result["confidence"] == 0.9
        assert result["intent"] == "test"

    def test_normalized_output_has_required_fields(self) -> None:
        content = '<analysis>\n{"intent": "query"}\n</analysis>'
        result = parse_analysis(content)
        assert result is not None
        # All blueprint fields should be present after normalization
        assert "emotion" in result
        assert "intent" in result
        assert "complexity" in result
        assert "key_facts" in result
        assert "needs_tool" in result
        assert "suggested_tools" in result

    def test_analysis_with_unicode_intent(self) -> None:
        content = '<analysis>\n{"intent": "查询天气", "emotion": "neutral"}\n</analysis>'
        result = parse_analysis(content)
        assert result is not None
        assert result["intent"] == "查询天气"

    def test_multiple_analysis_blocks_uses_first(self) -> None:
        content = (
            '<analysis>{"intent": "first"}</analysis>'
            'middle text'
            '<analysis>{"intent": "second"}</analysis>'
        )
        result = parse_analysis(content)
        assert result is not None
        assert result["intent"] == "first"


class TestNormalizeAnalysis:
    """Tests for normalize_analysis function."""

    def test_defaults_for_empty_dict(self) -> None:
        result = normalize_analysis({})
        assert result["emotion"] == "neutral"
        assert result["intent"] == "general"
        assert result["complexity"] == "medium"
        assert result["key_facts"] == []
        assert result["needs_tool"] is False
        assert result["suggested_tools"] == []

    def test_valid_emotion_values(self) -> None:
        for emotion in ("positive", "negative", "confused", "urgent", "neutral"):
            result = normalize_analysis({"emotion": emotion})
            assert result["emotion"] == emotion

    def test_invalid_emotion_defaults_to_neutral(self) -> None:
        result = normalize_analysis({"emotion": "unknown_emotion"})
        assert result["emotion"] == "neutral"

    def test_legacy_emotion_mapping(self) -> None:
        assert normalize_analysis({"emotion": "frustrated"})["emotion"] == "negative"
        assert normalize_analysis({"emotion": "curious"})["emotion"] == "neutral"
        assert normalize_analysis({"emotion": "excited"})["emotion"] == "positive"

    def test_complexity_validation(self) -> None:
        assert normalize_analysis({"complexity": "low"})["complexity"] == "low"
        assert normalize_analysis({"complexity": "high"})["complexity"] == "high"
        assert normalize_analysis({"complexity": "invalid"})["complexity"] == "medium"

    def test_key_facts_from_list(self) -> None:
        result = normalize_analysis({"key_facts": ["fact1", "fact2"]})
        assert result["key_facts"] == ["fact1", "fact2"]

    def test_key_facts_fallback_from_topics(self) -> None:
        result = normalize_analysis({"topics": ["topic1"]})
        assert result["key_facts"] == ["topic1"]

    def test_needs_tool_bool(self) -> None:
        assert normalize_analysis({"needs_tool": True})["needs_tool"] is True
        assert normalize_analysis({"needs_tool": False})["needs_tool"] is False
        assert normalize_analysis({"needs_tool": "yes"})["needs_tool"] is False  # non-bool

    def test_confidence_preserved(self) -> None:
        result = normalize_analysis({"confidence": 0.85})
        assert result["confidence"] == 0.85

    def test_confidence_invalid_value(self) -> None:
        result = normalize_analysis({"confidence": "not-a-number"})
        assert result["confidence"] == 0.5


class TestStripAnalysis:
    """Tests for strip_analysis function."""

    def test_strip_single_block(self) -> None:
        content = 'Hello <analysis>{"intent": "question"}</analysis> World'
        result = strip_analysis(content)
        assert result == "Hello  World"

    def test_strip_no_block(self) -> None:
        content = "No analysis here"
        result = strip_analysis(content)
        assert result == "No analysis here"

    def test_strip_multiple_blocks(self) -> None:
        content = (
            'A <analysis>{"a": 1}</analysis> B <analysis>{"b": 2}</analysis> C'
        )
        result = strip_analysis(content)
        assert result == "A  B  C"

    def test_strip_multiline_block(self) -> None:
        content = "Start\n<analysis>\n{\"key\": \"value\"}\n</analysis>\nEnd"
        result = strip_analysis(content)
        assert result == "Start\n\nEnd"

    def test_strip_only_analysis(self) -> None:
        content = '<analysis>{"x": 1}</analysis>'
        result = strip_analysis(content)
        assert result == ""

    def test_empty_string(self) -> None:
        result = strip_analysis("")
        assert result == ""
