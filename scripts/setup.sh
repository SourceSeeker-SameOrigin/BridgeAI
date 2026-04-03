#!/bin/bash
# ============================================================
# BridgeAI 一键部署脚本
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# ---------- 颜色输出 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "==========================================="
echo "  BridgeAI 安装向导"
echo "==========================================="
echo ""

# ---------- 依赖检查 ----------
check_command() {
    local cmd="$1"
    local hint="$2"
    if ! command -v "$cmd" &>/dev/null; then
        fail "$cmd 未安装。$hint"
    fi
    ok "$cmd 已安装: $(command -v "$cmd")"
}

info "检查系统依赖..."
check_command docker "请安装 Docker: https://docs.docker.com/get-docker/"
check_command openssl "请安装 openssl"

# 检查 docker compose (v2)
if docker compose version &>/dev/null; then
    ok "Docker Compose (v2) 已安装"
else
    fail "Docker Compose 未安装。请升级 Docker Desktop 或安装 docker-compose-plugin"
fi

# 检查 Docker 守护进程
if docker info &>/dev/null; then
    ok "Docker 守护进程运行中"
else
    fail "Docker 守护进程未运行。请先启动 Docker"
fi

echo ""

# ---------- 环境配置 ----------
info "配置环境变量..."

if [ ! -f .env ]; then
    cp .env.example .env

    # 生成随机 JWT 密钥
    JWT_SECRET=$(openssl rand -hex 32)
    # 生成随机数据库密码
    PG_PASSWORD=$(openssl rand -hex 16)
    # 生成随机 MinIO 密码
    MINIO_PASSWORD=$(openssl rand -hex 16)

    # macOS 和 Linux 的 sed 兼容写法
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|JWT_SECRET=change-me-to-a-random-string|JWT_SECRET=$JWT_SECRET|" .env
        sed -i '' "s|POSTGRES_PASSWORD=change-me-strong-password|POSTGRES_PASSWORD=$PG_PASSWORD|" .env
        sed -i '' "s|MINIO_SECRET_KEY=change-me-strong-password|MINIO_SECRET_KEY=$MINIO_PASSWORD|" .env
    else
        sed -i "s|JWT_SECRET=change-me-to-a-random-string|JWT_SECRET=$JWT_SECRET|" .env
        sed -i "s|POSTGRES_PASSWORD=change-me-strong-password|POSTGRES_PASSWORD=$PG_PASSWORD|" .env
        sed -i "s|MINIO_SECRET_KEY=change-me-strong-password|MINIO_SECRET_KEY=$MINIO_PASSWORD|" .env
    fi

    ok ".env 文件已生成并配置了随机密钥"
    warn "请编辑 .env 文件配置 LLM API Keys（至少配置一个）"
    echo ""
    echo "  可用模型提供商:"
    echo "    - ANTHROPIC_API_KEY  : Claude (需要代理)"
    echo "    - DEEPSEEK_API_KEY   : DeepSeek (需要代理)"
    echo "    - QWEN_API_KEY       : 通义千问 (国内直连)"
    echo "    - OLLAMA_BASE_URL    : Ollama 本地模型 (无需 Key)"
    echo ""

    read -p "是否现在编辑 .env 文件? [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        ${EDITOR:-vi} .env
    fi
else
    ok ".env 文件已存在，跳过生成"
fi

echo ""

# ---------- 选择部署模式 ----------
info "选择部署模式:"
echo "  1) 开发模式 (热重载，适合本地开发)"
echo "  2) 生产模式 (多副本，nginx 反向代理)"
echo ""
read -p "请选择 [1/2，默认 1]: " -n 1 -r DEPLOY_MODE
echo ""

COMPOSE_CMD="docker compose --env-file .env"

if [[ "$DEPLOY_MODE" == "2" ]]; then
    info "使用生产模式启动..."
    COMPOSE_FILE="-f docker/docker-compose.prod.yml"
else
    info "使用开发模式启动..."
    COMPOSE_FILE="-f docker/docker-compose.yml -f docker/docker-compose.dev.yml"
fi

# ---------- 构建并启动 ----------
info "构建并启动服务..."
$COMPOSE_CMD $COMPOSE_FILE up -d --build

echo ""
info "等待服务启动..."

# 健康检查循环
MAX_WAIT=120
WAIT=0
API_URL="http://localhost:8000/api/v1/system/health"

if [[ "$DEPLOY_MODE" == "2" ]]; then
    API_URL="http://localhost:${NGINX_HTTP_PORT:-80}/api/v1/system/health"
fi

while [ $WAIT -lt $MAX_WAIT ]; do
    if curl -sf "$API_URL" &>/dev/null; then
        break
    fi
    sleep 3
    WAIT=$((WAIT + 3))
    echo -n "."
done
echo ""

if [ $WAIT -ge $MAX_WAIT ]; then
    warn "服务启动超时，请检查日志:"
    echo "  $COMPOSE_CMD $COMPOSE_FILE logs"
    exit 1
fi

echo ""
echo "==========================================="
echo "  BridgeAI 启动成功!"
echo "==========================================="
echo ""

if [[ "$DEPLOY_MODE" == "2" ]]; then
    echo "  应用:     http://localhost:${NGINX_HTTP_PORT:-80}"
    echo "  API 文档: http://localhost:${NGINX_HTTP_PORT:-80}/docs"
else
    echo "  前端:     http://localhost:5173"
    echo "  API:      http://localhost:8000"
    echo "  API 文档: http://localhost:8000/docs"
fi

echo "  MinIO:    http://localhost:9001"
echo ""
echo "  查看日志: $COMPOSE_CMD $COMPOSE_FILE logs -f"
echo "  停止服务: $COMPOSE_CMD $COMPOSE_FILE down"
echo ""
