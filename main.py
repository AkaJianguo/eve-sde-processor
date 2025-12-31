import os
import requests
import zipfile
import json
import glob
from config.settings import SDE_JSONL_URL, DATA_DIR, DB_CONFIG
from core.importer import SDEImporter

def fetch_latest_build():
    """获取官方最新的 SDE 构建版本号"""
    print("正在检查官方最新版本...")
    response = requests.get(SDE_JSONL_URL)
    for line in response.text.splitlines():
        data = json.loads(line)
        if data.get("_key") == "sde":
            return data.get("buildNumber")
    return None

def main():
    # 1. 准备工作环境
    # 确保在 ~/eve-sde-processor 目录下创建 data 文件夹
    os.makedirs(DATA_DIR, exist_ok=True)
    importer = SDEImporter()
    
    # 2. 检查版本并下载
    build_num = fetch_latest_build()
    if not build_num:
        print("错误：无法获取 Build Number")
        return
        
    zip_filename = f"sde_{build_num}.zip"
    download_url = f"https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{build_num}-jsonl.zip"
    
    # 如果文件不存在才下载，避免重复下载几百 MB
    if not os.path.exists(zip_filename):
        print(f"正在下载 SDE Build {build_num} (约 200MB+)...")
        r = requests.get(download_url, stream=True)
        with open(zip_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    
    # 3. 解压到 data/ 目录
    print("正在解压数据到 data/ 目录...")
    with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
        zip_ref.extractall(DATA_DIR)
    
    # 4. 自动扫描并导入所有 .jsonl
    # glob 会查找 data 文件夹下所有以 .jsonl 结尾的文件
    sde_files = glob.glob(os.path.join(DATA_DIR, "*.jsonl"))
    
    if not sde_files:
        print(f"错误：在 {DATA_DIR} 目录中未找到数据文件。请检查解压是否成功。")
        return

    print(f"共发现 {len(sde_files)} 个数据文件，准备开始全量导入数据库...")
    
    for file_path in sde_files:
        try:
            importer.auto_import(file_path)
        except Exception as e:
            print(f"导入 {file_path} 失败: {e}")

    # 5. 清理压缩包释放空间
    if os.path.exists(zip_filename):
        os.remove(zip_filename)
        
    print("\n--- 所有静态数据已同步至数据库 ---")

if __name__ == "__main__":
    main()