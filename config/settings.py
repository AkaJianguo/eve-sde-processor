import os
from dotenv import load_dotenv

# 加载本地 .env 文件（仅用于本地开发，Docker 环境下会自动读取）
load_dotenv()

# --- 数据库配置 ---
# 默认 host 设为 'db'，对应 docker-compose 中的服务名
DB_HOST = os.getenv("DB_HOST", "db") 
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "eve_sde_db")
DB_USER = os.getenv("DB_USER", "eve_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# 数据库连接字典
DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "connect_timeout": 10
}

# --- SDE 路径配置 ---
# DATA_DIR 必须与 Dockerfile 中的 ENV DATA_DIR 以及 docker-compose 中的 volumes 路径一致
DATA_DIR = os.getenv("DATA_DIR", "data")

# SDE 索引元数据地址
SDE_JSONL_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"