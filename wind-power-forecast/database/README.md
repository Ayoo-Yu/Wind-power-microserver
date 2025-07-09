# 风电功率预测系统数据库

本目录包含风电功率预测系统的数据库配置和迁移脚本。

## 数据库配置

数据库使用PostgreSQL，通过Docker容器运行。配置文件为`docker-compose.yaml`。

## 数据库迁移

当数据库结构发生变化时，需要执行数据库迁移。本目录提供了几种执行迁移的方式：

### 方法1：直接在Docker容器中执行迁移（推荐）

这种方法适用于已经运行的Docker容器，不需要停止容器，也不会丢失现有数据。

1. 确保Docker容器正在运行
2. 运行`docker_apply_migrations.bat`脚本

```
cd wind-power-forecast/database
docker_apply_migrations.bat
```

### 方法2：在本地执行迁移

如果您已经在本地安装了PostgreSQL客户端，可以使用这种方法。

1. 确保PostgreSQL客户端已安装
2. 运行`apply_migrations.bat`脚本（Windows）或`apply_migrations.sh`脚本（Linux/Mac）

```
cd wind-power-forecast/database
apply_migrations.bat
```

### 方法3：重新创建数据库容器

如果您不需要保留现有数据，可以直接重新创建数据库容器。

1. 停止并删除现有容器
```
docker-compose down -v
```

2. 重新创建并启动容器
```
docker-compose up -d
```

3. 执行迁移脚本
```
docker_apply_migrations.bat
```

## 默认用户

迁移脚本会创建一个默认的管理员用户：

- 用户名：admin
- 密码：admin123

首次登录后，系统会要求修改密码。 