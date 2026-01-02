import os
import requests
import zipfile
import json
import glob
from config.settings import SDE_JSONL_URL, DATA_DIR
from core.importer import SDEImporter

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
    
    print(f"New version detected: {local_build} -> {latest_build}")
    
    # 3. 下载与执行
    zip_filename = f"sde_{latest_build}.zip"
    download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{latest_build}-jsonl.zip"
    
    try:
        print(f"Downloading SDE Build {latest_build}...")
        r = requests.get(download_url, stream=True)
        with open(zip_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print("Extracting data to /data directory...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        
        sde_files = glob.glob(os.path.join(DATA_DIR, "*.jsonl"))
        print(f"Found {len(sde_files)} files. Starting database import...")
        
        for file_path in sde_files:
            try:
                importer.auto_import(file_path)
            except Exception as e:
                print(f"Warning: Skipping {file_path} due to error.")
        
        save_local_version(latest_build)
        print(f"--- SDE Update Successful: Build {latest_build} ---")

    except Exception as e:
        print(f"Critical error during update: {e}")
        
    finally:
        # 4. 清理磁盘
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
        for j_file in glob.glob(os.path.join(DATA_DIR, "*.jsonl")):
            os.remove(j_file)
        print("Disk cleanup finished.")

if __name__ == "__main__":
    main()