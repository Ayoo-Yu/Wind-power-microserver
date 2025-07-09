#!/bin/bash
# 脚本等待金仓数据库启动完成，然后创建windpower数据库

echo "等待金仓数据库启动..."
sleep 30  # 等待足够的时间以确保数据库完全启动

echo "尝试连接数据库并创建windpower数据库..."
# 使用docker exec命令在金仓数据库容器内执行SQL
docker exec -i wind-power-kingbase bash << EOF
cd /home/kingbase
/home/kingbase/install/kingbase/bin/ksql -U system -d test << EOSQL
CREATE DATABASE windpower;
\q
EOSQL
EOF

# 验证数据库创建
echo "检查数据库是否创建成功..."
docker exec -i wind-power-kingbase bash -c "/home/kingbase/install/kingbase/bin/ksql -U system -d test -c '\l'"

# 更新后端连接
echo "修改后端配置并重启服务..."
docker exec -i wind-power-forecast-backend-1 bash -c "export DB_NAME=windpower"
docker restart wind-power-forecast-backend-1

echo "完成！请检查后端日志以确认连接状态。" 