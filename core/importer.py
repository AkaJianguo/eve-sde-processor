import json
import psycopg2
import os
from config.settings import DB_CONFIG

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
        自动根据文件名创建表并导入 JSONL 数据
        支持文本主键以兼容 _sde.jsonl 等元数据文件
        """
        base_name = os.path.basename(file_path).replace(".jsonl", "")
        
        # 转换表名逻辑：驼峰转下划线
        # 特殊处理：保留开头的下划线（如 _sde -> _sde）
        table_name = "".join(["_" + c.lower() if c.isupper() else c for c in base_name]).lstrip("_")
        if base_name.startswith("_"):
            table_name = "_" + table_name

        cursor = self.conn.cursor()
        try:
            # 关键修复：使用 TEXT PRIMARY KEY
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id TEXT PRIMARY KEY,
                    data JSONB
                );
            """)

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    record = json.loads(line)
                    # 关键修复：强制转换为字符串，兼容 "sde" 或 12345
                    item_id = str(record.get("_key"))
                    
                    if item_id == "None":
                        continue
                    
                    # 插入或更新逻辑
                    insert_sql = f"""
                        INSERT INTO {table_name} (id, data)
                        VALUES (%s, %s)
                        ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data;
                    """
                    cursor.execute(insert_sql, (item_id, json.dumps(record)))

            self.conn.commit()
            print(f"✅ Table [{table_name}]: Import completed.")

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error importing {table_name}: {e}")
            raise 
        finally:
            cursor.close()

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()