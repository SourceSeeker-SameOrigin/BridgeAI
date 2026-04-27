"""Plugin API endpoints — marketplace, install, execute."""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.plugin import InstalledPlugin
from app.models.user import User
from app.plugins.registry import get_plugin_registry
from app.schemas.common import ApiResponse
from app.schemas.plugin import (
    InstalledPluginResponse,
    InstalledPluginUpdate,
    PluginExecuteRequest,
    PluginInstallRequest,
    PluginMetadataResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["Plugins"])


@router.get("/marketplace", response_model=ApiResponse)
async def list_marketplace(
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """List all available plugins from the registry (marketplace)."""
    registry = get_plugin_registry()
    plugins = registry.list_plugins()
    return ApiResponse.success(data=plugins)


@router.get("/installed", response_model=ApiResponse)
async def list_installed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List plugins installed for the current tenant."""
    tenant_id = current_user.tenant_id
    if tenant_id is None:
        return ApiResponse.error(code=400, message="User has no tenant")

    result = await db.execute(
        select(InstalledPlugin)
        .where(
            InstalledPlugin.tenant_id == tenant_id,
            InstalledPlugin.is_active.is_(True),
        )
        .order_by(InstalledPlugin.created_at.desc())
    )
    rows = result.scalars().all()

    items = [
        InstalledPluginResponse(
            id=str(r.id),
            plugin_name=r.plugin_name,
            plugin_version=r.plugin_version,
            description=r.description,
            config=r.config or {},
            is_active=r.is_active,
            installed_by=str(r.installed_by) if r.installed_by else None,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
    return ApiResponse.success(data=[item.model_dump() for item in items])


@router.post("/install", response_model=ApiResponse)
async def install_plugin(
    request: PluginInstallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Install a plugin for the current tenant."""
    tenant_id = current_user.tenant_id
    if tenant_id is None:
        return ApiResponse.error(code=400, message="User has no tenant")

    registry = get_plugin_registry()

    # Validate plugin exists
    try:
        plugin = registry.get_plugin(request.plugin_name)
    except ValueError as e:
        return ApiResponse.error(code=404, message=str(e))

    # Check if already installed
    existing = await db.execute(
        select(InstalledPlugin).where(
            InstalledPlugin.tenant_id == tenant_id,
            InstalledPlugin.plugin_name == request.plugin_name,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        if row.is_active:
            return ApiResponse.error(code=409, message=f"Plugin '{request.plugin_name}' already installed")
        # Re-activate
        row.is_active = True
        row.plugin_version = plugin.version
        await db.commit()
        return ApiResponse.success(
            data={"id": str(row.id), "plugin_name": row.plugin_name},
            message="Plugin re-activated",
        )

    installed = InstalledPlugin(
        tenant_id=tenant_id,
        plugin_name=plugin.name,
        plugin_version=plugin.version,
        description=plugin.description,
        config={},
        is_active=True,
        installed_by=current_user.id,
    )
    db.add(installed)
    await db.commit()
    await db.refresh(installed)

    return ApiResponse.success(
        data={"id": str(installed.id), "plugin_name": installed.plugin_name},
        message="Plugin installed successfully",
    )


@router.put("/installed/{plugin_id}", response_model=ApiResponse)
async def update_installed_plugin(
    plugin_id: str,
    request: InstalledPluginUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Update an installed plugin (config / is_active)."""
    tenant_id = current_user.tenant_id
    if tenant_id is None:
        return ApiResponse.error(code=400, message="User has no tenant")

    result = await db.execute(
        select(InstalledPlugin).where(
            InstalledPlugin.id == plugin_id,
            InstalledPlugin.tenant_id == tenant_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return ApiResponse.error(code=404, message="Installed plugin not found")

    update_data = request.dict(exclude_unset=True)
    if "config" in update_data:
        # JSONB merge — preserve keys not in incoming update
        merged = dict(row.config or {})
        merged.update(update_data["config"] or {})
        row.config = merged
    if "is_active" in update_data:
        row.is_active = update_data["is_active"]

    await db.flush()
    return ApiResponse.success(
        data=InstalledPluginResponse(
            id=str(row.id),
            plugin_name=row.plugin_name,
            plugin_version=row.plugin_version,
            description=row.description,
            config=row.config or {},
            is_active=row.is_active,
            installed_by=str(row.installed_by) if row.installed_by else None,
            created_at=row.created_at.isoformat(),
        ),
        message="Plugin updated",
    )


@router.delete("/{plugin_id}", response_model=ApiResponse)
async def uninstall_plugin(
    plugin_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Uninstall (deactivate) a plugin."""
    tenant_id = current_user.tenant_id
    if tenant_id is None:
        return ApiResponse.error(code=400, message="User has no tenant")

    result = await db.execute(
        select(InstalledPlugin).where(
            InstalledPlugin.id == plugin_id,
            InstalledPlugin.tenant_id == tenant_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return ApiResponse.error(code=404, message="Installed plugin not found")

    row.is_active = False
    await db.commit()
    return ApiResponse.success(message="Plugin uninstalled")


@router.post("/{plugin_name}/execute", response_model=ApiResponse)
async def execute_plugin_tool(
    plugin_name: str,
    request: PluginExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Execute a plugin tool directly."""
    tenant_id = current_user.tenant_id
    if tenant_id is None:
        return ApiResponse.error(code=400, message="User has no tenant")

    # Check plugin is installed for this tenant
    installed = await db.execute(
        select(InstalledPlugin).where(
            InstalledPlugin.tenant_id == tenant_id,
            InstalledPlugin.plugin_name == plugin_name,
            InstalledPlugin.is_active.is_(True),
        )
    )
    if installed.scalar_one_or_none() is None:
        return ApiResponse.error(
            code=403,
            message=f"Plugin '{plugin_name}' is not installed. Please install it first.",
        )

    registry = get_plugin_registry()
    try:
        plugin = registry.get_plugin(plugin_name)
    except ValueError as e:
        return ApiResponse.error(code=404, message=str(e))

    result = await plugin.execute_tool(request.tool_name, request.arguments)
    if result.get("success"):
        return ApiResponse.success(data=result.get("data"))
    else:
        return ApiResponse.error(code=500, message=result.get("error", "Tool execution failed"))
