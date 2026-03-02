# 使用官方Python基础镜像
FROM python:3.12-alpine

# 设置工作目录
WORKDIR /app

# 复制脚本文件和空数据目录结构
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY templates/ ./templates/

# 安装依赖（请先创建requirements.txt）
COPY requirements.txt .

# 安装依赖（请先创建requirements.txt）
RUN pip install --no-cache-dir -r requirements.txt

# 复制并安装 ip138 IP归属地查询工具
COPY ip138/ ./ip138/
RUN pip install --no-cache-dir ./ip138/

# 暴露Web服务器端口
EXPOSE 5000

# 声明数据卷（容器启动时需映射到宿主机）
VOLUME /app/data

# 使用 ENTRYPOINT 确保每次启动都运行脚本
ENTRYPOINT ["python", "scripts/main.py"]
