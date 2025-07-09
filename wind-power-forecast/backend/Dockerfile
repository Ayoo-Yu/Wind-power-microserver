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

# 安装Node.js环境和PostgreSQL客户端工具
RUN apt-get update && apt-get install -y curl postgresql-client && \
    curl -sL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# 设置工作目录
WORKDIR /app

# 复制环境配置
COPY wind-power-forecast/backend/environment.yml .

# 配置pip使用阿里云镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 创建Conda环境
RUN conda env create -f environment.yml && conda clean --all --yes

# 激活Conda环境
ENV PATH /opt/conda/envs/wind-power-env/bin:$PATH

# 安装Gunicorn和gevent
RUN pip install gunicorn gevent flask-jwt-extended

# 复制alembic迁移配置 (从项目根目录复制)
COPY migration /app/migration/
COPY alembic.ini /app/alembic.ini

# 确保有正确的权限
RUN chmod -R 755 /app/migration
RUN chmod 644 /app/alembic.ini

# 复制项目代码
COPY wind-power-forecast/backend /app/

# # 创建符号链接，使脚本文件能在预期路径被找到
# RUN mkdir -p /app/backend/auto_scripts/scripts/supershort /app/backend/auto_scripts/scripts/short /app/backend/auto_scripts/scripts/middle
# RUN if [ -d "/app/auto_scripts/scripts/supershort" ]; then \
#         ln -sf /app/auto_scripts/scripts/supershort/scheduler_supershort.py /app/backend/auto_scripts/scripts/supershort/scheduler_supershort.py; \
#     fi && \
#     if [ -d "/app/auto_scripts/scripts/short" ]; then \
#         ln -sf /app/auto_scripts/scripts/short/scheduler_short.py /app/backend/auto_scripts/scripts/short/scheduler_short.py; \
#     fi && \
#     if [ -d "/app/auto_scripts/scripts/middle" ]; then \
#         ln -sf /app/auto_scripts/scripts/middle/scheduler_middle.py /app/backend/auto_scripts/scripts/middle/scheduler_middle.py; \
#     fi

# 创建启动脚本
COPY wind-power-forecast/backend/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 暴露端口
EXPOSE 5000

# 使用新的启动脚本
CMD ["/app/docker-entrypoint.sh"]