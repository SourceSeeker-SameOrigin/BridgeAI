"""
Seed data script for BridgeAI.

Creates demo tenant, admin user, sample agents (from templates),
sample MCP connector, and sample knowledge base.

Usage:
    cd backend && source .venv/bin/activate
    python -m scripts.seed_data
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, engine
from app.models.base import Base

# Import models so they are registered with SQLAlchemy
from app.models import user as _user_mod, agent as _agent_mod, mcp as _mcp_mod, knowledge as _kb_mod  # noqa: F401
from app.models.user import Tenant, User
from app.models.agent import Agent
from app.models.mcp import McpConnector
from app.models.knowledge import KnowledgeBase
from app.agents.templates import get_all_templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed configuration
# ---------------------------------------------------------------------------
DEMO_TENANT_NAME = "BridgeAI Demo"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_EMAIL = "1178672658@qq.com"


async def _hash_password(password: str) -> str:
    """Hash password using passlib (same as app.core.security)."""
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.hash(password)
    except ImportError:
        # Fallback: store as-is (not recommended for production)
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()


async def seed_tenant(db: AsyncSession) -> str:
    """Create demo tenant if not exists, return tenant_id."""
    result = await db.execute(
        select(Tenant).where(Tenant.name == DEMO_TENANT_NAME).limit(1)
    )
    tenant = result.scalar_one_or_none()
    if tenant:
        logger.info("Tenant '%s' already exists: %s", DEMO_TENANT_NAME, tenant.id)
        return str(tenant.id)

    tenant_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name=DEMO_TENANT_NAME, slug="bridgeai-demo")
    db.add(tenant)
    await db.flush()
    logger.info("Created tenant '%s': %s", DEMO_TENANT_NAME, tenant_id)
    return tenant_id


async def seed_admin_user(db: AsyncSession, tenant_id: str) -> str:
    """Create admin user if not exists, return user_id."""
    result = await db.execute(
        select(User).where(User.username == ADMIN_USERNAME).limit(1)
    )
    user = result.scalar_one_or_none()
    if user:
        logger.info("Admin user '%s' already exists: %s", ADMIN_USERNAME, user.id)
        return str(user.id)

    hashed = await _hash_password(ADMIN_PASSWORD)
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=ADMIN_USERNAME,
        email=ADMIN_EMAIL,
        hashed_password=hashed,
        tenant_id=tenant_id,
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Created admin user '%s': %s", ADMIN_USERNAME, user_id)
    return user_id


async def seed_agents(db: AsyncSession, tenant_id: str) -> list[str]:
    """Create sample agents from templates."""
    templates = get_all_templates()
    agent_ids: list[str] = []

    for tpl in templates:
        name = tpl["name"]
        result = await db.execute(
            select(Agent).where(Agent.name == name, Agent.tenant_id == tenant_id).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Agent '%s' already exists: %s", name, existing.id)
            agent_ids.append(str(existing.id))
            continue

        agent_id = str(uuid.uuid4())
        agent = Agent(
            id=agent_id,
            name=name,
            description=tpl.get("description", ""),
            system_prompt=tpl.get("system_prompt", ""),
            model_config_=tpl.get("model_config", {}),
            tenant_id=tenant_id,
            is_active=True,
        )
        db.add(agent)
        await db.flush()
        agent_ids.append(agent_id)
        logger.info("Created agent '%s': %s", name, agent_id)

    return agent_ids


async def seed_mcp_connector(db: AsyncSession, tenant_id: str) -> str:
    """Create a sample MCP connector."""
    sample_name = "示例 HTTP 连接器"
    result = await db.execute(
        select(McpConnector).where(
            McpConnector.name == sample_name,
            McpConnector.tenant_id == tenant_id,
        ).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("MCP connector '%s' already exists: %s", sample_name, existing.id)
        return str(existing.id)

    connector_id = str(uuid.uuid4())
    connector = McpConnector(
        id=connector_id,
        name=sample_name,
        description="演示用的 HTTP 类型 MCP 连接器",
        connector_type="http",
        endpoint_url="https://httpbin.org",
        auth_config={"timeout": 30},
        tenant_id=tenant_id,
    )
    db.add(connector)
    await db.flush()
    logger.info("Created MCP connector '%s': %s", sample_name, connector_id)
    return connector_id


async def seed_knowledge_base(db: AsyncSession, tenant_id: str) -> str:
    """Create a sample knowledge base."""
    sample_name = "示例知识库"
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.name == sample_name,
            KnowledgeBase.tenant_id == tenant_id,
        ).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("Knowledge base '%s' already exists: %s", sample_name, existing.id)
        return str(existing.id)

    kb_id = str(uuid.uuid4())
    kb = KnowledgeBase(
        id=kb_id,
        name=sample_name,
        description="包含示例文档的演示知识库",
        tenant_id=tenant_id,
    )
    db.add(kb)
    await db.flush()
    logger.info("Created knowledge base '%s': %s", sample_name, kb_id)
    return kb_id


async def main() -> None:
    """Run all seed operations."""
    logger.info("Starting BridgeAI seed data...")

    async with async_session_factory() as db:
        try:
            tenant_id = await seed_tenant(db)
            await seed_admin_user(db, tenant_id)
            await seed_agents(db, tenant_id)
            await seed_mcp_connector(db, tenant_id)
            await seed_knowledge_base(db, tenant_id)
            await db.commit()
            logger.info("Seed data complete.")
        except Exception:
            await db.rollback()
            logger.exception("Seed data failed, rolling back.")
            raise


if __name__ == "__main__":
    asyncio.run(main())
