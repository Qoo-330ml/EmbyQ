# syntax=docker/dockerfile:1

# Stage 1: build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: runtime (slim Python + Playwright Chromium only)
FROM python:3.11-slim-bookworm
WORKDIR /app

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 仅保留必要系统依赖，避免 Playwright 官方全家桶镜像过大
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        tzdata \
        ca-certificates \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# Python deps（含 playwright / ip-hiofd / qoo-ip138）
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

# App files
COPY scripts/ ./scripts/
COPY data/ ./data/

# Frontend dist for SPA hosting
COPY --from=frontend-builder /frontend/dist ./frontend/dist

EXPOSE 5000
VOLUME ["/app/data"]
ENTRYPOINT ["python", "scripts/main.py"]
