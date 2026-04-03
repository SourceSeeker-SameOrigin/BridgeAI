# 架构设计文档

## 总体架构

BridgeAI 采用分层架构设计，后端基于 FastAPI 构建，前端使用 React + TypeScript。

```
┌─────────────────────────────────────────────────────────────────────┐
│                         渠道层 (Channel Layer)                      │
│           企业微信 │ 钉钉 │ 飞书 │ Web │ API                        │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                       API 网关层 (Gateway)                          │
│    认证(JWT/API Key) │ 租户隔离 │ 安全头 │ CORS │ 异常处理          │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                       API 路由层 (api/v1/)                          │
│   auth │ chat │ agents │ mcp │ knowledge │ plugins │ channels      │
│                      参数校验 + 响应封装                             │
└──────────┬──────────────────────┬────────────────────┬──────────────┘
           │                      │                    │
┌──────────▼──────────┐ ┌────────▼────────┐ ┌────────▼──────────┐
│  业务逻辑层          │ │  Agent 引擎      │ │  MCP 网关          │
│  services/           │ │  engine/         │ │  mcp/              │
│                      │ │  agents/         │ │  connectors/       │
│  chat_service        │ │                  │ │                    │
│  agent_service       │ │  LangGraph       │ │  MySQL │ HTTP      │
│  auth_service        │ │  6 阶段管线      │ │  飞书  │ ...       │
│  ...                 │ │                  │ │                    │
└──────────┬──────────┘ └────────┬────────┘ └────────┬──────────┘
           │                      │                    │
           ├──────────────────────┼────────────────────┤
           │                      │                    │
┌──────────▼──────────────────────▼────────────────────▼──────────────┐
│                         数据层                                      │
│   PostgreSQL 16 (pgvector) │ Redis 7 │ MinIO                       │
│   ORM 模型 │ 向量存储       │ 缓存     │ 文件存储                    │
└────────────────────────────────────────────────────────────────────┘
```

## Agent 引擎 -- LangGraph 6 阶段管线

对话处理的核心是基于 LangGraph 状态机实现的 6 阶段管线。

### 管线流程

```
用户消息
   │
   ▼
Stage 1: 意图理解 (understand_intent)
   │  关键词预分类：debugging / generation / question / general
   │  利用上一轮分析结果加速判断
   ▼
Stage 2: 上下文增强 (enrich_context)
   │  四层 Prompt 融合：
   │    Layer 1: BridgeAI 基础行为
   │    Layer 2: Agent 人设 + RAG 上下文
   │    Layer 3: Few-shot 高评分案例
   │    Layer 4: 分析指令（让 LLM 输出 <analysis> JSON）
   ▼
Stage 3: 工具选择 (select_tools)
   │  校验 MCP 工具定义，过滤无效工具
   ▼
Stage 4: 模型路由 (route_model)
   │  3 层路由决策：
   │    Layer 1: Agent 默认模型
   │    Layer 2: 基于意图/复杂度调整
   │    Layer 3: 用户等级限制（预留）
   ▼
Stage 5: 执行 (由 chat_service 驱动)
   │  LLM 调用（经熔断器）
   │  工具调用循环（最多 5 轮）
   │  流式输出
   ▼
Stage 6: 结果整合
   │  解析 <analysis> JSON
   │  剥离分析内容，返回干净回复
   │  持久化消息和元数据
   ▼
返回给用户
```

### 状态定义

管线中的状态通过 `PipelineState` (TypedDict) 在各阶段之间传递：

- **输入状态** -- `user_message`, `history_messages`, `agent_config`, `knowledge_base_id` 等
- **Stage 1 输出** -- `intent`, `intent_confidence`
- **Stage 2 输出** -- `rag_context`, `optimized_messages`
- **Stage 3 输出** -- `available_tools`, `mcp_connector_ids`
- **Stage 4 输出** -- `provider_name`, `model_id`, `temperature`, `max_tokens`

### 熔断降级

`CircuitBreaker` 组件保障模型调用可用性：

- 单个模型连续失败 N 次后自动熔断
- 熔断后自动切换降级链中的下一个模型
- 熔断冷却时间后自动恢复为半开状态
- 所有模型都不可用时抛出明确异常

## MCP 网关

MCP (Model Context Protocol) 网关负责管理外部工具连接。

### 架构

```
Agent Pipeline
     │
     ▼
┌─── MCP Gateway ─────────────────────────┐
│                                          │
│  register_connector()  -- 注册连接器      │
│  execute_tool()        -- 执行工具        │
│  list_tools()          -- 列出工具        │
│  health_check()        -- 健康检查        │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Database │  │ HTTP API │  │  飞书   │ │
│  │Connector │  │Connector │  │Connector│ │
│  └──────────┘  └──────────┘  └────────┘ │
│                                          │
│  安全层：                                 │
│    - 参数校验                             │
│    - 输出脱敏（手机号/身份证/银行卡/邮箱）  │
│    - 审计日志记录                          │
│    - 执行耗时统计                          │
└──────────────────────────────────────────┘
```

### 连接器基类

所有 MCP 连接器实现 `MCPConnector` 抽象基类：

```python
class MCPConnector(ABC):
    async def connect(self, config: dict) -> None
    async def disconnect(self) -> None
    async def list_tools(self) -> list[ToolDefinition]
    async def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult
    async def health_check(self) -> bool
```

## RAG 引擎

知识库检索增强生成 (RAG) 引擎处理文档的全生命周期。

### 处理流程

```
文档上传                          查询
   │                               │
   ▼                               ▼
解析 (Parser)                  Query Embedding
   │  PDF / DOCX / MD / TXT        │
   ▼                               ▼
切分 (Chunker)                 pgvector 余弦相似度搜索
   │  chunk_size + overlap          │
   ▼                               ▼
向量化 (Embedding)             Top-K 结果
   │  批量处理，每批 100             │
   ▼                               ▼
存储 (pgvector)                注入 Agent Prompt
```

### 组件

- **Parsers** -- 解析器工厂模式，根据文件扩展名自动选择
- **Chunker** -- 可配置的文本切分器，支持 chunk_size 和 overlap
- **Embeddings** -- 支持 API 调用和本地 TF-IDF 两种模式
- **Engine** -- RAG 编排器，协调解析 -> 切分 -> 向量化 -> 存储 -> 检索

## 插件系统

行业插件以标准化接口扩展 Agent 能力。

### 插件接口

```python
class PluginBase(ABC):
    name: str
    display_name: str
    category: str  # ecommerce / finance / legal

    def get_tools(self) -> list[PluginTool]
    async def execute_tool(self, tool_name: str, arguments: dict) -> dict
    def get_prompt_templates(self) -> list[PluginPromptTemplate]
    def get_system_prompt_extension(self) -> str
```

### 插件发现

- `PluginLoader` 扫描 `plugins/industries/` 目录
- 自动发现并注册所有 `PluginBase` 子类
- 支持运行时启用/禁用

## 渠道接入

统一的渠道管理器连接 IM 平台与 Agent 管线。

```
企业微信/钉钉 Webhook
        │
        ▼
  ChannelManager
        │
        ├─ 验签 + 消息解析
        ├─ 路由到 chat_service
        ├─ 获取 Agent 回复
        └─ 通过原渠道回复用户
```

## 多租户隔离

采用共享数据库、行级隔离的多租户方案：

- **TenantMiddleware** -- 从请求头提取 `X-Tenant-Id`
- **JWT 优先** -- 认证用户的 `tenant_id` 优先于请求头
- **数据隔离** -- 所有业务表包含 `tenant_id` 字段

## 安全设计

### 认证

- **JWT** -- 用于 Web 端登录，24 小时有效期
- **API Key** -- 用于第三方集成，支持 hash 存储和权限范围

### 数据安全

- 密码使用 bcrypt (rounds=12) 哈希
- API Key 只存储 hash 值
- MCP 连接器凭据加密存储
- SQL 注入防护（SQLAlchemy ORM 参数化查询）

### HTTP 安全头

通过 `SecurityHeadersMiddleware` 添加：

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (HTTPS)
- `Content-Security-Policy`
- `Referrer-Policy`
- `Permissions-Policy`

## 数据库设计

使用 PostgreSQL 16 + pgvector 扩展：

### 核心表

| 表名 | 说明 |
|------|------|
| `users` | 用户表 |
| `agents` | Agent 配置表 |
| `conversations` | 会话表 |
| `messages` | 消息表（含 intent/emotion 元数据） |
| `mcp_connectors` | MCP 连接器配置 |
| `mcp_audit_logs` | MCP 调用审计日志 |
| `knowledge_bases` | 知识库配置 |
| `knowledge_documents` | 知识库文档 |
| `knowledge_chunks` | 文档切片（含 vector 列） |
| `plugins` | 插件配置 |
| `api_keys` | API Key 管理 |
| `audit_logs` | 统一审计日志 |
| `usage_records` | 用量计费记录 |
| `message_ratings` | 消息评分 |

### 技术选型理由

- **PostgreSQL + pgvector** 而非 MySQL + Milvus -- 一个数据库解决关系型 + 向量检索，运维成本低
- **LangGraph** 而非 LangChain Agent -- 基于状态机，流程可控，支持条件分支和循环
- **Zustand** 而非 Redux -- 代码量少 80%，TypeScript 友好
