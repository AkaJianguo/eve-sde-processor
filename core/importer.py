import json
import psycopg2
import os
import logging
import re
from psycopg2.extras import execute_values
from config.settings import DB_CONFIG

# 配置日志
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')

class SDEImporter:
    def __init__(self):
        """初始化数据库连接"""
        try:
            # 使用来自 config.settings 的 DB_CONFIG (确保 host 为 'db' 或 'ruoyi-pg')
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False 
            logging.info("Successfully connected to PostgreSQL.")
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            raise

    def _camel_to_snake(self, name):
        """将 CamelCase 转换为 snake_case"""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def auto_import(self, file_path, batch_size=1000):
        """
        自动根据文件名创建表并批量导入 JSONL 数据到 raw 架构
        """
        base_name = os.path.basename(file_path).replace(".jsonl", "")
        
        # 转换表名逻辑：驼峰转下划线 (例如 invTypes -> inv_types)
        table_name = self._camel_to_snake(base_name)
        if base_name.startswith("_"):
            table_name = "_" + table_name

        cursor = self.conn.cursor()
        try:
            # 1. 确保架构存在并创建表
            cursor.execute("CREATE SCHEMA IF NOT EXISTS raw;")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS raw.{table_name} (
                    id TEXT PRIMARY KEY,
                    data JSONB
                );
            """)

            logging.info(f"🚀 开始导入数据到 [raw.{table_name}]...")
            
            batch_data = []
            count = 0

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    record = json.loads(line)
                    item_id = str(record.get("_key"))
                    
                    if item_id == "None":
                        continue
                    
                    # 准备批量插入的数据元组
                    batch_data.append((item_id, json.dumps(record)))
                    count += 1

                    # 达到批次大小后执行插入
                    if len(batch_data) >= batch_size:
                        self._execute_batch_upsert(cursor, table_name, batch_data)
                        batch_data = []
                        logging.info(f"  已处理 {count} 条记录...")

            # 插入剩余的数据
            if batch_data:
                self._execute_batch_upsert(cursor, table_name, batch_data)

            self.conn.commit()
            logging.info(f"✅ [raw.{table_name}] 导入完成，共计 {count} 条记录。")

        except Exception as e:
            self.conn.rollback()
            logging.error(f"❌ 导入 raw.{table_name} 失败: {e}")
            raise 
        finally:
            cursor.close()

    def _execute_batch_upsert(self, cursor, table_name, data_list):
        """执行批量 Upsert 逻辑"""
        insert_sql = f"""
            INSERT INTO raw.{table_name} (id, data)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data;
        """
        execute_values(cursor, insert_sql, data_list)

    def close(self):
        """显式关闭连接"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logging.info("Database connection closed.")

    def __del__(self):
        self.close()