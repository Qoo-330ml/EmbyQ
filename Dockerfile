# syntax=docker/dockerfile:1

# Stage 1: build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: runtime
FROM python:3.12-alpine
WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App files
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY ip138/ ./ip138/
RUN pip install --no-cache-dir ./ip138/

# Frontend dist for SPA hosting
COPY --from=frontend-builder /frontend/dist ./frontend/dist

EXPOSE 5000
VOLUME /app/data
ENTRYPOINT ["python", "scripts/main.py"]
