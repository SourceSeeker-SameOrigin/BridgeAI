# BridgeAI - 企业 AI 中台产品方案

> 版本：v0.3.0 | 起草日期：2026-04-01 | 更新：2026-04-01 | 状态：待确认
> 参考项目：Fortune AI Agent（宜信金融 AI 顾问系统，Spring Boot + Spring AI）
> v0.3 变更：上下文分析由规则引擎改为大模型一次性输出，管线从 7 阶段简化为 6 阶段

## 一、产品定位

**一句话描述**：让企业用自然语言操作所有内部系统，开箱即用，支持私有部署。

**核心价值**：

```
企业现状：系统割裂、数据孤岛、AI 落不了地
BridgeAI：AI Agent + MCP 连接器 + 行业知识 + 私有部署 = 一站式解决
```

**目标用户**：

| 用户类型 | 画像 | 核心需求 |
|----------|------|---------|
| 技术团队 | 有开发能力，想让 AI 接入内部系统 | MCP 连接器、Agent SDK |
| 企业管理者 | 不懂技术，想提效降本 | 开箱即用、可视化配置 |
| 系统集成商 | 帮客户交付 AI 项目 | 私有部署、行业插件、OEM |
| 个人开发者 | 想基于 BridgeAI 做垂直产品 | 开源核心、API 接口 |

---

## 二、产品架构

<p align="center">
  <img src="../docs/assets/diagrams/system-layers.svg" width="800" alt="系统分层架构" />
</p>

---

## 三、四大方向详细设计

### 方向一：AI Agent 引擎

#### 1.1 核心能力

| 能力 | 说明 | 优先级 |
|------|------|--------|
| 多轮对话 | 上下文记忆，支持长对话 | P0 |
| 意图识别 | 大模型一次调用同时输出意图分析（无规则引擎） | P0 |
| 情绪检测 | 大模型一次调用同时输出情绪判断（无规则引擎） | P0 |
| 任务编排 | 复杂任务自动拆解为多步骤 | P0 |
| 工具调用 | 调用 MCP Server / API / 内置工具 | P0 |
| 流式输出 | 实时返回生成结果（SSE） | P0 |
| 3 级记忆管理 | 工作记忆(内存) + 短期(Redis) + 长期(DB+向量) | P0 |
| Prompt 四层融合 | 人设 + 上下文 + 情绪/意图 + Few-shot 示例 | P0 |
| 智能模型路由 | 5层决策：意图→复杂度→用户等级→性能→成本 | P0 |
| 熔断降级 | 模型调用失败自动切换下一个模型 | P0 |
| 子任务委派 | 主 Agent 委派子任务给专属子 Agent | P1 |
| Few-shot 学习循环 | 高评分对话自动注入为下次 Prompt 示例 | P1 |
| 多 Agent 协作 | 多个 Agent 协同完成复杂任务 | P2 |
| 可视化编排 | 拖拽式 Agent 工作流设计 | P2 |

#### 1.2 6 阶段对话处理管线

> 相比 Fortune AI Agent 的 7 阶段，我们将"上下文分析"合并到大模型调用中，
> 由大模型在回答的同时输出结构化分析，省掉一个独立阶段和一次模型调用。

```
① 请求接入
   ├── 提取 tenant_id, user_id, session_id
   ├── 输入校验 + 内容过滤（敏感词检测）
   └── 设置租户上下文（异步安全传播）

② Prompt 融合（含上下文分析指令）
   ├── Layer 1: Agent 人设 System Prompt（从 DB 加载）
   ├── Layer 2: 记忆摘要 + RAG 检索结果
   ├── Layer 3: Few-shot 高评分案例（从 Redis ZSET 取 Top-3）
   └── Layer 4: 上下文分析指令（要求模型在回复末尾输出 JSON 分析）
       → 情绪/意图/复杂度/关键事实，由大模型一次性判断
       → 无需规则引擎，零维护，准确率远高于关键词匹配

③ 智能模型路由（简化版，基于上一轮分析结果）
   ├── 首次对话：使用 Agent 配置的默认模型
   ├── 后续对话：基于上一轮模型输出的 intent/complexity 动态调整
   ├── 用户等级：VIP 用户使用高端模型
   └── 成本控制：在质量达标前提下选更便宜的

④ AI 调用（熔断降级 + Agent Loop）
   ├── 主模型调用（含工具描述 + 分析指令）
   ├── 失败 → 自动降级到下一个模型
   ├── 降级链: Claude → DeepSeek → Qwen → Ollama
   ├── 熔断器: 连续失败 N 次后直接跳过该模型
   ├── 工具调用 → MCP Gateway 执行 → 结果返回 LLM 继续
   └── 子任务委派 → 子 Agent 独立处理

⑤ 响应解析与持久化
   ├── 分离回复内容和 JSON 分析块
   ├── 回复内容 → 流式输出给用户
   ├── JSON 分析 → 解析后存入 DB（intent/emotion/complexity/key_facts）
   ├── 关键事实 → 写入记忆系统（Redis 短期 + DB 长期）
   └── 使用量记录（Token 统计 + 计费）

⑥ 反馈学习循环
   ├── 收集用户评分（1-5 星）
   ├── ≥4 星的对话自动存入 Redis ZSET（作为 Few-shot 候选）
   └── 持续优化：无需重新训练模型，通过 Prompt 示例自我改进
```

#### 1.2.1 大模型上下文分析指令（核心设计）

```python
# 注入到 System Prompt 末尾，要求模型在回复时同时输出分析
CONTEXT_ANALYSIS_INSTRUCTION = """
在回答用户问题后，请在回复末尾输出分析（用 <analysis> 标签包裹，不要展示给用户）：
<analysis>
{
  "emotion": "positive|negative|confused|urgent|neutral",
  "intent": "用一句话描述用户的真实意图",
  "complexity": "low|medium|high",
  "key_facts": ["从对话中提取的值得记住的关键信息"],
  "needs_tool": true/false,
  "suggested_tools": ["工具名称"]
}
</analysis>
"""

# 后端解析时：
# 1. 用正则提取 <analysis>...</analysis> 中的 JSON
# 2. 回复内容 = 去掉 <analysis> 标签后的文本
# 3. 分析结果存入 message_intents / message_emotions 表
```

#### 1.3 Agent 类型

```python
# 预置 Agent 模板
AGENT_TEMPLATES = {
    "customer_service": "智能客服 Agent - 基于知识库自动回答",
    "data_analyst": "数据分析 Agent - 自然语言查询数据库",
    "office_assistant": "办公助手 Agent - 文档处理、日程管理",
    "code_reviewer": "代码审查 Agent - 自动 Review PR",
    "custom": "自定义 Agent - 用户自行配置"
}

# 支持层级 Agent（参考 Fortune AI 的 Persona 层级）
# 主 Agent 可以委派子任务给子 Agent，每个子 Agent 有独立的：
# - System Prompt（人设）
# - 模型路由配置
# - 对话历史
# - 工具权限
# - 知识库绑定
```

#### 1.4 接入渠道

| 渠道 | 实现方式 | 优先级 |
|------|---------|--------|
| Web Chat | React 聊天组件，WebSocket 实时通信 | P0 |
| 企业微信 | 企微机器人回调 API | P0 |
| 钉钉 | 钉钉机器人 Stream 模式 | P1 |
| 飞书 | 飞书机器人事件订阅 | P1 |
| API | RESTful + WebSocket，供第三方集成 | P0 |
| Telegram | Bot API（已有 openclaw 经验） | P2 |

---

### 方向二：垂直行业 SaaS（行业插件体系）

#### 2.1 插件架构

```
plugins/
├── base.py              # 插件基类，定义标准接口
├── registry.py          # 插件注册中心
├── loader.py            # 动态加载器
└── industries/
    ├── ecommerce/       # 跨境电商插件
    │   ├── plugin.json  # 插件元信息
    │   ├── prompts/     # 行业 Prompt 模板
    │   ├── tools/       # 行业专属工具
    │   ├── knowledge/   # 行业知识库（规则、模板）
    │   └── models/      # 行业数据模型
    ├── legal/           # 法律行业插件
    ├── finance/         # 财税行业插件
    └── education/       # 教育行业插件
```

#### 2.2 首批行业插件

**插件一：跨境电商（P0，首发）**

| 功能 | 说明 |
|------|------|
| Listing 优化 | 输入产品信息 → 生成/优化亚马逊 Listing（标题、五点、描述、关键词） |
| 竞品分析 | 抓取竞品数据 → 价格对比 → 利润分析 → 调价建议 |
| 评论分析 | 批量分析买家评论 → 提取痛点 → 生成改进建议 |
| 客服回复 | 多语言买家消息自动回复 |
| 选品建议 | 基于市场数据和趋势推荐潜力产品 |

**插件二：财税助手（P1）**

| 功能 | 说明 |
|------|------|
| 智能记账 | 银行流水 + 发票 → 自动匹配科目 → 生成凭证 |
| 税务风险检测 | 分析账目数据 → 检测异常 → 风险预警 |
| 政策问答 | 基于最新财税法规的专业问答 |
| 报表生成 | 自然语言描述 → 自动生成财务报表 |

**插件三：法律助手（P1）**

| 功能 | 说明 |
|------|------|
| 合同审查 | 上传合同 → 标注风险条款 → 给出修改建议 |
| 文书生成 | 输入案情要素 → 生成法律文书 |
| 案例检索 | 自然语言检索裁判文书，预测胜诉率 |

**插件四：教育助手（P2）**

| 功能 | 说明 |
|------|------|
| 智能出题 | 按知识点和难度自动生成试题 |
| 学情分析 | 答题数据 → 个性化学习报告 |
| 课件生成 | 大纲 → 自动生成课件内容 |

#### 2.3 插件开发 SDK

```python
from bridgeai.plugins import PluginBase, tool, prompt_template

class EcommercePlugin(PluginBase):
    """跨境电商行业插件"""

    name = "ecommerce"
    display_name = "跨境电商助手"
    version = "1.0.0"

    @tool(name="optimize_listing", description="优化亚马逊 Listing")
    async def optimize_listing(self, product_info: dict) -> dict:
        """根据产品信息生成优化的 Listing"""
        ...

    @prompt_template(name="competitor_analysis")
    def competitor_analysis_prompt(self) -> str:
        return "分析以下竞品数据，给出定价建议..."
```

---

### 方向三：MCP Server 生态

#### 3.1 MCP 网关设计

```
MCP Gateway
├── 连接管理        # 管理所有 MCP Server 的生命周期
├── 协议适配        # 标准 MCP 协议实现
├── 权限控制        # 哪些 Agent 可以调用哪些 MCP Server
├── 调用审计        # 所有 MCP 调用记录留痕
├── 负载均衡        # 多实例 MCP Server 的负载分配
└── 健康检查        # 自动检测 MCP Server 状态
```

#### 3.2 首批 MCP 连接器

**连接器一：飞书 MCP（P0）**

| 工具 | 说明 |
|------|------|
| `feishu_send_message` | 发送消息到指定群/用户 |
| `feishu_read_doc` | 读取飞书文档内容 |
| `feishu_create_doc` | 创建飞书文档 |
| `feishu_list_calendar` | 查看日历安排 |
| `feishu_create_approval` | 发起审批流程 |
| `feishu_query_bitable` | 查询多维表格数据 |
| `feishu_update_bitable` | 更新多维表格数据 |

**连接器二：MySQL MCP（P0）**

| 工具 | 说明 |
|------|------|
| `mysql_query` | 执行 SELECT 查询（只读模式） |
| `mysql_describe` | 查看表结构 |
| `mysql_list_tables` | 列出所有表 |
| `mysql_explain` | 查看查询执行计划 |

安全特性：
- 只读模式（默认，可配置为读写）
- 行列级权限控制
- 查询超时限制
- 自动脱敏（手机号、身份证、银行卡）
- 查询审计日志

**连接器三：钉钉 MCP（P1）**

| 工具 | 说明 |
|------|------|
| `dingtalk_send_message` | 发送消息 |
| `dingtalk_create_task` | 创建待办任务 |
| `dingtalk_list_approval` | 查看审批列表 |
| `dingtalk_query_attendance` | 查询考勤数据 |

**连接器四：通用 HTTP API MCP（P0）**

| 工具 | 说明 |
|------|------|
| `http_get` | 发起 GET 请求 |
| `http_post` | 发起 POST 请求 |
| `http_put` | 发起 PUT 请求 |
| `http_delete` | 发起 DELETE 请求 |

作用：让用户无需开发，直接通过配置把任何 REST API 接入 BridgeAI。

**连接器五：金蝶/用友 MCP（P2）**

| 工具 | 说明 |
|------|------|
| `kingdee_query_voucher` | 查询会计凭证 |
| `kingdee_query_balance` | 查询科目余额 |
| `kingdee_create_voucher` | 创建会计凭证 |

#### 3.3 MCP 连接器市场

```
连接器市场功能：
├── 官方连接器        # BridgeAI 团队维护
├── 社区连接器        # 第三方开发者贡献
├── 一键安装          # 从市场安装到自己的 BridgeAI 实例
├── 版本管理          # 连接器的版本升级和回滚
├── 评分和评论        # 用户对连接器的反馈
└── 开发者文档        # 如何开发自己的 MCP 连接器
```

---

### 方向四：私有化部署

#### 4.1 部署方案

| 方案 | 适用场景 | 复杂度 |
|------|---------|--------|
| Docker Compose | 中小企业，单机部署 | 低 |
| Kubernetes Helm | 大企业，集群部署 | 中 |
| 离线安装包 | 政企内网，无外网 | 中 |

#### 4.2 Docker Compose 架构

```yaml
services:
  bridgeai-api:        # FastAPI 后端
  bridgeai-worker:     # Celery 异步任务
  bridgeai-web:        # React 前端
  bridgeai-mcp:        # MCP 网关
  postgres:            # 关系型数据库
  milvus:              # Milvus 向量数据库
  redis:               # 缓存 + 消息队列
  minio:               # 文件存储（文档、知识库）
```

#### 4.3 模型适配层（含智能路由 + 熔断降级）

```python
# 支持多模型，客户按需选择
MODEL_PROVIDERS = {
    "claude": {
        "name": "Anthropic Claude",
        "models": ["claude-opus-4-6", "claude-sonnet-4-6"],
        "type": "cloud",
        "note": "SaaS 版默认，能力最强"
    },
    "qwen": {
        "name": "通义千问",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "type": "cloud/private",
        "note": "国产，支持私有部署"
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "type": "cloud/private",
        "note": "性价比高，支持私有部署"
    },
    "openai": {
        "name": "OpenAI GPT",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "type": "cloud",
        "note": "备选"
    },
    "ollama": {
        "name": "Ollama 本地模型",
        "models": ["llama3", "qwen2", "mistral"],
        "type": "private",
        "note": "完全离线，适合高安全要求"
    }
}

# 智能模型路由配置（参考 Fortune AI 的 5 层决策树）
MODEL_ROUTING = {
    # 按意图映射默认模型
    "intent_model_map": {
        "data_analysis": "claude-sonnet-4-6",    # 数据分析需要强模型
        "customer_service": "qwen-plus",          # 客服用性价比模型
        "small_talk": "qwen-turbo",               # 闲聊用快速模型
        "code_review": "claude-opus-4-6",         # 代码审查用最强模型
        "default": "deepseek-chat"
    },
    # 熔断降级链（按优先级排列）
    "fallback_chain": [
        "claude-sonnet-4-6",
        "deepseek-chat",
        "qwen-plus",
        "qwen-turbo",
        "ollama/qwen2"   # 最终兜底：本地模型
    ],
    # 熔断器配置
    "circuit_breaker": {
        "failure_threshold": 3,       # 连续失败 3 次触发熔断
        "recovery_timeout_sec": 60,   # 熔断后 60 秒尝试恢复
        "call_timeout_sec": 30        # 单次调用超时
    }
}
```

#### 4.4 安全合规

| 安全要求 | 实现方式 |
|----------|---------|
| 数据不出境 | 私有部署 + 国产模型 |
| 访问控制 | RBAC 权限模型 |
| 操作审计 | 所有 Agent 操作记录到审计表 |
| 数据加密 | TLS 传输加密 + AES 存储加密 |
| 脱敏输出 | 敏感字段自动脱敏（手机号、身份证等） |
| 等保合规 | 支持等保二级/三级要求（政企场景） |

---

## 四、技术栈

| 层 | 技术选型 | 理由 |
|------|---------|------|
| **后端框架** | FastAPI | 异步高性能，类型安全，自动文档 |
| **数据库** | PostgreSQL + Milvus | 关系型数据 + 向量检索 |
| **缓存/队列** | Redis + Celery | 会话缓存 + 异步任务 |
| **Agent 框架** | LangGraph | 状态机编排，支持复杂工作流 |
| **MCP** | FastMCP (Python) | 官方推荐，开发快 |
| **RAG** | LlamaIndex | 成熟生态，支持多数据源 |
| **文件存储** | MinIO / 阿里云 OSS | 兼容 S3 协议 |
| **前端框架** | React 18 + TypeScript | 生态成熟 |
| **UI 组件库** | Ant Design 5 | 国内最流行的企业级组件库 |
| **前端状态** | Zustand | 轻量，比 Redux 简单 |
| **前端构建** | Vite | 快，现代 |
| **容器化** | Docker + Docker Compose | 一键部署 |
| **API 文档** | Swagger/OpenAPI (FastAPI 自带) | 自动生成 |

---

## 五、数据库设计（核心表）

### 5.1 用户与权限

```sql
-- 租户（多租户支持）
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    plan VARCHAR(20) DEFAULT 'free',  -- free/pro/enterprise
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 用户
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    password_hash VARCHAR(255),
    role VARCHAR(20) DEFAULT 'user',  -- admin/user/viewer
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- API Key
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.2 Agent 与会话（参考 Fortune AI 的 Persona + 4维隔离）

```sql
-- Agent 定义（支持层级结构：主Agent → 子Agent）
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    parent_agent_id UUID REFERENCES agents(id),  -- 子Agent指向父Agent
    task_key VARCHAR(100),           -- 子Agent的任务标识（如 fund_advisory）
    name VARCHAR(100) NOT NULL,
    description TEXT,
    type VARCHAR(50) DEFAULT 'custom',
    system_prompt TEXT,
    model_provider VARCHAR(50) DEFAULT 'claude',
    model_name VARCHAR(100) DEFAULT 'claude-sonnet-4-6',
    model_config JSONB DEFAULT '{}', -- Agent级模型路由配置覆盖
    tools JSONB DEFAULT '[]',        -- 绑定的工具列表
    plugins JSONB DEFAULT '[]',      -- 绑定的行业插件
    knowledge_base_id UUID,          -- 绑定的知识库
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 会话（4维隔离：tenant × user × agent × session）
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    agent_id UUID REFERENCES agents(id),
    user_id UUID REFERENCES users(id),
    channel VARCHAR(50),             -- web/wechat/dingtalk/feishu/api
    channel_user_id VARCHAR(200),
    title VARCHAR(200),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 消息（两层设计：快速字段 + 详情字段）
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL,       -- user/assistant/system/tool
    content TEXT,
    tool_calls JSONB,                -- Agent 的工具调用
    tool_results JSONB,              -- 工具返回结果
    -- 快速查询字段（参考 Fortune AI）
    intent VARCHAR(100),             -- 意图标识（快速过滤）
    emotion VARCHAR(50),             -- 情绪类型（快速统计）
    task_key VARCHAR(100),           -- 子任务标识
    model_used VARCHAR(100),         -- 实际使用的模型
    system_prompt_snapshot TEXT,     -- 当时的 System Prompt（审计用）
    -- 性能指标
    tokens_used INTEGER,
    response_time_ms INTEGER,
    first_token_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 意图识别详情（懒加载，深度分析时使用）
CREATE TABLE message_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id),
    primary_intent VARCHAR(100),
    secondary_intents JSONB DEFAULT '[]',
    intent_details JSONB DEFAULT '{}',  -- 完整分类数据
    confidence_score DECIMAL(3,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 情绪检测详情（懒加载）
CREATE TABLE message_emotions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id),
    emotion_type VARCHAR(50),        -- positive/negative/confused/urgent/neutral
    emotion_score DECIMAL(3,2),
    emotion_details JSONB DEFAULT '{}',
    confidence VARCHAR(10),          -- high/medium/low
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 用户评分（Few-shot 学习循环的数据源）
CREATE TABLE message_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id),
    tenant_id UUID,
    agent_id UUID,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    feedback TEXT,
    -- 缓存对话内容（避免 JOIN 查询，用于 Few-shot 注入）
    user_message TEXT,
    ai_response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 记忆系统（3级：工作记忆在Redis，短期在Redis+DB，长期在DB+向量）
CREATE TABLE agent_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,
    user_id UUID,
    agent_id UUID,
    memory_type VARCHAR(20),         -- fact/preference/context
    content TEXT NOT NULL,
    importance_score DECIMAL(3,2) DEFAULT 0.5,  -- 重要性评分
    metadata JSONB DEFAULT '{}',
    expires_at TIMESTAMPTZ,          -- 可选过期时间
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- 语义向量存储在 Milvus（Collection: agent_memories, FLOAT_VECTOR(1024), HNSW 索引）
```

### 5.3 MCP 与知识库

```sql
-- MCP 连接器配置
CREATE TABLE mcp_connectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,       -- feishu/mysql/dingtalk/http
    config JSONB NOT NULL,           -- 连接配置（加密存储）
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'unknown',
    last_health_check TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- MCP 调用审计
CREATE TABLE mcp_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID,
    connector_id UUID REFERENCES mcp_connectors(id),
    agent_id UUID,
    user_id UUID,
    tool_name VARCHAR(100),
    input_params JSONB,
    output_result JSONB,
    status VARCHAR(20),              -- success/error
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 知识库
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    embedding_model VARCHAR(100) DEFAULT 'bge-m3',
    chunk_size INTEGER DEFAULT 512,
    chunk_overlap INTEGER DEFAULT 50,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 知识库文档
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_base_id UUID REFERENCES knowledge_bases(id),
    filename VARCHAR(255),
    file_type VARCHAR(50),
    file_size BIGINT,
    status VARCHAR(20) DEFAULT 'pending',  -- pending/processing/ready/error
    chunk_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 知识库向量块
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES knowledge_documents(id),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- 向量存储在 Milvus（Collection: knowledge_chunks, FLOAT_VECTOR(1024), HNSW 索引, COSINE 距离）
```

### 5.4 行业插件与计费

```sql
-- 已安装插件
CREATE TABLE installed_plugins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    plugin_name VARCHAR(100) NOT NULL,
    version VARCHAR(20),
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    installed_at TIMESTAMPTZ DEFAULT NOW()
);

-- 使用量统计（计费用）
CREATE TABLE usage_records (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID,
    agent_id UUID,
    type VARCHAR(50),                -- agent_call/mcp_call/rag_query/embedding
    model VARCHAR(100),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0,    -- 成本（分）
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 按月汇总（快速查询）
CREATE INDEX idx_usage_records_monthly
    ON usage_records (tenant_id, date_trunc('month', created_at));
```

---

## 六、API 设计（核心接口）

### 6.1 Agent 对话

```
POST   /api/v1/chat/completions          # 发送消息（流式/非流式）
GET    /api/v1/conversations              # 会话列表
GET    /api/v1/conversations/{id}         # 会话详情
DELETE /api/v1/conversations/{id}         # 删除会话
GET    /api/v1/conversations/{id}/messages # 消息历史
```

### 6.2 Agent 管理

```
GET    /api/v1/agents                     # Agent 列表
POST   /api/v1/agents                     # 创建 Agent
GET    /api/v1/agents/{id}                # Agent 详情
PUT    /api/v1/agents/{id}                # 更新 Agent
DELETE /api/v1/agents/{id}                # 删除 Agent
POST   /api/v1/agents/{id}/test           # 测试 Agent
```

### 6.3 MCP 连接器

```
GET    /api/v1/mcp/connectors             # 连接器列表
POST   /api/v1/mcp/connectors             # 添加连接器
PUT    /api/v1/mcp/connectors/{id}        # 更新配置
DELETE /api/v1/mcp/connectors/{id}        # 删除连接器
POST   /api/v1/mcp/connectors/{id}/test   # 测试连接
GET    /api/v1/mcp/connectors/{id}/tools  # 查看可用工具
GET    /api/v1/mcp/audit                  # 调用审计日志
```

### 6.4 知识库

```
GET    /api/v1/knowledge                  # 知识库列表
POST   /api/v1/knowledge                  # 创建知识库
POST   /api/v1/knowledge/{id}/documents   # 上传文档
DELETE /api/v1/knowledge/{id}/documents/{doc_id}  # 删除文档
POST   /api/v1/knowledge/{id}/query       # 知识库检索
GET    /api/v1/knowledge/{id}/status      # 索引状态
```

### 6.5 行业插件

```
GET    /api/v1/plugins/marketplace        # 插件市场（可用插件）
GET    /api/v1/plugins/installed          # 已安装插件
POST   /api/v1/plugins/install            # 安装插件
PUT    /api/v1/plugins/{id}/config        # 配置插件
DELETE /api/v1/plugins/{id}               # 卸载插件
```

### 6.6 系统管理

```
GET    /api/v1/system/health              # 健康检查
GET    /api/v1/system/usage               # 使用量统计
GET    /api/v1/system/models              # 可用模型列表
PUT    /api/v1/system/settings            # 系统设置
```

---

## 七、前端页面规划

| 页面 | 功能 | 优先级 |
|------|------|--------|
| **登录/注册** | 账号密码 + 微信扫码 | P0 |
| **仪表盘** | 使用概览、调用量图表、费用统计 | P0 |
| **对话界面** | 选择 Agent 对话，流式输出，历史记录 | P0 |
| **Agent 管理** | 创建/编辑/删除 Agent，配置 Prompt 和工具 | P0 |
| **MCP 连接器** | 添加/管理连接器，查看可用工具，测试连接 | P0 |
| **知识库管理** | 创建知识库，上传文档，查看索引状态 | P0 |
| **插件市场** | 浏览/安装/卸载行业插件 | P1 |
| **审计日志** | 查看所有 Agent 和 MCP 操作记录 | P1 |
| **系统设置** | 模型配置、团队管理、API Key 管理 | P1 |
| **Agent 编排器** | 可视化拖拽设计 Agent 工作流 | P2 |

---

## 八、商业模式

### 8.1 定价

| 版本 | 价格 | 包含内容 |
|------|------|---------|
| **免费版** | 0 元 | 1 个 Agent, 2 个 MCP 连接器, 100 次/月调用, 社区支持 |
| **专业版** | 299 元/月 | 10 个 Agent, 10 个 MCP 连接器, 5000 次/月, 2 个行业插件 |
| **企业版** | 999 元/月 | 无限 Agent, 无限 MCP, 50000 次/月, 全部插件, 优先支持 |
| **私有部署** | 15-50 万（一次性）| 全功能, 私有部署, 定制开发, 专属支持 |

### 8.2 收入来源

```
SaaS 订阅          40%    ← 主要收入
私有化部署          30%    ← 高客单
MCP 连接器定制开发   15%    ← 增值服务
行业插件销售         10%    ← 长尾收入
技术咨询与培训        5%    ← 辅助
```

---

## 九、开发排期

### Phase 1：核心引擎 MVP（第 1-3 周）

```
Week 1:
  ├── 项目骨架搭建（FastAPI + React + Docker Compose）
  ├── 数据库 Schema + Migration
  ├── 用户认证（JWT + API Key）
  └── Agent 引擎核心（LangGraph 集成）

Week 2:
  ├── 对话 API（流式/非流式）
  ├── MCP 网关 + MySQL MCP Server
  ├── RAG 引擎（文档上传 → 向量化 → 检索）
  └── Web Chat 前端（React 聊天界面）

Week 3:
  ├── 飞书 MCP Server
  ├── 通用 HTTP API MCP
  ├── Agent 管理页面（CRUD）
  ├── MCP 连接器管理页面
  └── 知识库管理页面
```

### Phase 2：行业插件 + 渠道接入（第 4-6 周）

```
Week 4:
  ├── 插件体系框架
  ├── 跨境电商插件 v1
  └── 企微机器人接入

Week 5:
  ├── 财税助手插件 v1
  ├── 钉钉机器人接入
  └── 审计日志系统

Week 6:
  ├── 插件市场页面
  ├── 使用量统计 + 计费
  └── 系统设置页面
```

### Phase 3：私有部署 + 优化（第 7-8 周）

```
Week 7:
  ├── Docker Compose 一键部署脚本
  ├── 国产模型适配（Qwen/DeepSeek）
  ├── Ollama 本地模型支持
  └── 部署文档

Week 8:
  ├── 性能优化（缓存、并发）
  ├── 安全加固（脱敏、加密、RBAC）
  ├── 开源 MCP Server 独立发布到 GitHub
  └── 产品文档 + 官网
```

---

## 十、风险评估

| 风险 | 等级 | 应对措施 |
|------|------|---------|
| LLM API 成本过高 | 高 | 支持多模型切换，引导用户用国产模型 |
| 飞书/钉钉 API 变更 | 中 | 抽象适配层，降低耦合 |
| 首批用户获取困难 | 中 | 开源 MCP Server 引流 + 技术文章推广 |
| 行业知识深度不够 | 中 | 找行业合伙人，或先做通用场景 |
| 一人开发进度慢 | 高 | AI 辅助开发，MVP 先做核心链路 |
| 竞品（Dify/Coze）碾压 | 中 | 差异化：行业深度 + 私有部署 + MCP 生态 |

---

## 十一、成功指标

### 3 个月目标

| 指标 | 目标 |
|------|------|
| GitHub Star（MCP 项目） | 500+ |
| 注册用户 | 200+ |
| 付费用户 | 10+ |
| 月收入 | 5000+ 元 |
| MCP 连接器数量 | 5+ |
| 行业插件数量 | 2+ |

### 6 个月目标

| 指标 | 目标 |
|------|------|
| GitHub Star | 2000+ |
| 注册用户 | 1000+ |
| 付费用户 | 50+ |
| 月收入 | 30000+ 元 |
| 私有部署项目 | 2+ |
| 社区贡献者 | 10+ |
