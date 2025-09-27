#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印标题
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🌪️  风功率预测系统 - 快速启动工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker未安装${NC}"
    echo "   请访问：https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose未安装${NC}"
    echo "   请安装Docker Compose"
    exit 1
fi

# 检查权限
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}⚠️  警告：以root用户运行${NC}"
fi

echo -e "${GREEN}✅ 环境检查通过${NC}"
echo

# 显示菜单的函数
show_menu() {
    echo -e "${BLUE}请选择启动模式：${NC}"
    echo "1️⃣  开发环境（推荐）- 快速体验所有功能"
    echo "2️⃣  微服务架构 - 企业级完整部署"
    echo "3️⃣  仅基础设施 - 数据库和中间件"
    echo "4️⃣  系统状态检查"
    echo "5️⃣  停止所有服务"
    echo "6️⃣  查看日志"
    echo "7️⃣  退出"
    echo
}

# 开发环境启动
dev_env() {
    echo -e "${YELLOW}🚀 正在启动开发环境...${NC}"
    cd wind-power-forecast || exit

    # 检查配置文件
    if [[ ! -f .env ]]; then
        echo -e "${YELLOW}⚠️  创建默认配置文件${NC}"
        cp .env.example .env
    fi

    echo -e "${GREEN}📦 启动基础设施服务...${NC}"
    docker-compose -f database/docker-compose.yaml up -d

    echo -e "${GREEN}⏳ 等待数据库启动...${NC}"
    sleep 30

    echo -e "${GREEN}🎯 启动应用服务...${NC}"

    # 检查Node.js
    if command -v npm &> /dev/null; then
        echo -e "${GREEN}🚀 启动前端服务...${NC}"
        cd frontend && npm install && npm run dev &
        FRONTEND_PID=$!
        cd ..
    else
        echo -e "${RED}❌ Node.js未安装，跳过前端服务${NC}"
    fi

    # 检查Python
    if command -v python3 &> /dev/null; then
        echo -e "${GREEN}🐍 启动后端服务...${NC}"
        python3 -m pip install -r backend/requirements.txt
        python3 backend/app.py &
        BACKEND_PID=$!
    else
        echo -e "${RED}❌ Python未安装，跳过后端服务${NC}"
    fi

    echo -e "${GREEN}✅ 开发环境启动完成！${NC}"
    echo
    echo "📋 访问地址："
    echo "   前端应用: http://localhost:8080"
    echo "   后端API:  http://localhost:5000"
    echo "   数据库管理: http://localhost:5050"
    echo "   文件存储: http://localhost:9001"
    echo
    echo -e "${YELLOW}ℹ️  服务启动需要30-60秒${NC}"
    echo -e "${YELLOW}ℹ️  按回车键返回主菜单${NC}"
    read -r
}

# 微服务架构启动
microservices() {
    echo -e "${YELLOW}🚀 正在启动微服务架构...${NC}"
    cd wind-power-microservices || exit

    echo -e "${GREEN}🏗️  启动基础设施...${NC}"
    docker-compose up -d

    echo -e "${GREEN}⏳ 等待服务启动...${NC}"
    sleep 60

    echo -e "${GREEN}✅ 微服务架构启动完成！${NC}"
    echo
    echo "📋 访问地址："
    echo "   API网关:   http://localhost:8000"
    echo "   Grafana:   http://localhost:3000"
    echo "   Kafka UI:  http://localhost:8090"
    echo "   Prometheus: http://localhost:9090"
    echo
    echo -e "${YELLOW}ℹ️  服务启动需要1-2分钟${NC}"
    echo -e "${YELLOW}ℹ️  按回车键返回主菜单${NC}"
    read -r
}

# 仅基础设施
infrastructure() {
    echo -e "${YELLOW}🚀 正在启动基础设施...${NC}"
    cd wind-power-forecast || exit
    docker-compose -f database/docker-compose.yaml up -d
    echo -e "${GREEN}✅ 基础设施启动完成！${NC}"
    echo -e "${YELLOW}ℹ️  按回车键返回主菜单${NC}"
    read -r
}

# 系统状态检查
status_check() {
    echo -e "${YELLOW}🔍 正在检查系统状态...${NC}"
    echo

    # 检查Docker服务
    echo "1️⃣  Docker服务状态："
    if docker version > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ Docker运行正常${NC}"
    else
        echo -e "   ${RED}❌ Docker未运行${NC}"
    fi

    # 检查容器状态
    echo
    echo "2️⃣  容器运行状态："
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2> /dev/null || echo "   无运行中的容器"

    # 检查端口占用
    echo
    echo "3️⃣  端口占用检查："
    if netstat -tuln 2> /dev/null | grep -E ":8080|:5000|:8000|:3000" > /dev/null; then
        echo -e "   ${GREEN}✅ 系统端口已监听${NC}"
    else
        echo -e "   ${YELLOW}⚠️  系统端口未监听${NC}"
    fi

    echo
    echo -e "${YELLOW}ℹ️  按回车键返回主菜单${NC}"
    read -r
}

# 停止所有服务
stop_all() {
    echo -e "${YELLOW}🛑 正在停止所有服务...${NC}"

    # 停止后台进程
    jobs -p | xargs -r kill 2> /dev/null

    # 停止Docker容器
    cd wind-power-forecast 2> /dev/null || true
    docker-compose -f database/docker-compose.yaml down 2> /dev/null || true

    cd ../wind-power-microservices 2> /dev/null || true
    docker-compose down 2> /dev/null || true

    echo -e "${GREEN}✅ 所有服务已停止${NC}"
    echo -e "${YELLOW}ℹ️  按回车键返回主菜单${NC}"
    read -r
}

# 查看日志
view_logs() {
    echo -e "${YELLOW}📋 日志查看选项：${NC}"
    echo "1️⃣  Docker容器日志"
    echo "2️⃣  系统日志"
    echo "3️⃣  返回主菜单"
    echo

    read -r log_choice

    case $log_choice in
        1)
            echo -e "${GREEN}📄 Docker容器日志：${NC}"
            docker ps --format "{{.Names}}" 2> /dev/null
            echo
            read -r -p "请输入容器名称：" container_name
            docker logs "$container_name" --tail 50
            ;;
        2)
            echo -e "${GREEN}📄 系统日志：${NC}"
            if [[ -f wind-power-forecast/backend/logs/app.log ]]; then
                tail -50 wind-power-forecast/backend/logs/app.log
            else
                echo "日志文件不存在"
            fi
            ;;
        3)
            return
            ;;
    esac

    echo -e "${YELLOW}ℹ️  按回车键返回主菜单${NC}"
    read -r
}

# 主循环
while true; do
    show_menu
    read -r choice

    case $choice in
        1) dev_env ;;
        2) microservices ;;
        3) infrastructure ;;
        4) status_check ;;
        5) stop_all ;;
        6) view_logs ;;
        7) break ;;
        *) echo -e "${RED}❌ 无效选项，请重新输入${NC}" ;;
    esac
done

echo -e "${GREEN}👋 感谢使用风功率预测系统！${NC}"
echo -e "${GREEN}📚 详细使用指南请查看：PROJECT_DOCUMENTATION.md${NC}"
echo -e "${GREEN}🔧 运维手册请查看：OPERATIONS_MANUAL.md${NC}"
exit 0