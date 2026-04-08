"""Workflow execution engine.

Parses nodes and edges into an execution graph,
executes sequentially following edges, handles conditions.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.schemas.workflow import WorkflowExecuteResponse, WorkflowStepResult

logger = logging.getLogger(__name__)


def _build_adjacency(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Build node map and adjacency list from nodes/edges."""
    node_map: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        node_map[node["id"]] = node

    adj: Dict[str, List[Dict[str, Any]]] = {}
    for edge in edges:
        source = edge["source"]
        if source not in adj:
            adj[source] = []
        adj[source].append(edge)

    return node_map, adj


def _find_start_nodes(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[str]:
    """Find nodes with no incoming edges (start nodes)."""
    targets = {e["target"] for e in edges}
    start_ids = [n["id"] for n in nodes if n["id"] not in targets]
    return start_ids if start_ids else [nodes[0]["id"]] if nodes else []


def _evaluate_condition(condition: Optional[str], last_output: str) -> bool:
    """Simple condition evaluation.

    Supports:
    - None or empty string -> True (unconditional)
    - "contains:xxx" -> check if last_output contains xxx
    - "equals:xxx" -> exact match
    - "not_empty" -> check if last_output is not empty
    - "true"/"yes" -> always true
    - "false"/"no" -> always false
    """
    if not condition:
        return True

    condition = condition.strip().lower()

    if condition in ("true", "yes"):
        return True
    if condition in ("false", "no"):
        return False
    if condition == "not_empty":
        return bool(last_output.strip())

    if condition.startswith("contains:"):
        keyword = condition[len("contains:") :]
        return keyword.lower() in last_output.lower()
    if condition.startswith("equals:"):
        expected = condition[len("equals:") :]
        return last_output.strip().lower() == expected.lower()

    # Default: treat as substring match
    return condition in last_output.lower()


async def _execute_node(
    node: Dict[str, Any],
    input_text: str,
    variables: Dict[str, Any],
    last_output: str,
    edges: Optional[List[Dict[str, Any]]] = None,
    node_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> WorkflowStepResult:
    """Execute a single workflow node."""
    node_id = node["id"]
    node_type = node["type"]
    config = node.get("config", {})

    try:
        if node_type in ("llm_call", "llm"):
            prompt = config.get("prompt", "")
            # Replace {{input}} and {{last_output}} placeholders
            effective_prompt = (
                prompt.replace("{{input}}", input_text)
                .replace("{{last_output}}", last_output)
            )
            for var_key, var_val in variables.items():
                effective_prompt = effective_prompt.replace(
                    f"{{{{{var_key}}}}}", str(var_val)
                )

            # Simulate LLM call (in production, call actual LLM provider)
            output = f"[LLM Response] Processed: {effective_prompt[:200]}"
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="success",
                output=output,
            )

        elif node_type == "tool_call":
            tool_name = config.get("tool_name", "unknown")
            tool_params = config.get("params", {})
            # Simulate tool call
            output = f"[Tool: {tool_name}] Executed with params: {tool_params}"
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="success",
                output=output,
            )

        elif node_type == "condition":
            # Condition nodes evaluate and return which branch to take
            condition_expr = config.get("condition", "")
            result = _evaluate_condition(condition_expr, last_output)
            output = "true" if result else "false"
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="success",
                output=output,
            )

        elif node_type == "loop":
            max_iterations = config.get("max_iterations", 3)
            condition = config.get("condition", "")
            loop_results: list[WorkflowStepResult] = []
            loop_ctx = dict(variables)
            for i in range(max_iterations):
                # Find edges from this node with condition="loop" to locate body node
                loop_edges = [
                    e for e in (edges or [])
                    if e.get("source") == node_id and e.get("condition") == "loop"
                ]
                if loop_edges and node_map:
                    body_node_id = loop_edges[0]["target"]
                    body_node = node_map.get(body_node_id)
                    if body_node:
                        body_result = await _execute_node(
                            body_node, input_text, loop_ctx, last_output,
                        )
                        loop_results.append(body_result)
                        loop_ctx[f"loop_{i}"] = body_result.output or ""
                        last_output = body_result.output or last_output
                # Check break condition
                if condition and _evaluate_condition(condition, last_output):
                    break
            output = json.dumps({
                "iterations": len(loop_results),
                "results": [r.output for r in loop_results],
            }, ensure_ascii=False)
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="success",
                output=output,
            )

        elif node_type == "parallel":
            # Find all outgoing edges and execute target nodes in parallel
            parallel_edges = [
                e for e in (edges or [])
                if e.get("source") == node_id
            ]
            tasks: list[Any] = []
            for edge in parallel_edges:
                target_node = (node_map or {}).get(edge["target"])
                if target_node:
                    tasks.append(
                        _execute_node(target_node, input_text, variables, last_output)
                    )
            if tasks:
                parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
                output = json.dumps({
                    "branches": len(parallel_results),
                    "results": [
                        str(r.output) if isinstance(r, WorkflowStepResult) else str(r)
                        for r in parallel_results
                    ],
                }, ensure_ascii=False)
            else:
                output = json.dumps({"branches": 0, "results": []})
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="success",
                output=output,
            )

        elif node_type == "human_input":
            prompt_text = config.get("prompt", "Please provide input")
            # In real execution, this would pause and wait for user input
            output = f"[Human Input Requested] {prompt_text}"
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="success",
                output=output,
            )

        elif node_type in ("start", "end", "wait_input", "output"):
            # Pass-through nodes that forward the last output
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="success",
                output=last_output,
            )

        else:
            return WorkflowStepResult(
                node_id=node_id,
                node_type=node_type,
                status="error",
                error=f"Unknown node type: {node_type}",
            )

    except Exception as e:
        logger.error("Node execution error [%s]: %s", node_id, e, exc_info=True)
        return WorkflowStepResult(
            node_id=node_id,
            node_type=node_type,
            status="error",
            error=str(e),
        )


async def execute_workflow(
    workflow_id: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    input_text: str,
    variables: Optional[Dict[str, Any]] = None,
) -> WorkflowExecuteResponse:
    """Execute a workflow by traversing nodes following edges.

    Uses BFS-like traversal starting from nodes with no incoming edges.
    """
    if not nodes:
        return WorkflowExecuteResponse(
            workflow_id=workflow_id,
            status="completed",
            steps=[],
            final_output="No nodes to execute",
        )

    variables = variables or {}
    node_map, adj = _build_adjacency(nodes, edges)
    start_ids = _find_start_nodes(nodes, edges)

    steps: List[WorkflowStepResult] = []
    visited: set[str] = set()
    last_output = input_text

    # Simple sequential execution following the edge chain
    queue = list(start_ids)

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        node = node_map.get(current_id)
        if node is None:
            continue

        result = await _execute_node(node, input_text, variables, last_output, edges=edges, node_map=node_map)
        steps.append(result)

        if result.status == "error":
            return WorkflowExecuteResponse(
                workflow_id=workflow_id,
                status="error",
                steps=steps,
                final_output=result.error,
            )

        last_output = result.output or last_output

        # Follow edges from current node
        outgoing = adj.get(current_id, [])
        for edge in outgoing:
            target_id = edge["target"]
            edge_condition = edge.get("condition")

            # For condition nodes, match edge condition with node output
            if node["type"] == "condition":
                if edge_condition and not _evaluate_condition(edge_condition, last_output):
                    continue

            if target_id not in visited:
                queue.append(target_id)

    has_error = any(s.status == "error" for s in steps)

    return WorkflowExecuteResponse(
        workflow_id=workflow_id,
        status="error" if has_error else "completed",
        steps=steps,
        final_output=last_output,
    )
