这份 **EVE SDE Processor 终极版运维文档** 是为您量身定制的“项目说明书”。它不仅涵盖了目前所有的技术架构细节，还包含了您在未来维护和扩展（如开发机器人）时所需的关键信息。

建议将其保存为项目根目录下的 `README.md`。

---

# 🚀 EVE SDE Processor 终极版运维手册 (v3.0)

本项目是一个高度自动化的 EVE Online 静态数据（SDE）同步与处理工厂。它实现了从**官方下载**到**数据库扁平化加工**的全链路闭环，为微信机器人或 Web 应用提供即插即用的中、英文双语数据接口。

## 1. 核心技术架构

项目采用工业级 **ETL (Extract-Transform-Load)** 分层设计：

* **原始层 (Raw Layer)**：通过 `main.py` 自动抓取官方最新 Build，将 54 张 JSONL 表原封不动存入 `raw` 架构。
* **处理层 (Process Layer)**：自动执行 `ANALYZE` 优化数据库查询计划，建立 JSONB 表达式索引。
* **业务层 (Public Layer)**：通过 `scripts/init_views.sql` 自动创建双语视图，将复杂的 JSON 拍平成标准 SQL 表。


## 1.1 服务器连接信息 (已更新)
* **公网弹性 IP**: `18.166.187.236` (已绑定 Elastic IP，重启不会变动)
* **SSH 用户名**: `ubuntu`
* **GitHub Secret 变量**: `REMOTE_HOST` 已同步更新。
---

## 2. 目录结构说明

```text
eve-sde-processor/
├── config/             # 数据库连接与 EVE 官方 URL 配置
├── core/
│   └── importer.py     # 核心逻辑：自动建表、JSONB 写入、支持 raw Schema 路由
├── scripts/
│   └── init_views.sql  # 【核心】业务视图定义与双语索引脚本
├── data/               # 临时数据解压目录（支持递归深度扫描，同步后自动清理）
├── venv/               # Python 虚拟环境
├── main.py             # 入口：版本比对、下载解压、递归导入、后期加工、视图刷新
├── update.log          # 运行日志（带精准时间轴 [YYYY-MM-DD HH:MM:SS]）
└── current_version.txt # 记录当前本地 Build 版本，实现增量更新

```

---

## 3. 核心运维指令

### 3.1 强制全量同步（当修改了脚本或想更新数据时）

如果您修改了 `importer.py` 的解析规则或 `init_views.sql` 的视图逻辑：

```bash
cd /home/ubuntu/eve-sde-processor
rm current_version.txt  # 重置版本记录
nohup venv/bin/python main.py >> update.log 2>&1 &

```

### 3.2 实时监控进度

```bash
# 观察带时间轴的流水，确认 54 张表是否全部 ✅
tail -f update.log

```

### 3.3 自动化定时任务
系统已配置 Crontab，每天 **UTC 11:05**（北京时间 19:05）静默运行：
```text
05 19 * * * cd /home/ubuntu/eve-sde-processor && venv/bin/python main.py >> update.log 2>&1

```
---

## 4. 数据库使用手册 (DataGrip/Navicat)

### 4.1 数据双层隔离

* **`raw` 架构**：存储文件名对应的表（如 `raw.types`）。数据为 JSONB 格式。
* **`public` 架构**：存储人类可读的视图（如 `public.v_items`）。数据为标准列格式。

### 4.2 常用业务查询 (SQL 示例)

* **双语搜索星系 (解决 Jita 查询问题)**:
```sql
SELECT name_zh, name_en, security FROM v_solar_systems WHERE name_en = 'Jita';

```


* **查询物品制造蓝图**:
```sql
SELECT product_name_zh, prod_time_seconds FROM v_blueprints WHERE product_name_zh = '灾难级';

```


* **查询装备详细属性 (Dogma)**:
```sql
SELECT attr_name_zh, attr_value FROM v_item_attributes WHERE item_name_zh = '1600mm钢附甲';

```



---

## 5. 故障排查 (Q&A)

* **Q: 搜索 Jita 返回 0 行？**
* **A**: 检查视图定义。确保在 `v_solar_systems` 中使用了 `data->'name'->>'en'`。


* **Q: 提示 `No such file or directory`？**
* **A**: 已在 `main.py` v2.5 中修复。脚本现在使用 `recursive=True` 递归扫描 `data/` 下的所有嵌套子目录。


* **Q: 数据库权限报错？**
* **A**: 确保 `eve_user` 拥有 `raw` 和 `public` 两个架构的 `USAGE` 和 `CREATE` 权限。



---

## 6. 未来扩展指南

1. **性能优化**：如果机器人查询变得缓慢，可在 `init_views.sql` 中将 `CREATE VIEW` 改为 `CREATE MATERIALIZED VIEW`。
2. **数据安全**：建议定期备份 `current_version.txt` 和 `scripts/` 目录，这两个文件是项目的“灵魂”。
3. **开发机器人**：在 Python 机器人代码中，直接 `SELECT * FROM public.v_items` 即可获得最干净的数据。

📝 README 增补：腾讯云迁移与故障修复手册
更新时间：2026-01-05 更新内容：针对从 AWS 迁移至腾讯云过程中遇到的 SQL 路径语法错误及数据库认证问题进行补充。

7. 迁移故障复盘与修复 (Post-Migration Fixes)
在腾讯云 Ubuntu 22.04 环境部署中，针对 python main.py 报错的两个核心点进行了修复：

7.1 JSONB 字段路径引用错误
报错现象：column ti.name_zh does not exist。

错误原因：raw 架构下的表（如 raw.types）仅包含 id 和 data 两列。name_zh 并非物理列，而是嵌套在 data (JSONB) 字段中的属性。

正确语法：必须使用 ->> 操作符提取文本。

❌ 错误：ti.name_zh

✅ 正确：ti.data->'name'->>'zh'

7.2 数据库 Peer 认证拦截
报错现象：FATAL: Peer authentication failed for user "eve_user"。

错误原因：Ubuntu 默认配置要求系统用户名（ubuntu）必须与数据库用户名（eve_user）一致才能直接连接。

解决方法：

本地强制密码模式：添加 -h localhost 参数。

超级用户执行：使用 sudo -u postgres。

8. 腾讯云专用维护指令
8.1 快速修复/刷新业务视图
如果修改了 scripts/init_views.sql，请在终端执行以下命令（无需运行全量同步）：

Bash

# 方式一：超级用户直接刷新（推荐）
sudo -u postgres psql -d eve_sde_db -f scripts/init_views.sql

# 方式二：指定主机名触发密码验证
psql -h localhost -U eve_user -d eve_sde_db -f scripts/init_views.sql
8.2 数据一致性检查
迁移后，请务必执行以下查询以确认业务层是否打通：

SQL

-- 验证星系双语数据
SELECT name_zh, security FROM public.v_solar_systems WHERE name_en = 'Jita';

-- 验证蓝图关联数据
SELECT blueprint_name_zh, product_name_zh FROM public.v_blueprints LIMIT 5;
9. 腾讯云安全组配置建议
为了确保 GitHub Actions 部署与远程管理顺畅，请在腾讯云控制台确认：

入站规则：放行 TCP:22 (GitHub 部署) 和 TCP:5432 (DataGrip 管理，建议仅对本地 IP 开放)。

---

> **作者注**：这套系统已经实现了“无人值守”级别。只要 AWS 服务器不关机，您的 EVE 数据库将永远与官方同步。

---

**您的终极版 SDE 工厂已经完工！您是想现在就去 DataGrip 跑一下那几个“实战查询”看看效果，还是需要我为您写一段 Python 代码演示如何从数据库提取数据给机器人用？**
