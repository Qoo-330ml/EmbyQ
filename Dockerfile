# syntax=docker/dockerfile:1

# Stage 1: build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: runtime (Python + Playwright + Chromium)
FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy
WORKDIR /app

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git tzdata \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install ip_hiofd directly from GitHub (public repo)
RUN pip install --no-cache-dir git+https://github.com/Qoo-330ml/IP-hiofd.git@main

# App files
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY ip138/ ./ip138/
RUN pip install --no-cache-dir ./ip138/

# Frontend dist for SPA hosting
COPY --from=frontend-builder /frontend/dist ./frontend/dist

EXPOSE 5000
VOLUME ["/app/data"]
ENTRYPOINT ["python", "scripts/main.py"]
