#!/bin/bash
set -e

# 初始化数据库
if [ ! -s "/home/kingbase/userdata/data/sys_ident.conf" ]; then
    echo "初始化数据库..."
    # 初始化代码，根据金仓数据库的实际情况调整
fi

# 启动数据库
echo "启动金仓数据库服务..."
/home/kingbase/install/kingbase/bin/sys_ctl -D /home/kingbase/userdata/data start

# 等待数据库启动
sleep 5

# 创建应用数据库
if ! /home/kingbase/install/kingbase/bin/ksql -c "\l" | grep -q windpower; then
    echo "创建应用数据库 windpower..."
    /home/kingbase/install/kingbase/bin/ksql -c "CREATE DATABASE windpower WITH OWNER = system ENCODING = 'UTF8';"
fi

# 保持容器运行
tail -f /dev/null 