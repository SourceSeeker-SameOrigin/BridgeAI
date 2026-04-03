# API 接口文档

BridgeAI 后端 API 基于 FastAPI 构建，所有接口均以 `/api/v1` 为前缀。

<p align="center">
  <img src="assets/diagrams/api-overview.svg" width="800" alt="API全景" />
</p>

## 通用说明

### 认证方式

支持两种认证方式（二选一）：

1. **JWT Bearer Token** -- 通过登录获取
   ```
   Authorization: Bearer <token>
   ```

2. **API Key** -- 通过管理后台创建
   ```
   X-API-Key: <api_key>
   ```

### 多租户

需要在请求头中携带租户 ID：
```
X-Tenant-Id: <tenant_id>
```

### 统一响应格式

所有接口返回统一的 JSON 格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

错误响应：
```json
{
  "code": 400,
  "message": "错误描述",
  "data": null
}
```

### 分页响应

列表接口统一使用分页格式：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "size": 20,
    "pages": 5
  }
}
```

分页参数：
- `page` -- 页码，从 1 开始，默认 1
- `size` -- 每页数量，默认 20，最大 100

---

## 认证模块 `/auth`

### POST `/api/v1/auth/register` -- 用户注册

**无需认证**

请求体：
```json
{
  "username": "admin",
  "email": "1178672658@qq.com",
  "password": "your_password"
}
```

响应：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "uuid",
    "username": "admin",
    "email": "1178672658@qq.com",
    "role": "user",
    "tenant_id": "uuid"
  }
}
```

### POST `/api/v1/auth/login` -- 用户登录

**无需认证**

请求体：
```json
{
  "username": "admin",
  "password": "your_password"
}
```

响应：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "user": {
      "id": "uuid",
      "username": "admin",
      "role": "user"
    }
  }
}
```

---

## 对话模块 `/chat`

<p align="center">
  <img src="assets/diagrams/chat-sequence.svg" width="800" alt="聊天请求时序" />
</p>

### POST `/api/v1/chat/completions` -- 发送消息

**需要认证**

请求体：
```json
{
  "message": "你好，请帮我分析一下销售数据",
  "agent_id": "uuid (可选)",
  "conversation_id": "uuid (可选，不传则创建新会话)",
  "model": "deepseek-chat (可选)",
  "temperature": 0.7,
  "max_tokens": 4096,
  "stream": true,
  "knowledge_base_id": "uuid (可选)"
}
```

#### 非流式响应 (`stream: false`)

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "conversation_id": "uuid",
    "content": "AI 回复内容",
    "model_used": "deepseek-chat",
    "token_input": 150,
    "token_output": 300
  }
}
```

#### 流式响应 (`stream: true`)

返回 SSE (Server-Sent Events) 流，事件类型：

| 事件类型 | 说明 | 数据格式 |
|---------|------|---------|
| `meta` | 首个事件，包含会话 ID | `{"type": "meta", "conversation_id": "uuid"}` |
| `content` | 文本块 | `{"type": "content", "content": "文字"}` |
| `tool_call` | 工具调用 | `{"type": "tool_call", "tool_name": "...", "arguments": {...}}` |
| `tool_result` | 工具结果 | `{"type": "tool_result", "tool_name": "...", "result": {...}}` |
| `analysis` | 上下文分析 | `{"type": "analysis", "intent": "...", "emotion": "..."}` |
| `error` | 错误 | `{"type": "error", "content": "错误信息"}` |
| `done` | 流结束 | `{"type": "done"}` |

### POST `/api/v1/chat/messages/{message_id}/rate` -- 消息评分

**需要认证**

请求体：
```json
{
  "rating": 5,
  "feedback": "回答非常准确 (可选)"
}
```

> 评分范围 1-5，评分 >= 4 的对话会自动进入 Few-shot 学习池。

---

## Agent 管理 `/agents`

### POST `/api/v1/agents` -- 创建 Agent

请求体：
```json
{
  "name": "客服助手",
  "description": "智能客服机器人",
  "system_prompt": "你是一个专业的客服助手...",
  "model_config": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "tools": ["connector-uuid-1", "connector-uuid-2"],
  "knowledge_base_id": "uuid (可选)",
  "plugins": ["ecommerce"]
}
```

### GET `/api/v1/agents` -- Agent 列表

查询参数：`page`, `size`

### GET `/api/v1/agents/{agent_id}` -- Agent 详情

### PUT `/api/v1/agents/{agent_id}` -- 更新 Agent

请求体同创建，所有字段可选。

### DELETE `/api/v1/agents/{agent_id}` -- 删除 Agent

---

## MCP 连接器 `/mcp`

### POST `/api/v1/mcp` -- 创建连接器

请求体：
```json
{
  "name": "业务数据库",
  "description": "公司 MySQL 主库",
  "connector_type": "mysql",
  "endpoint_url": "mysql://user:pass@host:3306/dbname",
  "auth_config": {},
  "config": {},
  "capabilities": ["query", "execute"]
}
```

支持的 `connector_type`：
- `mysql` / `postgresql` / `database` -- 数据库连接器
- `http_api` / `http` -- 通用 HTTP API 连接器
- `feishu` / `lark` -- 飞书连接器

### GET `/api/v1/mcp` -- 连接器列表

### GET `/api/v1/mcp/{connector_id}` -- 连接器详情

### PUT `/api/v1/mcp/{connector_id}` -- 更新连接器

### DELETE `/api/v1/mcp/{connector_id}` -- 删除连接器（软删除）

### POST `/api/v1/mcp/{connector_id}/test` -- 测试连接

响应：
```json
{
  "code": 200,
  "message": "连接测试成功",
  "data": { "healthy": true }
}
```

### GET `/api/v1/mcp/{connector_id}/tools` -- 获取工具列表

响应：
```json
{
  "code": 200,
  "data": [
    {
      "name": "query_table",
      "description": "查询数据库表",
      "parameters": { ... }
    }
  ]
}
```

### POST `/api/v1/mcp/{connector_id}/execute` -- 执行工具

请求体：
```json
{
  "tool_name": "query_table",
  "arguments": {
    "sql": "SELECT * FROM orders LIMIT 10"
  }
}
```

响应：
```json
{
  "code": 200,
  "data": {
    "success": true,
    "data": [...],
    "error": null,
    "duration_ms": 45
  }
}
```

---

## 知识库 `/knowledge`

### POST `/api/v1/knowledge` -- 创建知识库

请求体：
```json
{
  "name": "产品文档",
  "description": "公司产品使用手册",
  "embedding_model": "text-embedding-ada-002",
  "chunk_size": 500,
  "chunk_overlap": 50
}
```

### GET `/api/v1/knowledge` -- 知识库列表

### GET `/api/v1/knowledge/{kb_id}` -- 知识库详情

### PUT `/api/v1/knowledge/{kb_id}` -- 更新知识库

### DELETE `/api/v1/knowledge/{kb_id}` -- 删除知识库

### POST `/api/v1/knowledge/{kb_id}/documents` -- 上传文档

**Content-Type: multipart/form-data**

表单字段：
- `file` -- 文档文件（支持 PDF、DOCX、MD、TXT）

上传后文档会在后台异步解析、切分、向量化。通过文档详情接口查询处理状态。

### GET `/api/v1/knowledge/{kb_id}/documents` -- 文档列表

### DELETE `/api/v1/knowledge/{kb_id}/documents/{doc_id}` -- 删除文档

### POST `/api/v1/knowledge/{kb_id}/search` -- 语义搜索

请求体：
```json
{
  "query": "如何配置单点登录？",
  "top_k": 5
}
```

响应：
```json
{
  "code": 200,
  "data": {
    "query": "如何配置单点登录？",
    "total": 3,
    "results": [
      {
        "chunk_id": "uuid",
        "content": "文档片段内容...",
        "similarity": 0.89,
        "chunk_index": 5,
        "document_id": "uuid"
      }
    ]
  }
}
```

---

## 插件 `/plugins`

### GET `/api/v1/plugins` -- 获取可用插件列表

### GET `/api/v1/plugins/{plugin_name}` -- 插件详情

### POST `/api/v1/plugins/{plugin_name}/enable` -- 启用插件

### POST `/api/v1/plugins/{plugin_name}/disable` -- 禁用插件

---

## 渠道 `/channels`

### GET `/api/v1/channels` -- 获取渠道状态

### POST `/api/v1/channels/wechat-work/callback` -- 企业微信回调

企业微信消息推送回调端点，支持 GET（验签）和 POST（消息处理）。

### POST `/api/v1/channels/dingtalk/callback` -- 钉钉回调

钉钉机器人消息回调端点。

---

## 系统 `/system`

### GET `/api/v1/system/health` -- 健康检查

**无需认证**

响应：
```json
{
  "code": 200,
  "data": {
    "status": "healthy",
    "database": "connected",
    "redis": "connected"
  }
}
```

### GET `/api/v1/system/models` -- 可用模型列表

**无需认证**

### GET `/api/v1/system/stats` -- 仪表盘统计

**需要认证**

返回当前租户的统计数据：对话数、消息数、Agent 数、日使用量、意图分布等。

---

## 审计 `/audit`

### GET `/api/v1/audit/logs` -- 审计日志查询

**需要认证**

查询参数：`page`, `size`, `action`, `user_id`, `start_date`, `end_date`

---

## 计费 `/billing`

### GET `/api/v1/billing/usage` -- 用量统计

**需要认证**

查询参数：`start_date`, `end_date`, `group_by`

---

## 错误码

| HTTP 状态码 | 说明 |
|:-----------:|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或认证过期 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用（连接器断开等） |
