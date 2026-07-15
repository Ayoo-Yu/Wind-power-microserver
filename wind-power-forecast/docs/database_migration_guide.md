# 数据库迁移与发布指南

## 管理原则

业务数据库结构只有一个变更入口：`backend/migrations` 下的 Alembic 迁移。SQLAlchemy 模型负责表达当前结构，迁移文件负责描述版本之间的变化。

应用进程、定时任务和 HTTP 接口不创建业务表。动态时间分区属于受控运维操作，并受对应数据源开关约束。

## 日常开发流程

1. 修改或新增 `backend/db_models` 中的模型。
2. 确认本地数据库已达到最新版本。
3. 生成迁移。
4. 人工检查升级和回滚逻辑。
5. 在本地测试升级。
6. 提交模型、迁移和测试。

```bash
python backend/manage_db.py status
python backend/manage_db.py create "增加测点映射表"
python backend/manage_db.py upgrade
python backend/manage_db.py check
```

Windows 可以直接使用 `database` 目录中的批处理脚本。

## 首次引入迁移管理

已有数据库执行：

```bash
python backend/manage_db.py prepare
```

该命令会核对模型要求的全部表。结构完整时写入当前基线版本；发现缺表时停止，不会偷偷补表。

全新数据库执行相同命令时，会创建当前模型表并记录基线。该引导行为只用于首次初始化。

## 发布流程

1. 对生产数据库执行完整备份。
2. 在生产数据副本上执行升级演练。
3. 停止会写入相关表的任务。
4. 执行 `python backend/manage_db.py upgrade`。
5. 执行 `python backend/manage_db.py check`。
6. 启动应用并检查数据库治理页面。

## 回滚要求

每个迁移都应提供可验证的回滚逻辑。涉及数据丢失的迁移应采用扩展、迁移、切换、清理的分阶段方式，避免直接删除仍可能被旧版本读取的结构。

## 内网交付

迁移文件随后端镜像或离线发布包交付，不依赖外网下载。发布包必须包含：

1. 精确镜像版本。
2. 数据库备份说明。
3. 待执行迁移清单。
4. 升级前检查和升级后验证命令。
5. 回滚步骤。
