import os
import requests
import zipfile
import json
import glob
import logging
import time
from datetime import datetime, timedelta
from config.settings import SDE_JSONL_URL, DATA_DIR
from core.importer import SDEImporter

# ==========================================
# 日志配置
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

VERSION_FILE = os.path.join(DATA_DIR, "current_version.txt")

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
        # 这里的 SDE_JSONL_URL 已经在 settings.py 中定义
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
    """后期加工：执行 ANALYZE 优化查询性能"""
    logging.info("开始数据库后期加工 (ANALYZE)...")
    try:
        with importer.conn.cursor() as cursor:
            # 这里的 importer.conn 对应 SDEImporter 里的连接
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'raw';")
            tables = cursor.fetchall()
            for table in tables:
                cursor.execute(f"ANALYZE raw.{table[0]};")
        importer.conn.commit()
        logging.info(f"✅ 后期加工完成：已优化 {len(tables)} 张表。")
    except Exception as e:
        logging.error(f"⚠️ 后期加工失败: {e}")
        importer.conn.rollback()

def refresh_business_views(importer):
    """自动执行 SQL 脚本刷新业务视图"""
    # 路径对齐：确保指向 Docker 容器内的脚本位置
    script_path = os.path.join(os.path.dirname(__file__), "scripts", "init_views.sql")
    if not os.path.exists(script_path):
        logging.warning(f"跳过视图刷新：找不到脚本文件 {script_path}")
        return
    
    logging.info("正在执行 SQL 脚本刷新业务视图...")
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        with importer.conn.cursor() as cursor:
            cursor.execute(sql_script)
        importer.conn.commit()
        logging.info("✅ 业务视图 (Public Schema) 已同步刷新。")
    except Exception as e:
        logging.error(f"⚠️ 刷新业务视图失败: {e}")
        importer.conn.rollback()

def perform_update_task():
    """单次完整更新任务逻辑"""
    importer = None
    zip_filename = None
    try:
        # 1. 检查版本
        latest_build = fetch_latest_build()
        local_build = get_local_version()
        
        if not latest_build:
            return

        if latest_build == local_build:
            logging.info(f"当前版本 {local_build} 已是最新，无需更新。")
            return
        
        logging.info(f"检测到新版本: {local_build if local_build else 'None'} -> {latest_build}")
        
        # 2. 只有在确定要更新时才初始化数据库连接，节省资源
        importer = SDEImporter()
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # 3. 下载
        zip_filename = f"sde_{latest_build}.zip"
        download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{latest_build}-jsonl.zip"
        
        logging.info(f"正在下载 SDE 构建版本 {latest_build}...")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(zip_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                
        # 4. 解压
        logging.info("正在解压数据...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        
        # 5. 遍历导入
        search_pattern = os.path.join(DATA_DIR, "**", "*.jsonl")
        sde_files = glob.glob(search_pattern, recursive=True)
        for file_path in sde_files:
            # 调用整合后带批量导入功能的 auto_import
            importer.auto_import(os.path.abspath(file_path))
        
        # 6. 后期维护
        run_post_processing(importer)
        refresh_business_views(importer)
        
        # 7. 更新本地版本锁
        save_local_version(latest_build)
        logging.info(f"--- 🚀 SDE 更新圆满成功：版本 {latest_build} ---")

    except Exception as e:
        logging.error(f"❌ 更新过程中发生严重错误: {e}")
    finally:
        # 清理工作
        if zip_filename and os.path.exists(zip_filename):
            os.remove(zip_filename)
        # 清理遗留的 jsonl 文件
        for j_file in glob.glob(os.path.join(DATA_DIR, "**", "*.jsonl"), recursive=True):
            try: os.remove(j_file)
            except: pass
        
        # 显式关闭数据库连接
        if importer:
            importer.close()

def main():
    logging.info("🚀 EVE SDE 自动更新守护进程已启动 (定时模式：每日 19:00)...")
    
    # 首次启动：如果没有版本记录，立刻执行一次
    if get_local_version() is None:
        logging.info("首次部署，检测到无本地版本记录，立刻执行初始数据导入...")
        perform_update_task()

    while True:
        now = datetime.now()
        target = now.replace(hour=19, minute=0, second=0, microsecond=0)
        
        if now >= target:
            target += timedelta(days=1)
            
        sleep_seconds = (target - now).total_seconds()
        logging.info(f"☕ 进入等待模式。下次检查：{target.strftime('%Y-%m-%d %H:%M:%S')} (约 {round(sleep_seconds/3600, 2)} 小时后)")
        
        time.sleep(sleep_seconds)
        
        logging.info("⏰ 到达预定时间，开始执行更新任务...")
        perform_update_task()

if __name__ == "__main__":
    main()