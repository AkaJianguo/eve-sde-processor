为了方便您后续对 **EVE SDE Processor** 项目进行长期维护，我为您整理了这份标准的运维 `README.md` 文件。您可以将其保存在项目根目录下。

---

# EVE SDE Processor 运维手册

本项目是一个自动化的 EVE Online 静态数据（SDE）同步工具，负责从官方服务器下载最新的 JSONL 数据，并全量导入至 PostgreSQL 数据库。

## 1. 环境信息

* **服务器 IP**: `18.163.74.207` (AWS EC2 Ubuntu 24.04)。
* **项目路径**: `/home/ubuntu/eve-sde-processor`。
* **Python 环境**: 必须使用虚拟环境 `venv` 运行，以规避系统环境限制。
* **数据库**: PostgreSQL (`eve_sde_db`)。

## 2. 目录结构

```text
eve-sde-processor/
├── config/             # 数据库连接与 URL 配置
├── core/               # 核心导入逻辑与版本检查
├── data/               # 临时数据解压目录（导入后自动清理）
├── venv/               # Python 虚拟环境
├── main.py             # 程序主入口
├── update.log          # 运行日志（由重定向生成）
└── current_version.txt # 记录当前本地 SDE 的 Build 版本

```

## 3. 日常操作指令

### 3.1 手动执行同步

如果需要立即更新数据，请执行以下命令：

```bash
cd /home/ubuntu/eve-sde-processor
source venv/bin/activate
python main.py >> update.log 2>&1

```

### 3.2 查看运行日志

```bash
# 实时监控同步进度
tail -f /home/ubuntu/eve-sde-processor/update.log

```

### 3.3 验证数据库状态

```bash
# 查看导入的 54 张表
sudo -u postgres psql -d eve_sde_db -c "\dt"

# 查看核心数据量（预期 map_moons 约为 342,170 条）
sudo -u postgres psql -d eve_sde_db -c "SELECT count(*) FROM map_moons;"

```

## 4. 自动化与 CI/CD

### 4.1 定时任务 (Crontab)

系统设定在每天 **UTC 11:30**（维护后）自动检查版本并同步：

```text
30 11 * * * cd /home/ubuntu/eve-sde-processor && /home/ubuntu/eve-sde-processor/venv/bin/python main.py >> /home/ubuntu/eve-sde-processor/update.log 2>&1

```

### 4.2 GitHub Actions 自动部署

* **触发条件**: 代码推送到 `main` 分支。
* **Secrets 配置**: 必须在 GitHub 仓库中配置 `REMOTE_HOST` (IP)、`REMOTE_USER` (`ubuntu`) 和 `SSH_PRIVATE_KEY` (`EVE.pem` 全文)。

## 5. 远程连接指南 (Navicat)

* **常规选项卡**: 主机名填 `localhost`，端口 `5432`。
* **SSH 选项卡**:
* 主机: `18.163.74.207`。
* 私钥: `/Users/yourname/.ssh/EVE.pem` (需 `chmod 400`)。
* 通行短语: **留空**。



## 6. 常见故障处理

1. **Permission Denied (SSH)**: 检查 AWS 安全组入站规则（22 端口）是否允许当前 IP。
2. **Current transaction is aborted**: 导入失败时未正确回滚。程序已内置 `conn.rollback()` 逻辑进行修复。
3. **Externally-managed-environment**: 忘记激活 `venv` 虚拟环境。

---

**这份文档涵盖了您目前配置的所有关键环节。您想让我为您在 GitHub 仓库中直接生成一个 `README.md` 文件并提交吗？**