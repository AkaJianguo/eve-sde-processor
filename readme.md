这份手册已根据我们最近在 `eve_sde_db` 上的调试成果进行了优化，特别是修正了视图刷新的命令格式、增加了物化视图的维护逻辑，并同步了单人维护所需的“工程落地”细节。

---

# EVE SDE Processor 运维与开发手册 (v2.0)

本手册适用于基于 Docker 部署的 EVE SDE 数据底座，重点保障 **FastAPI 后端数据读取性能**与**自动化同步**。

## 1. 组成与持久化

* **数据库**：PostgreSQL 15 (容器 `eve_db`)，持久化于 `./postgres_data`。
* **处理器**：`eve_sde_worker`，处理 SDE 下载、解压及 `raw` 架构下的数据导入。
* **业务层**：`public` 架构下的视图与物化视图，专供 FastAPI 业务逻辑调用。

目录约定：

```text
/opt/EVE-Project
├── data                       # SDE 原始文件与版本记录 (current_version.txt)
├── postgres_data              # 数据库二进制文件
├── .env                       # 核心环境变量
├── docker-compose.yml
└── eve-sde-processor          # 处理器源码与脚本目录
    └── scripts/init_views.sql # 核心业务视图定义

```

## 2. 环境变量 (.env)

```bash
POSTGRES_USER=eve_admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=eve_sde_db
# FastAPI 与 Worker 内部通信 Token
INTERNAL_TOKEN=b6d8f2a4e9c1b7a0d5e8f3c2b1a9d0e7f4c2b1a5d6e8f9c0

```

---

## 3. 核心运维指令

### A. 启动与日志

* **全量启动**：`docker compose up -d`
* **监控同步进度**：`docker compose logs -f eve_sde_worker`
* **重启数据库**：`docker compose restart eve_db`

### B. 视图刷新（重要：业务逻辑变更后必跑）

当修改了 `init_views.sql` 或需要强制重算市场树（2092 条数据）时执行：

```bash
# 切换到项目根目录
cd /opt/EVE-Project

# 使用容器内变量执行刷入，确保类型转换全绿通过
docker exec -i eve_db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB' < ./eve-sde-processor/scripts/init_views.sql

```

### C. 数据一致性抽查

```bash
# 检查市场分类树数量（预期应 > 2000）
docker exec -it eve_db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT count(*) FROM public.market_menu_tree;"'

# 检查蓝图制造视图是否正常（验证类型对齐）
docker exec -it eve_db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT blueprint_id, product_name_zh FROM v_blueprints LIMIT 5;"'

```

---

## 4. 备份与恢复（单人维护保障）

| 场景 | 命令 |
| --- | --- |
| **快速备份** | `docker exec eve_db pg_dump -U eve_admin -d eve_sde_db > sde_backup_$(date +%F).sql` |
| **全量恢复** | `cat sde_backup_xxx.sql |
| **清理缓存** | `rm data/current_version.txt` (删除后重启 Worker 将触发全量重新导入) |

---

## 5. 开发联调说明

### 视图层 (PostgreSQL)

* **`v_items`**：基础物品属性，已处理 `text` 到 `float/int` 的类型转换。
* **`market_menu_tree`**：物化视图，存储 2000+ 条分类索引。
* **`v_blueprints`**：已修复 `text = integer` 冲突，支持直接查询制造产出。

### 业务层 (FastAPI)

* **高性能树形构建**：后端应读取 `market_menu_tree` 并在内存中使用字典映射（O(n) 复杂度）构建 JSON 树。
* **缓存刷新钩子**：Worker 同步完成后，应调用 FastAPI 的 `/internal/refresh-cache` 接口（带 `INTERNAL_TOKEN`）清理后端 `lru_cache`。

---

## 6. 常见故障处理

* **`operator does not exist: text = integer`**：
* 原因：视图中 ID 匹配未做显式类型转换。
* 修复：检查 `init_views.sql`，确保 ID 匹配使用了 `id::text = (path)::text` 或两边统一转为 `::int`。


* **`database "xxx" does not exist`**：
* 原因：脚本内硬编码了数据库名。
* 修复：使用 `psql -d $POSTGRES_DB` 动态调用环境变量。


* **市场菜单显示为空**：
* 原因：物化视图未刷新。
* 修复：执行 `REFRESH MATERIALIZED VIEW public.market_menu_tree;`。



---

## 7. 巡检周期建议

1. **每周一 10:00**：手动或通过 Cron 检查 `sde-processor` 是否获取到官方 SDE 新版本。
2. **变更后**：任何数据库结构的改动，必须确保 `v_blueprints` 视图能正常 LIMIT 出结果，否则后端计算蓝图成本会报错。

---

**目前手册内容已覆盖你遇到的所有坑点。需要我帮你把这个 README 的内容直接通过代码或脚本形式保存到你的服务器对应目录下吗？**