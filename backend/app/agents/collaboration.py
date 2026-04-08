"""
Multi-Agent Collaboration Engine.

Allows a parent Agent to delegate sub-tasks to child Agents.
Each child Agent has its own system prompt, model config, and tools.
Supports both sequential and parallel delegation.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.model_router import resolve_provider_model
from app.models.agent import Agent
from app.providers.registry import get_provider_registry

logger = logging.getLogger(__name__)

# Maximum recursion depth to prevent infinite delegation chains
_MAX_DELEGATION_DEPTH = 3

# Delegate tool definition (OpenAI function-calling format)
DELEGATE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "delegate_task",
        "description": "将子任务委派给专门的子Agent处理。当任务需要特定领域专家时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "child_agent_name": {
                    "type": "string",
                    "description": "子Agent的名称（name字段）或task_key",
                },
                "task": {
                    "type": "string",
                    "description": "需要子Agent完成的具体任务描述",
                },
                "context": {
                    "type": "string",
                    "description": "与任务相关的上下文信息（可选）",
                    "default": "",
                },
            },
            "required": ["child_agent_name", "task"],
        },
    },
}


@dataclass(frozen=True)
class DelegationResult:
    """Immutable result from a child agent delegation."""

    child_agent_id: str
    child_agent_name: str
    task: str
    success: bool
    content: str
    model_used: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_agent_id": self.child_agent_id,
            "child_agent_name": self.child_agent_name,
            "task": self.task,
            "success": self.success,
            "content": self.content,
            "model_used": self.model_used,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class AgentCollaborator:
    """Orchestrates delegation from parent agents to child agents."""

    async def delegate_task(
        self,
        parent_agent_id: str,
        child_agent_id: str,
        task_description: str,
        context: dict[str, Any],
        db: AsyncSession,
        *,
        depth: int = 0,
    ) -> DelegationResult:
        """
        Delegate a task to a specific child agent.

        1. Load child agent config from DB
        2. Build prompt with task_description + context
        3. Call LLM with child's system_prompt and model config
        4. Return result to parent

        Args:
            parent_agent_id: Parent agent's UUID.
            child_agent_id: Child agent's UUID.
            task_description: What the child agent should do.
            context: Additional context dict (e.g. conversation history snippet).
            db: Database session.
            depth: Current delegation depth (prevents infinite recursion).

        Returns:
            DelegationResult with the child's response.
        """
        if depth >= _MAX_DELEGATION_DEPTH:
            return DelegationResult(
                child_agent_id=child_agent_id,
                child_agent_name="",
                task=task_description,
                success=False,
                content="",
                error=f"已达到最大委派深度 ({_MAX_DELEGATION_DEPTH})，终止递归委派",
            )

        start_time = time.monotonic()

        # Load child agent
        result = await db.execute(
            select(Agent).where(Agent.id == child_agent_id, Agent.is_active.is_(True))
        )
        child_agent = result.scalar_one_or_none()
        if child_agent is None:
            return DelegationResult(
                child_agent_id=child_agent_id,
                child_agent_name="",
                task=task_description,
                success=False,
                content="",
                error=f"子Agent不存在或已停用: {child_agent_id}",
            )

        # Build messages
        system_content = child_agent.system_prompt or "你是一个专业的AI助手。"
        context_str = json.dumps(context, ensure_ascii=False) if context else ""
        user_content = task_description
        if context_str:
            user_content = f"任务: {task_description}\n\n上下文信息:\n{context_str}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        # Resolve model
        agent_config = child_agent.model_config_ or {}
        provider_name, model_id = resolve_provider_model(agent_config)

        # Call LLM
        try:
            registry = get_provider_registry()
            provider = registry.get_provider(provider_name)
            response = await provider.chat(
                messages=messages,
                model=model_id,
                stream=False,
                temperature=agent_config.get("temperature", 0.7),
                max_tokens=agent_config.get("max_tokens", 4096),
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return DelegationResult(
                child_agent_id=str(child_agent.id),
                child_agent_name=child_agent.name,
                task=task_description,
                success=True,
                content=response.content,
                model_used=model_id,
                tokens_in=response.token_input,
                tokens_out=response.token_output,
                duration_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                "Delegation failed: parent=%s child=%s error=%s",
                parent_agent_id, child_agent_id, e,
                exc_info=True,
            )
            return DelegationResult(
                child_agent_id=str(child_agent.id),
                child_agent_name=child_agent.name,
                task=task_description,
                success=False,
                content="",
                duration_ms=elapsed_ms,
                error=str(e),
            )

    async def delegate_by_name(
        self,
        parent_agent_id: str,
        child_name_or_key: str,
        task_description: str,
        context: dict[str, Any],
        db: AsyncSession,
        *,
        depth: int = 0,
    ) -> DelegationResult:
        """
        Delegate by child agent name or task_key (instead of UUID).

        Searches for the child among the parent's sub_agents first,
        then falls back to a global name/task_key search.
        """
        # Search among children of parent first
        result = await db.execute(
            select(Agent).where(
                Agent.parent_agent_id == parent_agent_id,
                Agent.is_active.is_(True),
                (Agent.name == child_name_or_key) | (Agent.task_key == child_name_or_key),
            )
        )
        child = result.scalar_one_or_none()

        # Fallback: global search
        if child is None:
            result = await db.execute(
                select(Agent).where(
                    Agent.is_active.is_(True),
                    (Agent.name == child_name_or_key) | (Agent.task_key == child_name_or_key),
                ).limit(1)
            )
            child = result.scalar_one_or_none()

        if child is None:
            return DelegationResult(
                child_agent_id="",
                child_agent_name=child_name_or_key,
                task=task_description,
                success=False,
                content="",
                error=f"未找到名为 '{child_name_or_key}' 的子Agent",
            )

        return await self.delegate_task(
            parent_agent_id=parent_agent_id,
            child_agent_id=str(child.id),
            task_description=task_description,
            context=context,
            db=db,
            depth=depth,
        )

    async def run_parallel_tasks(
        self,
        parent_agent_id: str,
        tasks: list[dict[str, Any]],
        db: AsyncSession,
        *,
        depth: int = 0,
    ) -> list[DelegationResult]:
        """
        Execute multiple child agent tasks in parallel.

        Args:
            parent_agent_id: Parent agent's UUID.
            tasks: List of dicts, each with:
                - child_agent_id (str, optional): UUID of the child agent.
                - child_agent_name (str, optional): Name/task_key of the child agent.
                - task_description (str): Task to delegate.
                - context (dict, optional): Additional context.
            db: Database session.
            depth: Current delegation depth.

        Returns:
            List of DelegationResult, one per task.
        """
        if not tasks:
            return []

        coroutines = []
        for task_spec in tasks:
            child_id = task_spec.get("child_agent_id")
            child_name = task_spec.get("child_agent_name", "")
            task_desc = task_spec.get("task_description", task_spec.get("task", ""))
            ctx = task_spec.get("context", {})

            if child_id:
                coroutines.append(
                    self.delegate_task(
                        parent_agent_id=parent_agent_id,
                        child_agent_id=child_id,
                        task_description=task_desc,
                        context=ctx,
                        db=db,
                        depth=depth,
                    )
                )
            elif child_name:
                coroutines.append(
                    self.delegate_by_name(
                        parent_agent_id=parent_agent_id,
                        child_name_or_key=child_name,
                        task_description=task_desc,
                        context=ctx,
                        db=db,
                        depth=depth,
                    )
                )
            else:
                coroutines.append(
                    _make_error_result(task_desc, "未指定子Agent的ID或名称")
                )

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        final: list[DelegationResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                task_desc = tasks[i].get("task_description", tasks[i].get("task", ""))
                final.append(DelegationResult(
                    child_agent_id="",
                    child_agent_name="",
                    task=task_desc,
                    success=False,
                    content="",
                    error=str(r),
                ))
            else:
                final.append(r)

        return final


async def _make_error_result(task: str, error: str) -> DelegationResult:
    """Helper to create an error DelegationResult."""
    return DelegationResult(
        child_agent_id="",
        child_agent_name="",
        task=task,
        success=False,
        content="",
        error=error,
    )


# Module-level singleton
_collaborator: AgentCollaborator | None = None


def get_collaborator() -> AgentCollaborator:
    """Get the global AgentCollaborator singleton."""
    global _collaborator
    if _collaborator is None:
        _collaborator = AgentCollaborator()
    return _collaborator
