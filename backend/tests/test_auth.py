"""Tests for JWT token creation and verification (app.core.security)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Tests for password hash and verify."""

    def test_hash_and_verify(self) -> None:
        password = "MySecurePassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_is_different_each_time(self) -> None:
        password = "same-password"
        h1 = hash_password(password)
        h2 = hash_password(password)
        assert h1 != h2  # bcrypt uses random salt

    def test_verify_invalid_hash_returns_false(self) -> None:
        assert verify_password("password", "not-a-valid-hash") is False


class TestJWTTokens:
    """Tests for create_access_token and decode_access_token."""

    @patch("app.core.security.settings")
    def test_create_and_decode_token(self, mock_settings: object) -> None:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRE_MINUTES = 60

        token = create_access_token({"sub": "user-123"})
        payload = decode_access_token(token)

        assert payload["sub"] == "user-123"
        assert "exp" in payload

    @patch("app.core.security.settings")
    def test_custom_expiry(self, mock_settings: object) -> None:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRE_MINUTES = 60

        token = create_access_token(
            {"sub": "user-456"},
            expires_delta=timedelta(minutes=5),
        )
        payload = decode_access_token(token)
        assert payload["sub"] == "user-456"

    @patch("app.core.security.settings")
    def test_invalid_token_raises(self, mock_settings: object) -> None:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.token.here")
        assert exc_info.value.status_code == 401

    @patch("app.core.security.settings")
    def test_expired_token_raises(self, mock_settings: object) -> None:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRE_MINUTES = 60

        token = create_access_token(
            {"sub": "user-789"},
            expires_delta=timedelta(seconds=-10),
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401

    @patch("app.core.security.settings")
    def test_token_preserves_extra_claims(self, mock_settings: object) -> None:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRE_MINUTES = 60

        token = create_access_token({"sub": "u1", "role": "admin", "tenant_id": "t1"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"
        assert payload["tenant_id"] == "t1"

    @patch("app.core.security.settings")
    def test_wrong_secret_raises(self, mock_settings: object) -> None:
        mock_settings.JWT_SECRET = "secret-a"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRE_MINUTES = 60

        token = create_access_token({"sub": "user"})

        # Decode with different secret
        mock_settings.JWT_SECRET = "secret-b"
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401
