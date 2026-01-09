import os

# 从环境变量读取配置，实现“一次配置，到处运行”
# 在 Docker 内部，host 必须填 docker-compose 中的服务名 'db'
DB_HOST = os.getenv("DB_HOST", "db") 
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "eve_sde_db")
DB_USER = os.getenv("DB_USER", "eve_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "kKoqmo1IR2husRe9J2y/zzpS") # 建议这里也用 os.getenv

# 数据库连接配置字典
DB_CONFIG = {
    "host": DB_HOST,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "connect_timeout": 10  # 增加超时控制，提高稳定性
}

# 数据存储目录
DATA_DIR = os.getenv("DATA_DIR", "data")
SDE_JSONL_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"