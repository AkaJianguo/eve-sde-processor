import os
import requests
import zipfile
import json
import glob
import logging  # 引入日志模块
from config.settings import SDE_JSONL_URL, DATA_DIR
from core.importer import SDEImporter

# ==========================================
# 日志配置：[时间] [级别] 消息
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

VERSION_FILE = "current_version.txt"

def get_local_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_local_version(build_num):
    with open(VERSION_FILE, 'w') as f:
        f.write(str(build_num))

def fetch_latest_build():
    logging.info("正在连接 EVE 服务器检查 SDE 版本...")
    try:
        response = requests.get(SDE_JSONL_URL, timeout=15)
        response.raise_for_status()
        for line in response.text.splitlines():
            data = json.loads(line)
            if data.get("_key") == "sde":
                return str(data.get("buildNumber"))
    except Exception as e:
        logging.error(f"版本检查失败: {e}")
    return None

def run_post_processing(importer):
    logging.info("开始数据库后期加工 (ANALYZE)...")
    try:
        with importer.conn.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'raw';")
            tables = cursor.fetchall()
            for table in tables:
                cursor.execute(f"ANALYZE raw.{table[0]};")
        importer.conn.commit()
        logging.info(f"✅ 后期加工完成：已优化 {len(tables)} 张表。")
    except Exception as e:
        logging.error(f"⚠️ 后期加工失败: {e}")
        importer.conn.rollback()

def main():
    # 1. 初始化
    importer = SDEImporter()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 2. 版本检查
    latest_build = fetch_latest_build()
    local_build = get_local_version()
    
    if not latest_build:
        logging.warning("未能获取到远程版本号，跳过更新。")
        return

    if latest_build == local_build:
        logging.info(f"当前版本 {local_build} 已是最新，无需更新。")
        return
    
    logging.info(f"检测到新版本: {local_build if local_build else 'None'} -> {latest_build}")
    
    # 3. 下载与导入
    zip_filename = f"sde_{latest_build}.zip"
    download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{latest_build}-jsonl.zip"
    
    try:
        logging.info(f"正在下载 SDE 构建版本 {latest_build}...")
        r = requests.get(download_url, stream=True)
        with open(zip_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logging.info("正在解压数据到 /data 目录...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        
        # C. 【关键修改】递归查找所有子目录下的 jsonl 文件
        # 使用 **/*.jsonl 并设置 recursive=True
        search_pattern = os.path.join(DATA_DIR, "**", "*.jsonl")
        sde_files = glob.glob(search_pattern, recursive=True)
        
        logging.info(f"找到 {len(sde_files)} 个文件。开始导入...")
        
        for file_path in sde_files:
            try:
                # 【关键修改】使用绝对路径，防止 open() 找不到文件
                abs_path = os.path.abspath(file_path)
                importer.auto_import(abs_path)
            except Exception as e:
                logging.error(f"导入 {file_path} 时发生错误: {e}")
        # 4. 执行加工逻辑
        run_post_processing(importer)
        
        save_local_version(latest_build)
        logging.info(f"--- 🚀 SDE 更新圆满成功：版本 {latest_build} ---")

    except Exception as e:
        logging.error(f"❌ 更新过程中发生严重错误: {e}")
        
    finally:
        # 5. 清理磁盘
        logging.info("正在执行磁盘清理...")
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        for j_file in glob.glob(os.path.join(DATA_DIR, "*.jsonl")):
            os.remove(j_file)
        logging.info("清理完成。")

if __name__ == "__main__":
    main()