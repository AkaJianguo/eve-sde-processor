# EVE SDE Processor Docker 运维手册

适用于使用 `docker-compose.yml` 运行的最小化部署（PostgreSQL + SDE 处理器）。覆盖环境准备、启动、手动同步、备份与故障排查。

## 1. 组成与持久化
- 数据库：PostgreSQL 15（容器名 `eve_db`），数据持久化挂载到 `./postgres_data`。
- SDE 处理器：自建镜像（容器名 `eve_sde_worker`），代码位于 `./eve-sde-processor`，数据目录挂载为 `./data`。
- 时区：挂载宿主 `/etc/localtime` 和 `/etc/timezone` 保持时间一致。
- 网络：自定义 bridge `eve_net`，数据库端口仅绑定 `127.0.0.1:5432`，外部无法直接访问。

目录约定（宿主机）：
```
./data           # SDE 下载/解压/版本文件 current_version.txt
./postgres_data  # PostgreSQL 数据目录
./.env           # 环境变量文件（需自行创建）
./docker-compose.yml
./eve-sde-processor
```

## 2. 环境变量 (.env 示例)
```
DB_USER=eve_admin
DB_PASSWORD=your_password
DB_NAME=eve_sde_db
# 供 sde-processor 使用的数据库 URL
DATABASE_URL=postgresql://eve_admin:your_password@db:5432/eve_sde_db
```

## 3. 启动与日常操作
- 构建并启动：`docker compose up -d`
- 查看状态：`docker compose ps`
- 查看日志：`docker compose logs -f sde-processor` 或 `docker compose logs -f db`
- 停止：`docker compose down`

## 4. 手动同步与刷新
- 强制全量同步（忽略已记录版本）：
	1) 删除宿主机 `data/current_version.txt`（若存在）。
	2) 执行 `docker compose exec sde-processor python main.py`。
- 只刷新视图（修改了 `scripts/init_views.sql` 时）：
	`docker compose exec db psql -U ${DB_USER} -d ${DB_NAME} -f scripts/init_views.sql`

## 5. 数据库访问（宿主机）
- 本地 psql 连接：`psql -h 127.0.0.1 -U ${DB_USER} -d ${DB_NAME}`
- GUI (DataGrip/Navicat) 连接：主机 127.0.0.1，端口 5432，账户同上；建议仅在本机访问，不暴露公网。

## 6. 备份与恢复
- 备份：`docker compose exec db pg_dump -U ${DB_USER} -d ${DB_NAME} > backup.sql`
- 恢复：`cat backup.sql | docker compose exec -T db psql -U ${DB_USER} -d ${DB_NAME}`

## 7. 故障排查速查表
- 容器起不来：检查 `.env` 是否存在且变量齐全；确认端口 5432 未被占用。
- SDE 不更新：查看 `docker compose logs -f sde-processor`，必要时删除 `data/current_version.txt` 后重跑同步。
- DB 连接被拒绝：确保连接主机为 `127.0.0.1`，并检查 `.env` 中用户名/密码与数据库初始用户一致。
- 时间不一致：确认宿主 `/etc/localtime` `/etc/timezone` 是否存在且已挂载。

## 8. 日常巡检建议
- 每日：`docker compose ps` 确认状态；检查 `sde-processor` 日志是否完成当日同步。
- 每周：`du -sh postgres_data data` 查看磁盘占用；按需清理过期备份。
- 变更后：修改 `scripts/init_views.sql` 或核心逻辑，先在测试环境跑一遍 `docker compose exec sde-processor python main.py` 观察日志，再应用生产。
