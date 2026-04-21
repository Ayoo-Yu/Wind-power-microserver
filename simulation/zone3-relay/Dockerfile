FROM c104-scada-client:v1.0

RUN apt-get update && apt-get install -y \
    openssh-client \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/scripts/ecmwf_fetcher

# 复制Zone3原始脚本（不修改）
COPY 电力三区接收脚本/fetch_data_from_c.py /opt/scripts/ecmwf_fetcher/fetch_data_from_c.py
COPY 电力三区接收脚本/cleanup_state.py /opt/scripts/ecmwf_fetcher/cleanup_state.py

# 创建目录
RUN mkdir -p /data/from_server_c/temp \
    && mkdir -p /var/log \
    && mkdir -p /home/ecs-user/.ssh \
    && chmod 700 /home/ecs-user/.ssh

# SSH配置
RUN echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config \
    && echo "UserKnownHostsFile /dev/null" >> /etc/ssh/ssh_config

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY simulation/zone3-relay/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
