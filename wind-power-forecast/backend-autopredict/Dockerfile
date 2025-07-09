# # 使用 Miniconda 基础镜像
# FROM continuumio/miniconda3

# # 设置工作目录
# WORKDIR /app

# # 复制 environment.yml
# COPY environment.yml .

# # 创建 Conda 环境
# RUN conda env create -f environment.yml && conda clean --all --yes

# # 激活环境
# ENV PATH /opt/conda/envs/wind-power-env/bin:$PATH

# # 复制项目代码
# COPY . .

# # 暴露端口
# EXPOSE 5000

# # 启动应用
# CMD ["python", "app.py"]

FROM continuumio/miniconda3

# 安装Node.js环境（PM2依赖）和PostgreSQL客户端工具
RUN apt-get update && apt-get install -y curl postgresql-client && \
    curl -sL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g pm2 && \
    echo "PM2安装路径: $(which pm2)" && \
    # 不创建符号链接，直接使用npm全局安装的路径
    echo "export PM2_PATH=$(which pm2)" >> /etc/environment

# 设置工作目录
WORKDIR /app

# 复制环境配置
COPY wind-power-forecast/backend-autopredict/environment.yml .

# 配置pip使用阿里云镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 创建Conda环境
RUN conda env create -f environment.yml && conda clean --all --yes

# 激活Conda环境
ENV PATH /opt/conda/envs/wind-power-env/bin:$PATH

# 复制项目代码
COPY wind-power-forecast/backend-autopredict /app/

# 创建PM2配置文件
RUN echo "module.exports = { apps: [{\
  name: 'autopredict-app',\
  script: 'app.py',\
  interpreter: 'python',\
  autorestart: true,\
  watch: false,\
  env: { NODE_ENV: 'production' }\
}] }" > ecosystem.config.js

# 创建启动脚本
COPY wind-power-forecast/backend-autopredict/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 暴露端口
EXPOSE 5001

# 使用启动脚本
CMD ["/app/docker-entrypoint.sh"]