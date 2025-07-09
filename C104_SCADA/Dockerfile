# 使用官方的 Python 基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件（如果你的依赖在一个 requirements.txt 文件中）
COPY requirements.txt .

# 安装 Python 依赖
# 假设 c104 库可以通过 pip 安装，或者你在这里添加特定于 c104 的安装步骤
RUN pip install --no-cache-dir -r requirements.txt
# 或者直接: RUN pip install --no-cache-dir c104 some_other_dependency

# 复制你的脚本到工作目录
COPY scada_c104.py .

# 复制配置文件到工作目录
#COPY config.ini .

# 复制日志配置模块到工作目录
COPY logging_config.py .

# 创建日志目录
RUN mkdir -p logs

# 设置默认时区 (可选, 但对于日志时间戳可能有用)
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 运行你的 Python 脚本
CMD ["python", "scada_c104.py"]