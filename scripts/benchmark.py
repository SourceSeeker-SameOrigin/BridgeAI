"""BridgeAI performance benchmark using httpx.

Usage:
    python scripts/benchmark.py [--base-url http://localhost:8000] [--concurrency 10] [--requests 100]
"""

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine

import httpx


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    total_requests: int
    successful: int
    failed: int
    elapsed_seconds: float
    latencies: tuple[float, ...]

    @property
    def requests_per_second(self) -> float:
        if self.elapsed_seconds == 0:
            return 0.0
        return self.successful / self.elapsed_seconds

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed / self.total_requests

    @property
    def p50(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_l = sorted(self.latencies)
        idx = int(len(sorted_l) * 0.50)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    @property
    def p95(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_l = sorted(self.latencies)
        idx = int(len(sorted_l) * 0.95)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    @property
    def p99(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_l = sorted(self.latencies)
        idx = int(len(sorted_l) * 0.99)
        return sorted_l[min(idx, len(sorted_l) - 1)]


def format_result(result: BenchmarkResult) -> str:
    lines = [
        f"  [{result.name}]",
        f"    Total: {result.total_requests}  |  OK: {result.successful}  |  Failed: {result.failed}",
        f"    RPS: {result.requests_per_second:.1f}  |  Error rate: {result.error_rate:.1%}",
    ]
    if result.latencies:
        lines.append(
            f"    Latency  p50: {result.p50 * 1000:.1f}ms  |  "
            f"p95: {result.p95 * 1000:.1f}ms  |  p99: {result.p99 * 1000:.1f}ms"
        )
    return "\n".join(lines)


async def _run_scenario(
    name: str,
    func: Callable[[httpx.AsyncClient], Coroutine],
    client: httpx.AsyncClient,
    num_requests: int,
    concurrency: int,
) -> BenchmarkResult:
    """Run a benchmark scenario with controlled concurrency."""
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    success_count = 0
    fail_count = 0

    async def _task() -> None:
        nonlocal success_count, fail_count
        async with sem:
            start = time.perf_counter()
            try:
                await func(client)
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)
                success_count += 1
            except Exception:
                fail_count += 1

    wall_start = time.perf_counter()
    await asyncio.gather(*[_task() for _ in range(num_requests)])
    wall_elapsed = time.perf_counter() - wall_start

    return BenchmarkResult(
        name=name,
        total_requests=num_requests,
        successful=success_count,
        failed=fail_count,
        elapsed_seconds=wall_elapsed,
        latencies=tuple(latencies),
    )


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

_TEST_USER = {"username": "bench_user", "password": "BenchPass123!"}
_auth_token: str = ""


async def scenario_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/system/health")
    resp.raise_for_status()


async def scenario_register_or_login(client: httpx.AsyncClient) -> None:
    global _auth_token
    # Try login first
    resp = await client.post("/api/v1/auth/login", json=_TEST_USER)
    if resp.status_code == 200:
        _auth_token = resp.json().get("access_token", "")
        return
    # If login fails, try register
    resp = await client.post(
        "/api/v1/auth/register",
        json={**_TEST_USER, "email": "bench@test.local", "nickname": "bench"},
    )
    if resp.status_code in (200, 201):
        _auth_token = resp.json().get("access_token", "")


async def scenario_list_agents(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {_auth_token}"},
    )
    resp.raise_for_status()


async def scenario_root(client: httpx.AsyncClient) -> None:
    resp = await client.get("/")
    resp.raise_for_status()


async def benchmark(base_url: str, concurrency: int, num_requests: int) -> None:
    print(f"\nBridgeAI Performance Benchmark")
    print(f"  Target: {base_url}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Requests per scenario: {num_requests}")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Warm up: register/login
        await scenario_register_or_login(client)

        scenarios = [
            ("Health Check", scenario_health),
            ("Root Endpoint", scenario_root),
        ]

        # Only run authenticated scenarios if we have a token
        if _auth_token:
            scenarios.append(("List Agents", scenario_list_agents))

        for name, func in scenarios:
            result = await _run_scenario(name, func, client, num_requests, concurrency)
            print(format_result(result))
            print()

    print("=" * 60)
    print("Benchmark complete.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="BridgeAI performance benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent requests")
    parser.add_argument("--requests", type=int, default=100, help="Total requests per scenario")
    args = parser.parse_args()

    asyncio.run(benchmark(args.base_url, args.concurrency, args.requests))


if __name__ == "__main__":
    main()
