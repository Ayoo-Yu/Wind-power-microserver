# 金仓数据库方言使用指南

本文档提供了金仓数据库 SQLAlchemy 方言的使用指南以及本地测试方法，无需进入 Docker 容器。

## 问题背景

在使用 Alembic 自动生成迁移脚本时，可能会遇到以下错误：

```
TypeError: %d format: a number is required, not str
```

这个错误通常是因为金仓数据库在处理 VARCHAR 类型时返回的长度值是字符串类型（如 "255 char"），而 SQLAlchemy 期望这个值是整数类型。我们通过自定义方言解决了这个问题。

## 金仓数据库方言介绍

`kingbase_dialect.py` 文件定义了一个自定义的 SQLAlchemy 方言，用于处理金仓数据库的特殊行为：

1. 版本兼容性：提供固定版本号，避免解析错误
2. 类型处理：修复 VARCHAR 类型长度为字符串的问题，自动转换为整数
3. 类型封装：封装原始 SQLAlchemy 类型，确保长度总是整数
4. 特殊格式处理：专门处理金仓数据库中的"xxx char"格式的长度值

### 特殊格式处理

金仓数据库常返回带有"char"后缀的长度值，如"255 char"、"100char"等。我们的方言通过正则表达式专门处理这种格式：

```python
# 提取"255 char"格式中的数字部分
char_pattern = re.compile(r'^(\d+)\s*char$', re.IGNORECASE)
match = char_pattern.match(str(length_str).strip())
if match:
    return int(match.group(1))
```

该方法可以正确处理以下格式：
- "255 char"（带空格）
- "100char"（无空格）
- "20 CHAR"（不同大小写）
- "5char   "（带尾随空格）

## 本地测试方法

我们提供了三个测试脚本，可以在本地验证金仓数据库方言是否正确工作：

### 基本方言测试

运行 `test_dialect.py` 脚本来测试基本的方言功能：

```bash
# 设置环境变量
export DB_HOST=localhost
export DB_PORT=54321
export DB_USER=system
export DB_PASSWORD=12345678ab
export DB_NAME=windpower

# 运行测试脚本
python test_dialect.py
```

这个脚本会：
1. 测试数据库连接
2. 检查现有表的列类型和长度
3. 创建测试表并验证类型转换
4. 提供 Alembic 命令测试指南

### Alembic 兼容性测试

运行 `test_alembic.py` 脚本来测试 Alembic 兼容性：

```bash
# 运行测试脚本 (会自动设置默认环境变量)
python test_alembic.py
```

这个脚本会：
1. 测试方言加载
2. 验证 migration/env.py 配置
3. 测试 Alembic 命令 (current, check, revision)

### "char"后缀格式测试

运行 `test_char_format.py` 脚本来专门测试"char"后缀格式的处理：

```bash
# 运行测试脚本
python test_char_format.py
```

这个脚本会：
1. 测试各种"char"后缀格式的长度提取
2. 检查模型定义中的类型处理
3. 验证生成的DDL语句中的长度值

## 不进入容器的 Alembic 测试方法

您可以直接在本地使用 Alembic 命令，无需进入 Docker 容器：

```bash
# 确保 PYTHONPATH 指向项目根目录
cd wind-power-forecast
export PYTHONPATH=.

# 设置数据库连接环境变量
export DB_HOST=localhost  # 如果使用Docker，可以设置为容器服务名
export DB_PORT=54321
export DB_USER=system
export DB_PASSWORD=12345678ab
export DB_NAME=windpower

# 查看当前迁移版本
alembic current

# 创建新的迁移脚本
alembic revision --autogenerate -m "测试迁移"

# 升级到最新版本
alembic upgrade head
```

## Windows 用户测试方法

Windows 用户可以直接运行提供的批处理脚本：

```
test_kingbase.bat
```

此脚本提供了一个交互式菜单，可以：
1. 运行基本方言测试
2. 运行 Alembic 兼容性测试
3. 直接执行 Alembic 命令
4. 查看帮助信息

## 常见问题

### 1. 类型转换失败

如果仍然遇到类型转换问题，尝试检查：
- 金仓数据库版本是否兼容
- 模型定义中是否使用了特殊的类型参数
- SQLAlchemy 版本是否支持自定义方言

### 2. 数据库连接失败

确保：
- 数据库服务正在运行
- 连接参数正确（主机、端口、用户名、密码）
- 网络连接畅通（如果连接远程数据库）

### 3. Alembic 命令失败

可能的原因：
- Alembic 配置不正确
- migration/env.py 中的连接字符串格式错误
- 缺少必要的表或权限

### 4. 路径问题

如果遇到模块导入错误：
```
ModuleNotFoundError: No module named 'kingbase_dialect'
```

确保：
- PYTHONPATH 设置正确
- 当前工作目录包含 kingbase_dialect.py
- 运行命令的环境中安装了所有依赖包

## 其他注意事项

1. 在生产环境中应避免硬编码的数据库连接信息
2. 测试脚本中的默认值仅用于演示，应根据实际环境进行调整
3. 确保数据库用户具有足够的权限执行迁移操作 