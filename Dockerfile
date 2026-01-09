# 使用成熟稳定的 Python 3.11 版本
FROM python:3.11-slim

WORKDIR /app

# 安装 PostgreSQL 客户端库等必要依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码
COPY . .

# 启动命令：确保 main.py 是你的入口文件
CMD ["python", "main.py"]