#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

cleanup() {
  echo ""
  echo "正在停止所有服务..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  echo "已停止"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "=========================================="
echo "  RAG 知识库管理系统 - 一键启动"
echo "=========================================="

# --- 后端 ---
echo ""
echo "▶ 启动后端 (FastAPI @ http://localhost:8000) ..."
cd "$BACKEND_DIR"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# --- 前端 ---
echo "▶ 启动前端 (Vite   @ http://localhost:3000) ..."
cd "$FRONTEND_DIR"
npx vite --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "  ✅ 服务已启动"
echo "  后端 API:  http://localhost:8000"
echo "  API 文档:  http://localhost:8000/api/docs"
echo "  前端页面:  http://localhost:3000"
echo "  登录账号:  admin / admin123"
echo "=========================================="
echo "  按 Ctrl+C 停止所有服务"
echo ""

wait
