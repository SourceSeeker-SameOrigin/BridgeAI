"""Database MCP connector supporting PostgreSQL and MySQL."""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.mcp.connectors.base import MCPConnector, ToolDefinition, ToolResult
from app.mcp.masking import mask_dict

logger = logging.getLogger(__name__)

# Only SELECT / SHOW / DESCRIBE / EXPLAIN are allowed in read-only mode
_READONLY_PATTERN = re.compile(
    r"^\s*(SELECT|SHOW|DESCRIBE|DESC|EXPLAIN)\s",
    re.IGNORECASE,
)


class DatabaseConnector(MCPConnector):
    """MCP connector for querying MySQL / PostgreSQL databases.

    Supports read-only mode (default), query timeout, row limits,
    and automatic sensitive data masking.
    """

    name = "database"
    description = "Query MySQL or PostgreSQL databases"

    def __init__(self) -> None:
        self._pool: Any = None
        self._db_type: str = "postgresql"
        self._read_only: bool = True
        self._max_rows: int = 100
        self._timeout: int = 10
        self._config: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, config: dict[str, Any]) -> None:
        """Connect to database. Config may contain an endpoint_url or
        individual host/port/database/username/password fields."""
        self._read_only = config.get("read_only", True)
        self._max_rows = min(config.get("max_rows", 100), 1000)
        self._timeout = min(config.get("timeout_seconds", 10), 60)
        self._config = config

        # Parse connection info from endpoint_url or individual fields
        endpoint_url: str | None = config.get("endpoint_url")
        if endpoint_url:
            parsed = urlparse(endpoint_url)
            scheme = parsed.scheme.split("+")[0]  # postgresql+asyncpg -> postgresql
            self._db_type = "mysql" if "mysql" in scheme else "postgresql"
            host = parsed.hostname or "localhost"
            port = parsed.port or (3306 if self._db_type == "mysql" else 5432)
            database = (parsed.path or "").lstrip("/")
            username = parsed.username or ""
            password = parsed.password or ""
        else:
            self._db_type = config.get("db_type", "postgresql")
            host = config.get("host", "localhost")
            port = config.get("port", 5432 if self._db_type == "postgresql" else 3306)
            database = config.get("database", "")
            username = config.get("username", "")
            password = config.get("password", "")

        if self._db_type == "postgresql":
            await self._connect_pg(host, port, database, username, password)
        else:
            await self._connect_mysql(host, port, database, username, password)

    async def _connect_pg(
        self, host: str, port: int, database: str, user: str, password: str
    ) -> None:
        import asyncpg  # type: ignore

        self._pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=1,
            max_size=5,
            command_timeout=self._timeout,
        )

    async def _connect_mysql(
        self, host: str, port: int, database: str, user: str, password: str
    ) -> None:
        import aiomysql  # type: ignore

        self._pool = await aiomysql.create_pool(
            host=host,
            port=port,
            db=database,
            user=user,
            password=password,
            minsize=1,
            maxsize=5,
            connect_timeout=self._timeout,
            autocommit=True,
        )

    async def disconnect(self) -> None:
        if self._pool is None:
            return
        if self._db_type == "postgresql":
            await self._pool.close()
        else:
            self._pool.close()
            await self._pool.wait_closed()
        self._pool = None

    async def health_check(self) -> bool:
        if self._pool is None:
            return False
        try:
            if self._db_type == "postgresql":
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
            else:
                async with self._pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
            return True
        except Exception as exc:
            logger.warning("Database health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="list_tables",
                description="列出数据库中所有表",
                parameters={},
            ),
            ToolDefinition(
                name="describe_table",
                description="显示表结构（列名、类型、约束）",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "表名"},
                    },
                    "required": ["table_name"],
                },
            ),
            ToolDefinition(
                name="query",
                description="执行 SELECT 查询（只读模式，默认限制 100 行）",
                parameters={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SQL 查询语句"},
                    },
                    "required": ["sql"],
                },
            ),
            ToolDefinition(
                name="explain_query",
                description="显示查询执行计划",
                parameters={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SQL 查询语句"},
                    },
                    "required": ["sql"],
                },
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if self._pool is None:
            return ToolResult(success=False, error="数据库未连接")

        dispatch = {
            "list_tables": self._list_tables,
            "describe_table": self._describe_table,
            "query": self._execute_query,
            "explain_query": self._explain_query,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"未知工具: {tool_name}")

        try:
            result = await asyncio.wait_for(handler(arguments), timeout=self._timeout)
            # Apply data masking to the result
            masked = mask_dict(result)
            return ToolResult(success=True, data=masked)
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"查询超时（{self._timeout}秒）")
        except Exception as exc:
            logger.exception("Tool %s execution failed", tool_name)
            return ToolResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _list_tables(self, _arguments: dict[str, Any]) -> list[dict[str, str]]:
        if self._db_type == "postgresql":
            sql = (
                "SELECT table_name, table_type "
                "FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "ORDER BY table_name"
            )
            rows = await self._fetch_pg(sql)
        else:
            sql = "SHOW TABLES"
            rows = await self._fetch_mysql(sql)
        return rows

    async def _describe_table(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        table_name = arguments.get("table_name", "")
        if not table_name or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
            raise ValueError(f"非法表名: {table_name}")

        if self._db_type == "postgresql":
            sql = (
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{table_name}' "
                "ORDER BY ordinal_position"
            )
            rows = await self._fetch_pg(sql)
        else:
            sql = f"DESCRIBE `{table_name}`"
            rows = await self._fetch_mysql(sql)
        return rows

    async def _execute_query(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        sql = arguments.get("sql", "").strip()
        if not sql:
            raise ValueError("SQL 查询不能为空")

        if self._read_only and not _READONLY_PATTERN.match(sql):
            raise ValueError("只读模式下仅允许 SELECT / SHOW / DESCRIBE / EXPLAIN 语句")

        # Enforce row limit — append LIMIT if not present
        upper_sql = sql.upper()
        if "LIMIT" not in upper_sql:
            sql = f"{sql.rstrip(';')} LIMIT {self._max_rows}"

        if self._db_type == "postgresql":
            return await self._fetch_pg(sql)
        return await self._fetch_mysql(sql)

    async def _explain_query(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        sql = arguments.get("sql", "").strip()
        if not sql:
            raise ValueError("SQL 查询不能为空")

        if self._read_only and not _READONLY_PATTERN.match(sql):
            raise ValueError("只读模式下仅允许对 SELECT 查询执行 EXPLAIN")

        explain_sql = f"EXPLAIN {sql.rstrip(';')}"
        if self._db_type == "postgresql":
            return await self._fetch_pg(explain_sql)
        return await self._fetch_mysql(explain_sql)

    # ------------------------------------------------------------------
    # Internal fetch helpers
    # ------------------------------------------------------------------

    async def _fetch_pg(self, sql: str) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [dict(row) for row in rows]

    async def _fetch_mysql(self, sql: str) -> list[dict[str, Any]]:
        import aiomysql  # type: ignore

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [dict(row) for row in rows] if rows else []
