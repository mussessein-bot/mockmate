#!/bin/bash
# MockMate 一键启动脚本
# 功能：启动前后端 + Cloudflare tunnel，输出别人可以直接访问的 URL

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
ENV_FILE="$ROOT/.env"
FRONTEND_ENV="$FRONTEND_DIR/.env.local"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PIDS=()

cleanup() {
  echo ""
  echo "正在关闭所有服务..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  rm -f "$BACKEND_TUNNEL_LOG" "$FRONTEND_TUNNEL_LOG"
  echo "已关闭。"
}
trap cleanup EXIT INT TERM

# 等待 tunnel URL 出现在日志文件中（最多 30 秒）
wait_for_tunnel_url() {
  local logfile="$1"
  for i in $(seq 1 30); do
    local url
    url=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$logfile" 2>/dev/null | head -1)
    if [ -n "$url" ]; then
      echo "$url"
      return 0
    fi
    sleep 1
  done
  return 1
}

BACKEND_TUNNEL_LOG=$(mktemp)
FRONTEND_TUNNEL_LOG=$(mktemp)

echo "========================================"
echo "  MockMate 启动中..."
echo "========================================"

# ── Step 1：后端 tunnel ──────────────────────
echo ""
echo "⏳ [1/4] 建立后端 tunnel..."
HTTPS_PROXY=http://127.0.0.1:7890 cloudflared tunnel --url http://localhost:8000 \
  >"$BACKEND_TUNNEL_LOG" 2>&1 &
PIDS+=($!)

BACKEND_TUNNEL_URL=$(wait_for_tunnel_url "$BACKEND_TUNNEL_LOG") || {
  echo -e "${RED}❌ 后端 tunnel 失败，请检查 cloudflared 和代理设置${NC}"
  exit 1
}
echo -e "${GREEN}✅ 后端 tunnel：$BACKEND_TUNNEL_URL${NC}"

# 更新 .env 的 BACKEND_URL
if grep -q "^BACKEND_URL=" "$ENV_FILE" 2>/dev/null; then
  sed -i '' "s|^BACKEND_URL=.*|BACKEND_URL=$BACKEND_TUNNEL_URL|" "$ENV_FILE"
else
  echo "BACKEND_URL=$BACKEND_TUNNEL_URL" >> "$ENV_FILE"
fi

# ── Step 2：启动后端 ─────────────────────────
echo ""
echo "⏳ [2/4] 启动后端..."
cd "$BACKEND_DIR"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
PIDS+=($!)

# 等待后端就绪
for i in $(seq 1 15); do
  curl -s http://localhost:8000/docs > /dev/null 2>&1 && break
  sleep 1
done
echo -e "${GREEN}✅ 后端已启动（localhost:8000）${NC}"

# ── Step 3：更新前端配置，启动前端 ────────────
echo ""
echo "⏳ [3/4] 启动前端..."

# 写入前端 .env.local，让浏览器知道后端在哪
cat > "$FRONTEND_ENV" <<EOF
NEXT_PUBLIC_API_URL=$BACKEND_TUNNEL_URL
NEXT_PUBLIC_AUDIO_URL=$BACKEND_TUNNEL_URL
EOF

cd "$FRONTEND_DIR"
npm run dev -- --port 3001 &
PIDS+=($!)

# 等待前端 Next.js 编译完成
for i in $(seq 1 30); do
  curl -s http://localhost:3001 > /dev/null 2>&1 && break
  sleep 1
done
echo -e "${GREEN}✅ 前端已启动（localhost:3001）${NC}"

# ── Step 4：前端 tunnel ──────────────────────
echo ""
echo "⏳ [4/4] 建立前端 tunnel..."
HTTPS_PROXY=http://127.0.0.1:7890 cloudflared tunnel --url http://localhost:3001 \
  >"$FRONTEND_TUNNEL_LOG" 2>&1 &
PIDS+=($!)

FRONTEND_TUNNEL_URL=$(wait_for_tunnel_url "$FRONTEND_TUNNEL_LOG") || {
  echo -e "${RED}❌ 前端 tunnel 失败${NC}"
  exit 1
}

# ── 完成 ─────────────────────────────────────
echo ""
echo "========================================"
echo -e "${GREEN}  🎉 MockMate 已就绪！${NC}"
echo "========================================"
echo ""
echo -e "  👥 分享给别人：${YELLOW}$FRONTEND_TUNNEL_URL${NC}"
echo ""
echo "  本地调试："
echo "    前端  → http://localhost:3001"
echo "    后端  → http://localhost:8000"
echo "    文档  → http://localhost:8000/docs"
echo ""
echo "  按 Ctrl+C 关闭所有服务"
echo "========================================"

# 阻塞，等待任意子进程退出（异常退出时 cleanup 自动触发）
wait
