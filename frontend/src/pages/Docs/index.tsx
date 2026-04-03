import { useState } from 'react'
import { Menu } from 'antd'
import {
  RocketOutlined,
  ApiOutlined,
  AppstoreOutlined,
  CloudServerOutlined,
  LinkOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import GlassCard from '../../components/GlassCard'
import MarkdownRenderer from '../../components/MarkdownRenderer'

/* ---------- doc content ---------- */
const DOCS: Record<string, string> = {
  quickstart: `# 快速开始

欢迎使用 **BridgeAI** —— 企业级 AI 中台。

## 1. 注册与登录

访问平台首页，点击「立即开始」完成注册。支持邮箱注册和企业 SSO 登录。

## 2. 创建你的第一个 Agent

进入「智能体」页面，点击「创建 Agent」：

1. 填写名称和描述
2. 选择底层模型（如 DeepSeek、GPT-4o、Claude）
3. 编写系统提示词（System Prompt）
4. 保存并测试

\`\`\`json
{
  "name": "客服助手",
  "model": "deepseek-chat",
  "system_prompt": "你是一个专业的客服助手，帮助用户解答产品问题。",
  "temperature": 0.7
}
\`\`\`

## 3. 开始对话

在「对话」页面选择刚创建的 Agent，即可开始智能对话。

## 4. 接入渠道

支持通过以下方式接入：
- **Web 界面**：直接在平台对话
- **REST API**：通过 API 集成到你的应用
- **企业微信 / 钉钉**：在「设置 → 渠道管理」中配置

---

> 如需帮助，请联系 support@bridgeai.com
`,

  api: `# API 文档

## 基础信息

- **Base URL**: \`/api/v1\`
- **认证方式**: Bearer Token
- **Content-Type**: \`application/json\`

## 认证

### 登录获取 Token

\`\`\`bash
POST /api/v1/auth/login

{
  "username": "admin",
  "password": "your-password"
}
\`\`\`

**响应：**

\`\`\`json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400
  }
}
\`\`\`

## Agent 管理

### 获取 Agent 列表

\`\`\`bash
GET /api/v1/agents
Authorization: Bearer <token>
\`\`\`

### 创建 Agent

\`\`\`bash
POST /api/v1/agents

{
  "name": "客服机器人",
  "description": "自动回复客户咨询",
  "model_id": "deepseek-chat",
  "system_prompt": "你是一个专业的客服助手。",
  "temperature": 0.7,
  "tools": ["search", "calculator"]
}
\`\`\`

## 对话

### 发送消息（流式）

\`\`\`bash
POST /api/v1/chat/stream

{
  "agent_id": "agent-uuid",
  "session_id": "session-uuid",
  "message": "你好，请介绍一下你们的产品"
}
\`\`\`

响应为 SSE（Server-Sent Events）格式。

## 知识库

### 上传文档

\`\`\`bash
POST /api/v1/knowledge/{kb_id}/upload
Content-Type: multipart/form-data

file: <your-document.pdf>
\`\`\`

### 检索文档

\`\`\`bash
POST /api/v1/knowledge/{kb_id}/search

{
  "query": "退货政策是什么？",
  "top_k": 5
}
\`\`\`

## 统一响应格式

\`\`\`json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
\`\`\`

错误响应：

\`\`\`json
{
  "code": 400,
  "message": "参数错误：name 不能为空",
  "data": null
}
\`\`\`
`,

  plugins: `# 插件开发指南

## 插件体系

BridgeAI 采用插件化架构，支持通过标准接口扩展平台能力。

## 插件结构

\`\`\`
my-plugin/
├── manifest.json      # 插件元数据
├── main.py            # 入口逻辑
├── requirements.txt   # 依赖
└── README.md          # 说明文档
\`\`\`

## manifest.json 示例

\`\`\`json
{
  "name": "ecommerce-plugin",
  "display_name": "电商助手",
  "version": "1.0.0",
  "description": "提供订单查询、库存管理等电商能力",
  "category": "ecommerce",
  "author": "BridgeAI Team",
  "tools": [
    {
      "name": "query_order",
      "description": "根据订单号查询订单详情",
      "parameters": {
        "order_id": { "type": "string", "description": "订单编号", "required": true }
      }
    }
  ]
}
\`\`\`

## 开发流程

1. 创建插件目录结构
2. 编写 \`manifest.json\` 定义工具
3. 实现工具逻辑（Python / Node.js）
4. 本地测试：\`bridgeai plugin test ./my-plugin\`
5. 打包上传：\`bridgeai plugin publish ./my-plugin\`

## 工具函数规范

\`\`\`python
async def query_order(order_id: str) -> dict:
    """根据订单号查询订单详情"""
    # 你的业务逻辑
    order = await db.orders.find_one({"order_id": order_id})
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "total": order["total"],
    }
\`\`\`

> 工具函数需要返回可序列化的 dict，供 Agent 解析使用。
`,

  mcp: `# MCP 开发指南

## 什么是 MCP？

**MCP（Model Context Protocol）** 是 BridgeAI 用于连接外部系统的标准协议。通过 MCP，AI Agent 可以安全地访问企业内部系统。

## 支持的连接器

| 连接器 | 用途 | 状态 |
|--------|------|------|
| 飞书 | 消息、日历、文档 | 可用 |
| 钉钉 | 消息、审批、考勤 | 可用 |
| 企业微信 | 消息、通讯录 | 可用 |
| MySQL | 数据库查询 | 可用 |
| PostgreSQL | 数据库查询 | 可用 |
| HTTP API | 通用 REST 调用 | 可用 |

## 自定义 MCP Server

\`\`\`python
from bridgeai_mcp import MCPServer, tool

server = MCPServer(name="my-connector")

@server.tool()
async def get_employee(employee_id: str) -> dict:
    """查询员工信息"""
    # 调用内部 HR 系统
    result = await hr_api.get(f"/employees/{employee_id}")
    return result

if __name__ == "__main__":
    server.run(port=8001)
\`\`\`

## 注册连接器

在「MCP 连接器」页面添加自定义 Server：

1. 填写名称和 Server URL
2. 选择传输协议（SSE / WebSocket）
3. 配置认证信息
4. 测试连接
5. 保存

## 在 Agent 中使用

创建或编辑 Agent 时，在「工具」选项中勾选已注册的 MCP 连接器，Agent 即可调用对应工具。
`,

  deploy: `# 部署指南

## 系统要求

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Node.js 18+（前端构建）

## Docker 部署（推荐）

\`\`\`bash
# 克隆代码
git clone https://github.com/SourceSeeker-SameOrigin/BridgeAI.git
cd bridgeai

# 复制环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库、API Key 等

# 启动
docker compose up -d
\`\`\`

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| DATABASE_URL | PostgreSQL 连接 | postgresql://user:pass@localhost/bridgeai |
| REDIS_URL | Redis 连接 | redis://localhost:6379/0 |
| SECRET_KEY | JWT 签名密钥 | your-secret-key-here |
| DEEPSEEK_API_KEY | DeepSeek API Key | sk-... |
| OPENAI_API_KEY | OpenAI API Key | sk-proj-... |

## 手动部署

### 后端

\`\`\`bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 初始化数据库
alembic upgrade head

# 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
\`\`\`

### 前端

\`\`\`bash
cd frontend
npm install
npm run build

# 产物在 dist/ 目录，配合 Nginx 部署
\`\`\`

## Nginx 配置示例

\`\`\`nginx
server {
    listen 80;
    server_name bridgeai.example.com;

    location / {
        root /opt/bridgeai/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
\`\`\`

## 生产建议

- 使用 **Gunicorn + Uvicorn** 多 worker 部署
- 配置 **HTTPS** 证书
- 启用 **日志持久化**
- 配置 **监控告警**（Prometheus + Grafana）
- 定期 **备份数据库**
`,
}

export default function DocsPage() {
  const { t } = useTranslation()
  const [activeKey, setActiveKey] = useState('quickstart')

  const MENU_ITEMS = [
    { key: 'quickstart', icon: <RocketOutlined />, label: t('docs.quickstart') },
    { key: 'api', icon: <ApiOutlined />, label: t('docs.api') },
    { key: 'plugins', icon: <AppstoreOutlined />, label: t('docs.pluginDev') },
    { key: 'mcp', icon: <LinkOutlined />, label: t('docs.mcpDev') },
    { key: 'deploy', icon: <CloudServerOutlined />, label: t('docs.deploy') },
  ]

  return (
    <div className="animate-fade-in">
      <h2 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', marginBottom: 24 }}>
        {t('docs.title')}
      </h2>

      <div style={{ display: 'flex', gap: 24, height: 'calc(100vh - 160px)' }}>
        {/* left sidebar */}
        <div
          style={{
            width: 200,
            flexShrink: 0,
            background: 'rgba(17,24,39,0.7)',
            borderRadius: 12,
            border: '1px solid rgba(148,163,184,0.1)',
            overflow: 'hidden',
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[activeKey]}
            items={MENU_ITEMS}
            onClick={({ key }) => setActiveKey(key)}
            style={{ background: 'transparent', borderRight: 'none' }}
          />
        </div>

        {/* right content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <GlassCard hoverable={false} style={{ height: '100%', overflow: 'auto' }}>
            <MarkdownRenderer content={DOCS[activeKey] ?? ''} />
          </GlassCard>
        </div>
      </div>
    </div>
  )
}
