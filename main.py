import os
import requests
import zipfile
import json
import glob
import logging
import time
from datetime import datetime, timedelta
from config.settings import SDE_JSONL_URL, DATA_DIR, API_SECRET_KEY
from core.importer import SDEImporter

# ==========================================
# 配置与常量 (建议同步更新 settings.py)
# ==========================================
# FastAPI 缓存刷新接口地址 (根据你的 Docker 网络或域名调整)
API_REFRESH_URL = os.getenv("API_REFRESH_URL", "http://fastapi-app:8000/internal/refresh-market-cache")

VERSION_FILE = os.path.join(DATA_DIR, "current_version.txt")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ==========================================
# 工具函数
# ==========================================

def get_local_version():
    """读取本地存储的 SDE 构建版本"""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_local_version(build_num):
    """保存当前已完成导入的版本"""
    with open(VERSION_FILE, 'w') as f:
        f.write(str(build_num))

def fetch_latest_build():
    """连接 EVE 服务器检查最新的 SDE 构建版本"""
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

def notify_api_service():
    """数据更新完成后，通知 FastAPI 服务清理内存缓存"""
    logging.info(f"🚀 准备通知 API 服务刷新缓存: {API_REFRESH_URL}")
    try:
        headers = {"X-Internal-Token": API_SECRET_KEY}
        # 发送 POST 请求触发 FastAPI 的 .cache_clear()
        response = requests.post(API_REFRESH_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            logging.info("✅ API 服务响应：内存缓存已重置，新数据已生效。")
        else:
            logging.warning(f"⚠️ API 服务响应异常: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"❌ 无法连接到 API 服务进行刷新: {e}")

# ==========================================
# 数据库后期处理逻辑
# ==========================================

def run_post_processing(importer):
    """后期加工：执行 ANALYZE 优化 PostgreSQL 查询计划"""
    logging.info("开始数据库后期加工 (ANALYZE)...")
    try:
        with importer.conn.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'raw';")
            tables = cursor.fetchall()
            for table in tables:
                cursor.execute(f"ANALYZE raw.{table[0]};")
        importer.conn.commit()
        logging.info(f"✅ 后期加工完成：已优化 {len(tables)} 张原始数据表。")
    except Exception as e:
        logging.error(f"⚠️ 后期加工失败: {e}")
        importer.conn.rollback()

def refresh_business_views(importer):
    """自动执行 SQL 脚本刷新业务视图及物化视图"""
    script_path = os.path.join(os.path.dirname(__file__), "scripts", "init_views.sql")
    if not os.path.exists(script_path):
        logging.warning(f"跳过视图刷新：找不到脚本文件 {script_path}")
        return
    
    logging.info("正在执行 SQL 脚本刷新业务视图及物化视图...")
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        with importer.conn.cursor() as cursor:
            # 执行包含 REFRESH MATERIALIZED VIEW 的 SQL 脚本
            cursor.execute(sql_script)
        importer.conn.commit()
        logging.info("✅ 业务视图与市场菜单物化视图已同步刷新。")
    except Exception as e:
        logging.error(f"⚠️ 刷新业务视图失败: {e}")
        importer.conn.rollback()

# ==========================================
# 任务调度核心
# ==========================================

def perform_update_task():
    """单次完整更新任务逻辑：检查 -> 下载 -> 导入 -> 刷新 -> 通知"""
    importer = None
    zip_filename = None
    try:
        # 1. 版本比对
        latest_build = fetch_latest_build()
        local_build = get_local_version()
        
        if not latest_build:
            logging.warning("未能获取到远程版本，跳过本次更新。")
            return

        if latest_build == local_build:
            logging.info(f"当前版本 {local_build} 已是最新，无需更新。")
            return
        
        logging.info(f"检测到新版本: {local_build if local_build else 'None'} -> {latest_build}")
        
        # 2. 初始化导入器并准备环境
        importer = SDEImporter()
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # 3. 下载 SDE 压缩包
        zip_filename = f"sde_{latest_build}.zip"
        download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{latest_build}-jsonl.zip"
        
        logging.info(f"正在下载 SDE 构建版本 {latest_build}...")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(zip_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                
        # 4. 解压 JSONL 文件
        logging.info("正在解压数据...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        
        # 5. 遍历并导入所有 JSONL 数据到 raw 架构
        search_pattern = os.path.join(DATA_DIR, "**", "*.jsonl")
        sde_files = glob.glob(search_pattern, recursive=True)
        logging.info(f"发现 {len(sde_files)} 个数据文件，准备导入...")
        for file_path in sde_files:
            importer.auto_import(os.path.abspath(file_path))
        
        # 6. 后期数据库优化与业务视图转换
        run_post_processing(importer)
        refresh_business_views(importer)
        
        # 7. 更新本地版本标识
        save_local_version(latest_build)
        
        # 8. 【核心环节】数据已准备就绪，通知 FastAPI 刷新内存缓存
        notify_api_service()
        
        logging.info(f"--- 🚀 SDE 更新圆满成功：版本 {latest_build} ---")

    except Exception as e:
        logging.error(f"❌ 更新过程中发生严重错误: {e}")
    finally:
        # 善后工作：清理临时文件
        if zip_filename and os.path.exists(zip_filename):
            os.remove(zip_filename)
        for j_file in glob.glob(os.path.join(DATA_DIR, "**", "*.jsonl"), recursive=True):
            try: os.remove(j_file)
            except: pass
        
        if importer:
            importer.close()

def main():
    logging.info("🚀 EVE SDE 自动更新守护进程已启动 (每日 19:00 运行)...")
    
    # 首次部署检查
    if get_local_version() is None:
        logging.info("首次部署，检测到无本地版本记录，立刻执行初始数据导入...")
        perform_update_task()

    while True:
        now = datetime.now()
        # 设定每天晚上 19:00 执行
        target = now.replace(hour=19, minute=0, second=0, microsecond=0)
        
        if now >= target:
            target += timedelta(days=1)
            
        sleep_seconds = (target - now).total_seconds()
        logging.info(f"☕ 等待中。下次检查：{target.strftime('%Y-%m-%d %H:%M:%S')} (约 {round(sleep_seconds/3600, 2)} 小时后)")
        
        time.sleep(sleep_seconds)
        
        logging.info("⏰ 到达预定时间，开始执行更新检查...")
        perform_update_task()

if __name__ == "__main__":
    main()