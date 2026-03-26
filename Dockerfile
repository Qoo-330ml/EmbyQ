# syntax=docker/dockerfile:1

# Stage 1: build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: runtime (lighter Python on Alpine)
FROM python:3.12-alpine
WORKDIR /app

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 最小系统依赖
RUN apk add --no-cache tzdata ca-certificates \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone

# Python deps（qoo-ip138）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App files
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY README.md ./
COPY VERSION ./
COPY ABOUT.md ./

# Frontend dist for SPA hosting
COPY --from=frontend-builder /frontend/dist ./frontend/dist

EXPOSE 5000
VOLUME ["/app/data"]
ENTRYPOINT ["python", "scripts/main.py"]
