#!/bin/bash

# 检查app.py是否已修改
if grep -q "init_users_and_roles" app.py; then
  echo "✅ app.py已包含用户初始化代码"
else
  echo "❌ app.py缺少用户初始化代码，请先修改app.py"
  exit 1
fi

# 构建新镜像
echo "开始构建新的后端镜像..."
docker build -t wind-power-forecast-backend:latest .

echo "构建完成！新镜像ID:"
docker images wind-power-forecast-backend:latest --format "{{.ID}}"

echo "使用以下命令保存镜像:"
echo "docker save wind-power-forecast-backend:latest > wind-power-forecast-backend.tar"

echo "使用以下命令在阿里云服务器上加载镜像:"
echo "docker load < wind-power-forecast-backend.tar" 