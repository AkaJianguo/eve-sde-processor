# 使用 Python 3.11-slim 保持生产环境稳定
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    DATA_DIR=/app/data

WORKDIR /app

# 1. 安装系统依赖 (libpq-dev 用于 PostgreSQL 连接)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. 准备目录与用户安全
# 创建数据存放目录和脚本目录，并添加非 root 用户
RUN mkdir -p /app/data /app/scripts && \
    useradd -m eveuser && \
    chown -R eveuser:eveuser /app

# 3. 安装 Python 依赖
COPY --chown=eveuser:eveuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制项目文件
COPY --chown=eveuser:eveuser . .

# 切换到安全用户
USER eveuser

# 启动守护进程
CMD ["python", "main.py"]