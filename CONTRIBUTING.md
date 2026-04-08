# 贡献指南

感谢你对 BridgeAI 的关注！本文档将帮助你快速上手开发和贡献代码。

## 开发环境搭建

### 前置要求

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 16（或使用 Docker）
- Redis 7（或使用 Docker）

### 1. 克隆项目

```bash
git clone https://github.com/SourceSeeker-SameOrigin/BridgeAI.git
cd BridgeAI
```

### 2. 启动基础设施

```bash
docker compose -f docker/docker-compose.dev.yml up -d
```

这会启动 PostgreSQL + Milvus 向量数据库、Redis 和 MinIO。

### 3. 后端环境

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制并编辑环境变量
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key

# 数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 前端环境

```bash
cd frontend
npm install
npm run dev
```

### 5. 验证

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:5173 | Web 界面 |
| 后端 API | http://localhost:8000 | REST API |
| API 文档 | http://localhost:8000/docs | Swagger 文档 |
| MinIO | http://localhost:9001 | 对象存储控制台 |
| Prometheus | http://localhost:9090 | 监控 |
| Grafana | http://localhost:3001 | 监控大盘 |
| Milvus | localhost:19530 | 向量数据库 |
| PostgreSQL | localhost:5432 | 数据库 |
| Redis | localhost:6379 | 缓存 |
| Ollama | http://localhost:11434 | 本地模型 |

健康检查：`curl http://localhost:8000/api/v1/system/health`

## 代码规范

### Python 后端

- 遵循 **PEP 8** 编码规范
- 所有函数签名必须使用 **类型注解**
- 使用 `black` 格式化代码，`isort` 排序导入，`ruff` 进行 lint
- 使用 `logging` 模块记录日志，禁止 `print()`
- API 接口参数使用 Pydantic Schema 校验
- POST 请求参数使用 Body 类型
- 优先使用不可变数据结构（`@dataclass(frozen=True)`）

```bash
# 格式化代码
black app/
isort app/
ruff check app/ --fix
```

### TypeScript 前端

- 使用 TypeScript strict 模式
- 组件使用函数式组件 + Hooks
- 状态管理使用 Zustand
- 使用 ESLint + Prettier 格式化

### 数据库变更

所有数据库结构变更必须通过 Alembic 迁移：

```bash
# 创建迁移
alembic revision --autogenerate -m "描述变更内容"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### Git Commit 规范

使用 Conventional Commits 格式：

```
<type>: <description>

<optional body>
```

**Type 类型：**

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 代码重构（不影响功能） |
| `docs` | 文档变更 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖变更 |
| `perf` | 性能优化 |
| `ci` | CI/CD 配置变更 |

**示例：**

```
feat: 添加飞书渠道连接器
fix: 修复 MCP 连接器超时未重连的问题
refactor: 重构 Agent Pipeline 状态管理
docs: 更新 API 文档中的认证说明
```

## Pull Request 流程

### 1. 创建分支

```bash
git checkout -b feat/your-feature-name
# 或
git checkout -b fix/issue-description
```

### 2. 开发与测试

- 编写代码并确保符合代码规范
- 编写单元测试，确保测试通过
- 运行已有测试确保没有回归

```bash
cd backend
pytest tests/ -v
```

### 3. 提交 PR

- PR 标题简洁明了，不超过 70 个字符
- 在 PR 描述中说明：
  - **做了什么** -- 简要描述改动内容
  - **为什么** -- 改动的原因和目的
  - **怎么测试** -- 如何验证改动正确性
- 关联相关 Issue（如有）

### 4. Code Review

- 至少需要 1 位 Reviewer 通过
- 解决所有 Review 评论
- CI 检查通过后合并

## Issue 提交指南

### Bug 报告

请包含以下信息：

```markdown
## Bug 描述
简要描述遇到的问题。

## 复现步骤
1. 进入 '...'
2. 点击 '...'
3. 输入 '...'
4. 观察到错误

## 期望行为
描述你期望发生的情况。

## 实际行为
描述实际发生的情况。

## 环境信息
- 操作系统: [例如 macOS 15.2]
- Python 版本: [例如 3.11.5]
- Node.js 版本: [例如 18.20.0]
- 浏览器: [例如 Chrome 120]

## 截图/日志
如有错误截图或日志，请附上。
```

### 功能建议

```markdown
## 功能描述
简要描述你希望添加的功能。

## 使用场景
描述这个功能解决什么问题，谁会使用它。

## 建议实现方式
如果你有实现思路，请在此描述。

## 其他信息
任何补充信息。
```

## 项目结构说明

```
backend/app/
├── api/v1/          # API 路由 -- 只做参数校验和响应封装
├── services/        # 业务逻辑 -- 核心业务处理
├── models/          # ORM 模型 -- 数据库表定义
├── schemas/         # Pydantic 模型 -- 请求/响应数据结构
├── engine/          # Agent 管线 -- LangGraph 状态机
├── agents/          # 模型路由 + 熔断 -- 模型选择与故障转移
├── mcp/             # MCP 网关 -- 工具连接与执行
├── rag/             # RAG 引擎 -- 文档解析与向量检索
├── plugins/         # 行业插件 -- 可扩展的行业能力
├── channels/        # 渠道接入 -- 企微/钉钉消息处理
├── providers/       # LLM 适配 -- 多模型提供商统一接口
├── middleware/      # 中间件 -- 租户隔离、安全
└── core/            # 核心工具 -- 数据库、Redis、安全、异常
```

## 开发约定

1. **API 设计** -- 所有 API 统一使用 `ApiResponse` 封装响应
2. **错误处理** -- 使用 `AppException` 体系，不在 API 层捕获通用异常
3. **多租户** -- 所有查询必须考虑 `tenant_id` 隔离
4. **安全** -- 不在日志中记录 API Key、密码等敏感信息
5. **异步** -- 数据库和 HTTP 操作全部使用 async/await

## 许可证

通过贡献代码，你同意你的贡献将以 [MIT License](LICENSE) 授权。
