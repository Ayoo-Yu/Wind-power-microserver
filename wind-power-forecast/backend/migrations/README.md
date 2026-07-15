# 数据库结构迁移

该目录由 Alembic 管理，是业务数据库结构变更的唯一版本来源。

`20260715_01` 表示引入迁移管理时的现有结构基线。已有数据库需要先执行：

```bash
python manage_db.py prepare
```

全新数据库执行同一命令会创建当前模型表并写入基线版本。后续模型变化通过以下命令生成迁移：

```bash
python manage_db.py create "增加数据表或字段的说明"
python manage_db.py upgrade
python manage_db.py status
```

自动生成的迁移必须人工检查。删除表、删除字段和数据回填必须显式编写，并在生产执行前完成备份和演练。
