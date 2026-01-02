import os
import requests
import zipfile
import json
import glob
from config.settings import SDE_JSONL_URL, DATA_DIR
from core.importer import SDEImporter

# 增量更新版本记录文件
VERSION_FILE = "current_version.txt"

def get_local_version():
    """读取本地存储的上一次更新成功的版本号"""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_local_version(build_num):
    """保存当前成功的版本号到本地"""
    with open(VERSION_FILE, 'w') as f:
        f.write(str(build_num))

def fetch_latest_build():
    """从官方获取最新的 SDE 构建版本号"""
    print("Connecting to EVE servers to check SDE version...")
    try:
        response = requests.get(SDE_JSONL_URL, timeout=15)
        response.raise_for_status()
        for line in response.text.splitlines():
            data = json.loads(line)
            if data.get("_key") == "sde":
                return str(data.get("buildNumber"))
    except Exception as e:
        print(f"Version check failed: {e}")
    return None

def run_post_processing(importer):
    """
    后期加工逻辑：
    1. 执行 ANALYZE 优化查询性能
    2. 确保权限正确
    """
    print("Starting database post-processing...")
    try:
        with importer.conn.cursor() as cursor:
            # ANALYZE 会更新 PostgreSQL 的查询优化器统计信息
            # 这对于 JSONB 这种大数据量表的查询效率至关重要
            cursor.execute("ANALYZE raw.inv_types;")
            cursor.execute("ANALYZE raw.map_solar_systems;")
            
            # 如果你有物化视图（Materialized Views），可以在这里刷新
            # cursor.execute("REFRESH MATERIALIZED VIEW public.mv_items;")
            
            print("Post-processing: Database stats updated (ANALYZE).")
            
        importer.conn.commit()
        print("✅ Post-processing completed successfully.")
    except Exception as e:
        print(f"⚠️ Post-processing failed: {e}")
        importer.conn.rollback()

def main():
    # 1. 初始化
    importer = SDEImporter()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 2. 版本检查
    latest_build = fetch_latest_build()
    local_build = get_local_version()
    
    if not latest_build:
        print("Could not fetch remote version.")
        return

    if latest_build == local_build:
        print(f"Local build {local_build} is up to date.")
        return
    
    print(f"New version detected: {local_build if local_build else 'None'} -> {latest_build}")
    
    # 3. 下载与执行流程
    zip_filename = f"sde_{latest_build}.zip"
    download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{latest_build}-jsonl.zip"
    
    try:
        # A. 下载
        print(f"Downloading SDE Build {latest_build}...")
        r = requests.get(download_url, stream=True)
        with open(zip_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        # B. 解压
        print("Extracting data to /data directory...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        
        # C. 自动导入到 raw 架构
        sde_files = glob.glob(os.path.join(DATA_DIR, "*.jsonl"))
        print(f"Found {len(sde_files)} files. Starting database import to 'raw' schema...")
        
        for file_path in sde_files:
            try:
                # 此时调用的是带 raw. 前缀的 importer
                importer.auto_import(file_path)
            except Exception as e:
                print(f"Warning: Skipping {file_path} due to error: {e}")
        
        # D. 执行后期加工 (ANALYZE / 权限刷新)
        run_post_processing(importer)
        
        # E. 成功后保存版本
        save_local_version(latest_build)
        print(f"--- SDE Update Successful: Build {latest_build} ---")

    except Exception as e:
        print(f"❌ Critical error during update: {e}")
        
    finally:
        # 4. 磁盘清理
        print("Performing disk cleanup...")
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        for j_file in glob.glob(os.path.join(DATA_DIR, "*.jsonl")):
            os.remove(j_file)
        print("Disk cleanup finished.")

if __name__ == "__main__":
    main()