"""Tests for app.mcp.masking."""

import pytest

from app.mcp.masking import mask_dict, mask_sensitive_data


class TestMaskSensitiveData:
    """Tests for mask_sensitive_data function."""

    def test_mask_phone_number(self) -> None:
        text = "联系电话: 13812345678"
        result = mask_sensitive_data(text)
        assert "13812345678" not in result
        assert "138****5678" in result

    def test_mask_multiple_phones(self) -> None:
        text = "电话1: 13912345678, 电话2: 15887654321"
        result = mask_sensitive_data(text)
        assert "13912345678" not in result
        assert "15887654321" not in result
        assert "139****5678" in result
        assert "158****4321" in result

    def test_mask_email(self) -> None:
        text = "邮箱: user@example.com"
        result = mask_sensitive_data(text)
        assert "user@example.com" not in result
        assert "***邮箱***" in result

    def test_mask_id_card(self) -> None:
        text = "身份证: 110101199001011234"
        result = mask_sensitive_data(text)
        assert "110101199001011234" not in result

    def test_no_sensitive_data(self) -> None:
        text = "这是一段普通文本，没有敏感信息。"
        result = mask_sensitive_data(text)
        assert result == text

    def test_empty_string(self) -> None:
        result = mask_sensitive_data("")
        assert result == ""

    def test_non_string_input(self) -> None:
        # Should return the input as-is for non-strings
        assert mask_sensitive_data(123) == 123  # type: ignore[arg-type]
        assert mask_sensitive_data(None) is None  # type: ignore[arg-type]


class TestMaskDict:
    """Tests for mask_dict function."""

    def test_mask_string_values_in_dict(self) -> None:
        data = {"phone": "我的手机号是13812345678", "name": "张三"}
        result = mask_dict(data)
        assert "13812345678" not in result["phone"]
        assert result["name"] == "张三"

    def test_mask_nested_dict(self) -> None:
        data = {"user": {"email": "test@example.com", "age": 25}}
        result = mask_dict(data)
        assert "test@example.com" not in result["user"]["email"]
        assert result["user"]["age"] == 25

    def test_mask_list(self) -> None:
        data = ["联系: 13812345678", "普通文本"]
        result = mask_dict(data)
        assert "13812345678" not in result[0]
        assert result[1] == "普通文本"

    def test_mask_complex_nested(self) -> None:
        data = {
            "results": [
                {"content": "电话: 15912345678"},
                {"content": "OK"},
            ]
        }
        result = mask_dict(data)
        assert "15912345678" not in result["results"][0]["content"]
        assert result["results"][1]["content"] == "OK"

    def test_non_string_non_container(self) -> None:
        assert mask_dict(42) == 42
        assert mask_dict(3.14) == 3.14
        assert mask_dict(True) is True

    def test_empty_containers(self) -> None:
        assert mask_dict({}) == {}
        assert mask_dict([]) == []
