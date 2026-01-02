import json
import psycopg2
import os
from config.settings import DB_CONFIG

class SDEImporter:
    def __init__(self):
        """初始化数据库连接"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False  # 使用事务控制，方便出错回滚
            print("数据库连接成功。")
        except Exception as e:
            print(f"无法连接到数据库: {e}")
            raise

    def auto_import(self, file_path):
        """
        自动根据文件名创建表并导入 JSONL 数据
        例如: mapRegions.jsonl -> table: map_regions
        """
        # 1. 从文件名生成表名 (驼峰转下划线)
        base_name = os.path.basename(file_path).replace(".jsonl", "")
        # 处理特殊情况或直接转换，例如 mapRegions -> map_regions
        table_name = "".join(["_" + c.lower() if c.isupper() else c for c in base_name]).lstrip("_")
        
        # 修正：如果文件名本身已经是全小写或有特殊命名，这里做微调
        if table_name == "types": table_name = "inv_types" # 可选：匹配官方常用命名

        print(f"正在处理文件: {base_name} -> 目标表: {table_name}")

        cursor = self.conn.cursor()
        try:
            # 2. 创建表结构 (id + jsonb 数据)
            # 使用 IF NOT EXISTS 防止重复创建
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id BIGINT PRIMARY KEY,
                data JSONB
            );
            """
            cursor.execute(create_table_sql)

            # 3. 读取并插入数据
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    record = json.loads(line)
                    # 假设 JSONL 的 key 是 ID，值是内容
                    # 或者 SDE JSONL 通常格式为 {"_key": 123, ...内容}
                    item_id = record.get("_key")
                    if item_id is None:
                        continue
                    
                    # 插入或更新
                    insert_sql = f"""
                    INSERT INTO {table_name} (id, data)
                    VALUES (%s, %s)
                    ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data;
                    """
                    cursor.execute(insert_sql, (item_id, json.dumps(record)))

            self.conn.commit()
            print(f"✅ {table_name} 导入成功。")

        except Exception as e:
            self.conn.rollback()
            print(f"❌ 导入 {table_name} 时出错，已跳过并重置连接: {e}")
            raise e
        finally:
            cursor.close()

    def __del__(self):
        """析构函数：关闭连接"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()