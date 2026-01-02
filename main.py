import os
import requests
import zipfile
import json
import glob
import logging
from config.settings import SDE_JSONL_URL, DATA_DIR
from core.importer import SDEImporter

# 配置日志
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
    logging.info("Connecting to EVE servers to check SDE version...")
    try:
        response = requests.get(SDE_JSONL_URL, timeout=15)
        response.raise_for_status()
        for line in response.text.splitlines():
            data = json.loads(line)
            if data.get("_key") == "sde":
                return str(data.get("buildNumber"))
    except Exception as e:
        logging.error(f"Version check failed: {e}")
    return None

def run_post_processing(importer):
    logging.info("Starting database post-processing...")
    try:
        with importer.conn.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'raw';")
            tables = cursor.fetchall()
            for table in tables:
                cursor.execute(f"ANALYZE raw.{table[0]};")
        importer.conn.commit()
        logging.info(f"✅ Post-processing: Analyzed {len(tables)} tables.")
    except Exception as e:
        logging.error(f"⚠️ Post-processing failed: {e}")
        importer.conn.rollback()

def main():
    importer = SDEImporter()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    latest_build = fetch_latest_build()
    local_build = get_local_version()
    
    if not latest_build:
        logging.warning("Could not fetch remote version.")
        return

    if latest_build == local_build:
        logging.info(f"Local build {local_build} is up to date.")
        return
    
    logging.info(f"New version detected: {local_build} -> {latest_build}")
    
    zip_filename = f"sde_{latest_build}.zip"
    download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{latest_build}-jsonl.zip"
    
    try:
        logging.info(f"Downloading SDE Build {latest_build}...")
        r = requests.get(download_url, stream=True)
        with open(zip_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logging.info("Extracting data...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        
        sde_files = glob.glob(os.path.join(DATA_DIR, "*.jsonl"))
        logging.info(f"Found {len(sde_files)} files. Starting import...")
        
        for file_path in sde_files:
            try:
                importer.auto_import(file_path)
            except Exception as e:
                logging.error(f"Error importing {file_path}: {e}")
        
        run_post_processing(importer)
        save_local_version(latest_build)
        logging.info(f"--- SDE Update Successful: Build {latest_build} ---")

    except Exception as e:
        logging.error(f"Critical error: {e}")
    finally:
        logging.info("Cleaning up disks...")
        if os.path.exists(zip_filename): os.remove(zip_filename)
        for j_file in glob.glob(os.path.join(DATA_DIR, "*.jsonl")): os.remove(j_file)
        logging.info("Disk cleanup finished.")

if __name__ == "__main__":
    main()