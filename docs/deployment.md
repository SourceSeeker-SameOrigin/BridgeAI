# BridgeAI 部署指南

## 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 20 GB | 50 GB+ (含模型存储) |
| Docker | 24.0+ | 最新版 |
| Docker Compose | v2.20+ | 最新版 |
| 操作系统 | Linux / macOS | Ubuntu 22.04 LTS |

## 快速开始

### 一键部署

```bash
git clone <repo-url> BridgeAI
cd BridgeAI
bash scripts/setup.sh
```

脚本会自动：
1. 检查系统依赖（Docker、Docker Compose）
2. 生成 `.env` 文件并填入随机密钥
3. 提示配置 LLM API Keys
4. 构建并启动所有服务
5. 等待健康检查通过

### 手动部署

```bash
# 1. 复制并编辑环境配置
cp .env.example .env
# 编辑 .env，至少配置一个 LLM API Key

# 2. 开发模式
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.dev.yml \
  up -d --build

# 3. 生产模式
docker compose --env-file .env \
  -f docker/docker-compose.prod.yml \
  up -d --build
```

## 部署模式对比

| 特性 | 开发模式 | 生产模式 |
|------|---------|---------|
| 热重载 | 支持 | 不支持 |
| API 副本数 | 1 | 2 |
| Nginx 反向代理 | 无 | 有 |
| Celery Worker | 无 | 有 |
| 前端 | Vite Dev Server | 静态文件 + Nginx |
| 适用场景 | 本地开发 | 线上部署 |

## 环境变量参考

### 必填项

| 变量 | 说明 | 示例 |
|------|------|------|
| `JWT_SECRET` | JWT 签名密钥 | `openssl rand -hex 32` 生成 |
| `POSTGRES_PASSWORD` | 数据库密码 | 强随机密码 |
| `MINIO_SECRET_KEY` | MinIO 密码 | 至少 8 位 |

### LLM 模型配置

至少配置一个模型提供商：

| 变量 | 提供商 | 网络要求 | 说明 |
|------|--------|---------|------|
| `ANTHROPIC_API_KEY` | Claude | 海外 API，需代理 | [获取 Key](https://console.anthropic.com/) |
| `DEEPSEEK_API_KEY` | DeepSeek | 海外 API，需代理 | [获取 Key](https://platform.deepseek.com/) |
| `QWEN_API_KEY` | 通义千问 | 国内直连，无需代理 | [获取 Key](https://dashscope.console.aliyun.com/) |
| `OLLAMA_BASE_URL` | Ollama 本地模型 | 本地，无需代理 | 默认 `http://localhost:11434` |

### 代理设置

如果使用海外 API（Anthropic、DeepSeek），需要配置代理：

| 变量 | 说明 | 示例 |
|------|------|------|
| `HTTP_PROXY` | HTTP 代理 | `http://127.0.0.1:1087` |
| `HTTPS_PROXY` | HTTPS 代理 | `http://127.0.0.1:1087` |

> Docker 容器内使用 `http://host.docker.internal:1087` 访问宿主机代理。

### 其他配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | `bridgeai` | 数据库名 |
| `POSTGRES_USER` | `bridgeai` | 数据库用户 |
| `MINIO_ACCESS_KEY` | `bridgeai` | MinIO 用户名 |
| `NGINX_HTTP_PORT` | `80` | Nginx 监听端口 |
| `DEBUG` | `false` | 调试模式 |

## 模型配置详情

### Claude (Anthropic)

```env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
HTTP_PROXY=http://host.docker.internal:1087
HTTPS_PROXY=http://host.docker.internal:1087
```

支持模型：`claude-sonnet-4-20250514`、`claude-haiku-4-20250514` 等。

### DeepSeek

```env
DEEPSEEK_API_KEY=sk-xxxxx
HTTP_PROXY=http://host.docker.internal:1087
HTTPS_PROXY=http://host.docker.internal:1087
```

支持模型：`deepseek-chat`、`deepseek-reasoner` 等。

### 通义千问 (Qwen)

```env
QWEN_API_KEY=sk-xxxxx
# 无需代理，国内直连
```

支持模型：`qwen-max`、`qwen-plus`、`qwen-turbo` 等。

### Ollama 本地模型

1. 安装 Ollama：
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

2. 拉取模型：
```bash
ollama pull llama3
ollama pull qwen2:7b
```

3. 配置：
```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

> 在 Docker 容器中访问宿主机 Ollama 需使用 `host.docker.internal`。

支持模型：取决于本地已安装的模型。

## 生产环境注意事项

### SSL/TLS 配置

`docker/nginx.conf` 中预留了 HTTPS 配置位置。生产环境建议：

1. 使用反向代理（如 Caddy/Traefik）在外层终止 TLS
2. 或在 nginx.conf 中配置 SSL 证书：

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    # ... 其余配置不变
}
```

### 数据备份

```bash
# 备份 PostgreSQL
docker compose exec postgres pg_dump -U bridgeai bridgeai > backup.sql

# 恢复
docker compose exec -T postgres psql -U bridgeai bridgeai < backup.sql
```

### 日志查看

```bash
# 所有服务
docker compose -f docker/docker-compose.prod.yml logs -f

# 单个服务
docker compose -f docker/docker-compose.prod.yml logs -f bridgeai-api
```

## 故障排查

### 服务无法启动

```bash
# 查看容器状态
docker compose -f docker/docker-compose.prod.yml ps

# 查看具体错误
docker compose -f docker/docker-compose.prod.yml logs bridgeai-api
```

### API 返回 502

- 检查后端是否启动完成：`docker compose logs bridgeai-api`
- 确认健康检查通过：`curl http://localhost:8000/api/v1/system/health`

### 模型调用失败

- **海外 API 超时**：检查代理配置 `HTTP_PROXY` / `HTTPS_PROXY`
- **通义千问报错**：确认 `QWEN_API_KEY` 正确，DashScope 控制台已开通服务
- **Ollama 连接失败**：确认 Ollama 服务运行中 (`ollama serve`)，Docker 中使用 `host.docker.internal`

### 数据库连接失败

- 确认 PostgreSQL 容器健康：`docker compose exec postgres pg_isready`
- 检查密码是否匹配 `.env` 中的 `POSTGRES_PASSWORD`
