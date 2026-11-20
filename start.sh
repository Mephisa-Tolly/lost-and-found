# start.sh — Linux / macOS / 云平台启动脚本
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if ! python3 -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[1/3] 安装 Python 依赖……"
  python3 -m pip install -r requirements.txt --quiet
fi

# 仓库里不保存前端构建产物，本地直接 clone 下来时需要先构建一次
if [ ! -f "frontend/dist/index.html" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[2/3] 未找到 frontend/dist，正在构建前端……"
    (cd frontend && npm install --no-audit --no-fund --silent && npm run build --silent)
  else
    echo "[2/3] 警告：没有 frontend/dist，也没装 Node.js，页面将无法打开"
    echo "      请安装 Node.js 20+ 后执行：cd frontend && npm install && npm run build"
  fi
fi

echo "[3/3] 启动服务，端口 ${PORT:-8000}"
exec python3 backend/main.py
