FROM c104-scada-client:v1.0

RUN apt-get update && apt-get install -y \
    openssh-client \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/scripts/ecmwf_fetcher

# 安装Python依赖
COPY simulation/zone2-processor/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 复制Zone2原始脚本（不修改，仅导入函数）
COPY 电力二区接收脚本/fetch_data_from_c.py /opt/scripts/ecmwf_fetcher/fetch_data_from_c.py
COPY 电力二区接收脚本/etext2csv.py /opt/scripts/ecmwf_fetcher/etext2csv.py
COPY 电力二区接收脚本/cleanup_state.py /opt/scripts/ecmwf_fetcher/cleanup_state.py

# 创建 db_models 包目录
RUN mkdir -p /opt/scripts/db_models

# 复制模拟模式包装脚本
COPY simulation/zone2-processor/process_local.py /opt/scripts/ecmwf_fetcher/process_local.py

# 复制DB引导脚本
COPY simulation/zone2-processor/ensure_db.py /opt/scripts/ensure_db.py

# 复制DB摄取相关文件
COPY simulation/zone2-processor/db_config.py /opt/scripts/db_config.py
COPY wind-power-forecast/backend/services/ecmwf_ingest_service.py /opt/scripts/ecmwf_ingest_service.py
COPY wind-power-forecast/backend/db_models/__init__.py /opt/scripts/db_models/__init__.py.full
COPY simulation/zone2-processor/db_models_init.py /opt/scripts/db_models/__init__.py
COPY wind-power-forecast/backend/db_models/base.py /opt/scripts/db_models/base.py
COPY wind-power-forecast/backend/db_models/ecmwf_model.py /opt/scripts/db_models/ecmwf_model.py
# 金仓数据库方言（处理版本字符串兼容性）
COPY wind-power-forecast/backend/kingbase_dialect.py /opt/scripts/kingbase_dialect.py

# 创建目录
RUN mkdir -p /data/from_server_c/temp \
    && mkdir -p /data/from_server_c/csv/CDQ \
    && mkdir -p /data/from_server_c/csv/DQ \
    && mkdir -p /data/from_server_c/csv/QXYC \
    && mkdir -p /data/daily_pre_csv/short \
    && mkdir -p /data/daily_pre_csv/middle \
    && mkdir -p /data/daily_pre_csv/example \
    && mkdir -p /var/log

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY simulation/zone2-processor/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
