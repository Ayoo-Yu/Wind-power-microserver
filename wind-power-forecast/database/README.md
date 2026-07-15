# 风电功率预测系统数据库管理

数据库结构由 Alembic 迁移统一管理。应用启动和业务接口只检查结构版本，不再负责自动建表。

## Windows 本地开发

查看数据库状态：

```bat
database\database_status.bat
```

模型发生变化后生成迁移：

```bat
database\create_migration.bat "增加测点映射表"
```

检查生成的 Python 迁移文件后执行升级：

```bat
database\apply_migrations.bat
```

脚本不保存数据库密码。请通过项目 `.env` 或当前终端环境变量提供连接配置。

## Linux 内网部署

```bash
./database/db.sh status
./database/db.sh prepare
./database/db.sh upgrade
```

首次接管已有数据库时，`prepare` 会先核对全部模型表。只有结构完整时才会写入基线版本。全新数据库执行 `prepare` 会创建模型表并记录基线。

## Docker 部署

```bash
docker compose exec backend python manage_db.py status
docker compose exec backend python manage_db.py upgrade
```

## 安全约束

1. 生产升级前必须备份数据库。
2. 自动生成的迁移必须人工检查。
3. 表删除和字段删除必须手工编写迁移。
4. 前端数据库治理页面只提供状态和容量监控，不执行任意 SQL。
