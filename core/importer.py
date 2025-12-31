import os
import requests
import zipfile
import json
import glob
import shutil
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
    print("正在连接官方服务器检查 SDE 版本...")
    try:
        response = requests.get(SDE_JSONL_URL, timeout=15)
        response.raise_for_status()
        for line in response.text.splitlines():
            data = json.loads(line)
            if data.get("_key") == "sde":
                return str(data.get("buildNumber"))
    except Exception as e:
        print(f"检查版本失败: {e}")
    return None

def main():
    # 1. 初始化检查
    importer = SDEImporter()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 2. 版本比对 (增量逻辑核心)
    latest_build = fetch_latest_build()
    local_build = get_local_version()
    
    if not latest_build:
        print("无法获取远程版本，请检查网络连接。")
        return

    if latest_build == local_build:
        print(f"当前版本 {local_build} 已是最新，无需更新。")
        return
    
    print(f"发现新版本: {local_build if local_build else 'None'} -> {latest_build}")
    
    # 3. 下载流程
    zip_filename = f"sde_{latest_build}.zip"
    download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{latest_build}-jsonl.zip"
    
    try:
        print(f"开始下载 SDE Build {latest_build}...")
        r = requests.get(download_url, stream=True)
        with open(zip_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        # 4. 解压逻辑
        print("正在解压数据到 data 目录...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        
        # 5. 全自动导入 54 个文件
        sde_files = glob.glob(os.path.join(DATA_DIR, "*.jsonl"))
        print(f"共发现 {len(sde_files)} 个数据文件，开始导入数据库...")
        
        for file_path in sde_files:
            try:
                importer.auto_import(file_path)
            except Exception as e:
                print(f"警告：{file_path} 导入中断，已尝试回滚并继续。")
        
        # 6. 更新版本记录
        save_local_version(latest_build)
        print(f"--- SDE 更新成功，当前版本: {latest_build} ---")

    except Exception as e:
        print(f"执行更新过程中发生严重错误: {e}")
        
    finally:
        # 7. 存储优化：清理空间
        print("执行磁盘空间回收...")
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        # 清理解压后的 JSONL 文件，因为它们已经在数据库里了
        jsonl_files = glob.glob(os.path.join(DATA_DIR, "*.jsonl"))
        for j_file in jsonl_files:
            os.remove(j_file)
        print("空间清理完成。")

if __name__ == "__main__":
    main()