"""Tests for app.services.billing_service — quota checking and plan limits."""

import pytest

from app.services.billing_service import PLAN_LIMITS, BillingService, billing_service
from app.schemas.billing import PlanInfo, UsageSummary


class TestPlanLimitsConfig:
    """Verify plan limits are correctly configured."""

    def test_free_plan_limits(self) -> None:
        limits = PLAN_LIMITS["free"]
        assert limits["monthly_calls"] == 100
        assert limits["monthly_tokens"] == 50000

    def test_pro_plan_limits(self) -> None:
        limits = PLAN_LIMITS["pro"]
        assert limits["monthly_calls"] == 5000
        assert limits["monthly_tokens"] == 1000000

    def test_enterprise_plan_limits(self) -> None:
        limits = PLAN_LIMITS["enterprise"]
        assert limits["monthly_calls"] == 50000
        assert limits["monthly_tokens"] == 10000000

    def test_all_plans_have_required_keys(self) -> None:
        for plan_name, limits in PLAN_LIMITS.items():
            assert "monthly_calls" in limits, f"{plan_name} missing monthly_calls"
            assert "monthly_tokens" in limits, f"{plan_name} missing monthly_tokens"

    def test_plan_limits_are_positive(self) -> None:
        for plan_name, limits in PLAN_LIMITS.items():
            assert limits["monthly_calls"] > 0
            assert limits["monthly_tokens"] > 0

    def test_pro_greater_than_free(self) -> None:
        assert PLAN_LIMITS["pro"]["monthly_calls"] > PLAN_LIMITS["free"]["monthly_calls"]
        assert PLAN_LIMITS["pro"]["monthly_tokens"] > PLAN_LIMITS["free"]["monthly_tokens"]

    def test_enterprise_greater_than_pro(self) -> None:
        assert PLAN_LIMITS["enterprise"]["monthly_calls"] > PLAN_LIMITS["pro"]["monthly_calls"]
        assert PLAN_LIMITS["enterprise"]["monthly_tokens"] > PLAN_LIMITS["pro"]["monthly_tokens"]


class TestPlanInfoModel:
    """Test PlanInfo schema behavior for quota checking logic."""

    def test_free_plan_defaults(self) -> None:
        info = PlanInfo()
        assert info.plan == "free"
        assert info.monthly_calls_limit == 100
        assert info.calls_remaining == 100

    def test_quota_remaining_calculation(self) -> None:
        info = PlanInfo(
            plan="pro",
            monthly_calls_limit=5000,
            monthly_tokens_limit=1000000,
            monthly_calls_used=4500,
            monthly_tokens_used=500000,
            calls_remaining=500,
            tokens_remaining=500000,
        )
        assert info.calls_remaining == 500
        assert info.tokens_remaining == 500000

    def test_quota_exceeded_scenario(self) -> None:
        info = PlanInfo(
            plan="free",
            monthly_calls_limit=100,
            monthly_tokens_limit=50000,
            monthly_calls_used=100,
            monthly_tokens_used=50000,
            calls_remaining=0,
            tokens_remaining=0,
        )
        assert info.calls_remaining == 0
        assert info.tokens_remaining == 0


class TestUsageSummaryModel:
    """Test UsageSummary schema."""

    def test_defaults_are_zero(self) -> None:
        summary = UsageSummary()
        assert summary.monthly_calls == 0
        assert summary.monthly_tokens == 0
        assert summary.chat_calls == 0
        assert summary.mcp_calls == 0
        assert summary.rag_calls == 0

    def test_populated_summary(self) -> None:
        summary = UsageSummary(
            monthly_calls=150,
            monthly_tokens=30000,
            chat_calls=100,
            mcp_calls=30,
            rag_calls=20,
            chat_tokens=30000,
        )
        assert summary.monthly_calls == 150
        assert summary.chat_tokens == 30000


class TestBillingServiceSingleton:
    """Test that the global singleton is properly initialized."""

    def test_singleton_exists(self) -> None:
        assert billing_service is not None
        assert isinstance(billing_service, BillingService)


class TestQuotaCheckLogic:
    """Test the quota check logic using PlanInfo model directly.

    The actual check_quota method requires a DB session, but
    we can validate the logic pattern it uses.
    """

    @pytest.mark.parametrize(
        "plan,calls_used,tokens_used,expected_allowed",
        [
            ("free", 0, 0, True),
            ("free", 50, 25000, True),
            ("free", 99, 49999, True),
            ("free", 100, 50000, False),
            ("free", 101, 0, False),
            ("free", 0, 50001, False),
            ("pro", 0, 0, True),
            ("pro", 4999, 999999, True),
            ("pro", 5000, 1000000, False),
            ("enterprise", 49999, 9999999, True),
            ("enterprise", 50000, 10000000, False),
        ],
    )
    def test_quota_check_scenarios(
        self,
        plan: str,
        calls_used: int,
        tokens_used: int,
        expected_allowed: bool,
    ) -> None:
        limits = PLAN_LIMITS[plan]
        calls_remaining = max(0, limits["monthly_calls"] - calls_used)
        tokens_remaining = max(0, limits["monthly_tokens"] - tokens_used)

        is_allowed = calls_remaining > 0 and tokens_remaining > 0
        assert is_allowed == expected_allowed, (
            f"Plan={plan}, calls_used={calls_used}, tokens_used={tokens_used}: "
            f"expected {expected_allowed}, got {is_allowed}"
        )

    def test_unknown_plan_falls_back_to_free(self) -> None:
        limits = PLAN_LIMITS.get("unknown_plan", PLAN_LIMITS["free"])
        assert limits["monthly_calls"] == 100
        assert limits["monthly_tokens"] == 50000
