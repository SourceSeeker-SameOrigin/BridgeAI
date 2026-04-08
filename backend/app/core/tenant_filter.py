"""
Multi-tenant automatic SQL filtering safety net.

Uses asyncio ContextVar to track the current tenant_id per request,
and a SQLAlchemy ``do_orm_execute`` event listener to WARN when a
query on a tenant-aware table is missing a tenant_id filter.

This does NOT auto-inject WHERE clauses (which can break complex joins),
but instead logs warnings so developers catch missing filters early.
"""

import logging
from contextvars import ContextVar
from typing import Optional

from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ContextVar is async-safe and works correctly with asyncio tasks
_current_tenant_id: ContextVar[Optional[str]] = ContextVar("current_tenant_id", default=None)

# Tables that require tenant_id filtering
_TENANT_AWARE_TABLES = frozenset({
    "agents",
    "agent_memories",
    "knowledge_bases",
    "knowledge_documents",
    "knowledge_chunks",
    "mcp_connectors",
    "mcp_audit_logs",
    "conversations",
    "messages",
    "workflows",
    "plugins",
})


def set_current_tenant(tenant_id: str | None) -> None:
    """Set the current tenant_id for the active async context."""
    _current_tenant_id.set(tenant_id)


def get_current_tenant() -> str | None:
    """Get the current tenant_id from the active async context."""
    return _current_tenant_id.get()


def setup_tenant_filter(engine: object) -> None:
    """Register a SQLAlchemy event listener that warns on unfiltered tenant queries.

    This is a safety net -- all API endpoints should still explicitly filter
    by tenant_id. The listener only logs warnings to help catch regressions.
    """

    @event.listens_for(Session, "do_orm_execute")
    def _check_tenant_filter(orm_execute_state: object) -> None:
        if not orm_execute_state.is_select:  # type: ignore[attr-defined]
            return

        tenant_id = get_current_tenant()
        if not tenant_id:
            # No tenant context (public endpoints, system tasks)
            return

        # Inspect the compiled SQL string for tenant_id references
        try:
            statement = orm_execute_state.statement  # type: ignore[attr-defined]
            compiled = statement.compile(compile_kwargs={"literal_binds": False})
            sql_text = str(compiled)

            # Check if any tenant-aware table is referenced without tenant_id filter
            for table_name in _TENANT_AWARE_TABLES:
                if table_name in sql_text and "tenant_id" not in sql_text:
                    logger.warning(
                        "TENANT_FILTER_MISSING: Query on '%s' without tenant_id filter. "
                        "Current tenant: %s. SQL: %.200s",
                        table_name,
                        tenant_id,
                        sql_text,
                    )
                    break  # One warning per query is enough
        except Exception:
            # Don't let the safety net break actual queries
            pass
