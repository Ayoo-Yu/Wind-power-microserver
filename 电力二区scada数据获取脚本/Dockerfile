# Dockerfile for scada_client
# 放在 scada-data-get/ 文件夹内

# 使用一个合适的Python基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# (可选) 如果 .so 文件有特定的系统依赖，在这里安装
# RUN apt-get update && apt-get install -y some-dependency && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 单独进行，以便利用 Docker 的层缓存
# 只有当 requirements.txt 改变时，这一层和之后的层才会重新构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制当前构建上下文中的所有其他文件到镜像的 /app 目录
# 这会包括 scada_client.py, logging_config.py, config.ini,
# libx86_x64-iec104.so, iec104api.py, iec104types.py, 等所有在
# scada-data-get/ 目录下的文件 (除了被 .dockerignore 排除的)
COPY . .

# 设置时区 (和你的其他服务保持一致)
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 运行脚本的命令
CMD ["python3", "scada_client.py"]