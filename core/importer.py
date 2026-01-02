import json
import psycopg2
import os
from config.settings import DB_CONFIG
import logging # 增加导入
class SDEImporter:
    def __init__(self):
        """初始化数据库连接"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False 
            print("Successfully connected to PostgreSQL.")
        except Exception as e:
            print(f"Database connection failed: {e}")
            raise

    def auto_import(self, file_path):
        """
        自动根据文件名创建表并导入 JSONL 数据到 raw 架构
        """
        base_name = os.path.basename(file_path).replace(".jsonl", "")
        
        # 转换表名逻辑：驼峰转下划线
        table_name = "".join(["_" + c.lower() if c.isupper() else c for c in base_name]).lstrip("_")
        if base_name.startswith("_"):
            table_name = "_" + table_name

        cursor = self.conn.cursor()
        try:
            # --- 关键修改：在表名前强制加上 raw. 前缀 ---
            
            # 1. 建表时指定架构为 raw
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS raw.{table_name} (
                    id TEXT PRIMARY KEY,
                    data JSONB
                );
            """)

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    record = json.loads(line)
                    item_id = str(record.get("_key"))
                    
                    if item_id == "None":
                        continue
                    
                    # 2. 插入或更新时也必须指向 raw.{table_name}
                    insert_sql = f"""
                        INSERT INTO raw.{table_name} (id, data)
                        VALUES (%s, %s)
                        ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data;
                    """
                    cursor.execute(insert_sql, (item_id, json.dumps(record)))

            self.conn.commit()
            logging.info(f"✅ Table [raw.{table_name}]: 导入完成。")

        except Exception as e:
            self.conn.rollback()
            logging.error(f"❌ 导入 raw.{table_name} 失败: {e}")
            raise 
        finally:
            cursor.close()

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()