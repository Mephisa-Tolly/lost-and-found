# 校园智能失物招领匹配系统 v3.0
# 两阶段构建：前端在镜像里现构建，仓库中不再保存 frontend/dist。
# （dist 的文件名带内容哈希，提交进仓库只会随着每次改代码不断堆积旧文件）

# ---------- 阶段 1：构建前端 ----------
FROM node:20-slim AS web
WORKDIR /web

# 先只拷依赖清单，代码变动时能命中缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 依赖单独装一层，改代码不会重复安装
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY . /app
# 用镜像内构建出的产物覆盖（本地没有 dist 也能正常部署）
COPY --from=web /web/dist /app/frontend/dist

# 数据库与上传图片放在可写目录；云平台挂持久磁盘时把 DB_PATH 指到挂载点
RUN mkdir -p /app/data

EXPOSE 8000

# 云平台通过 PORT 环境变量指定端口，main.py 已读取
CMD ["python", "backend/main.py"]
