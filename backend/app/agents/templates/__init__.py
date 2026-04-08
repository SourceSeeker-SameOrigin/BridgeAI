"""Pre-built agent configuration templates."""

from app.agents.templates.customer_service import CUSTOMER_SERVICE_TEMPLATE
from app.agents.templates.data_analyst import DATA_ANALYST_TEMPLATE
from app.agents.templates.metaphysics_assistant import METAPHYSICS_ASSISTANT_TEMPLATE
from app.agents.templates.office_assistant import OFFICE_ASSISTANT_TEMPLATE

ALL_TEMPLATES: list[dict] = [
    CUSTOMER_SERVICE_TEMPLATE,
    DATA_ANALYST_TEMPLATE,
    OFFICE_ASSISTANT_TEMPLATE,
    METAPHYSICS_ASSISTANT_TEMPLATE,
]


def get_all_templates() -> list[dict]:
    """Return all available agent templates."""
    return [dict(t) for t in ALL_TEMPLATES]


def get_template_by_key(key: str) -> dict | None:
    """Find a template by its unique key."""
    for t in ALL_TEMPLATES:
        if t.get("key") == key:
            return dict(t)
    return None
