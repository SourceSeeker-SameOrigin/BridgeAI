"""Shared pytest fixtures for BridgeAI backend tests."""

import pytest


@pytest.fixture
def jwt_secret() -> str:
    return "test-secret-key-for-unit-tests"


@pytest.fixture
def jwt_algorithm() -> str:
    return "HS256"
