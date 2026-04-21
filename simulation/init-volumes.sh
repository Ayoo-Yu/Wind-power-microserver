#!/bin/bash
# 初始化模拟生产环境目录结构和前置条件

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== 模拟生产环境初始化 ==="
echo "项目根目录: $PROJECT_ROOT"
echo ""

# 创建数据目录
mkdir -p "$SCRIPT_DIR/data/etext/temp"
mkdir -p "$SCRIPT_DIR/data/predict-short"
mkdir -p "$SCRIPT_DIR/data/predict-middle"
mkdir -p "$SCRIPT_DIR/data/template"
mkdir -p "$SCRIPT_DIR/logs/zone3"
mkdir -p "$SCRIPT_DIR/logs/zone2"
mkdir -p "$SCRIPT_DIR/ssh"

echo "[1/3] 目录结构已创建"

# 检查SSH密钥
if [ -f "$SCRIPT_DIR/ssh/id_rsa" ]; then
    echo "[2/3] SSH密钥: OK (simulation/ssh/id_rsa 已存在)"
else
    echo "[2/3] SSH密钥: 缺失"
    echo "       需要SSH私钥用于Zone3拉取腾讯云数据"
    echo "       请将私钥放到: $SCRIPT_DIR/ssh/id_rsa"
    echo ""
    echo "       获取方式: sshpass -p 'yzz0216yhAAAA' scp root@49.232.246.73:/root/.ssh/id_rsa $SCRIPT_DIR/ssh/id_rsa"
fi

# 检查模板文件
if [ -f "$SCRIPT_DIR/data/template/template_predict_input.csv" ]; then
    echo "[3/3] 预测模板: OK (template_predict_input.csv 已存在)"
else
    echo "[3/3] 预测模板: 缺失"
    echo "       Zone2处理器需要此文件做列对齐"
    echo "       请放到: $SCRIPT_DIR/data/template/template_predict_input.csv"
fi

echo ""
echo "=== 初始化完成 ==="
echo "启动: docker-compose -f simulation-compose.yaml up -d"
