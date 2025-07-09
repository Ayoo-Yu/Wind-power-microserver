#!/bin/bash

# --- 配置 ---
# 定义脚本和虚拟环境的目标安装基础目录
INSTALL_BASE_DIR="/opt/scripts/ecmwf_fetcher"
# 定义最终的 Python 脚本名称 (主脚本，应包含拉取和转换逻辑)
SCRIPT_NAME="fetch_data_from_c.py"
# 定义状态文件清理脚本名称
CLEANUP_SCRIPT_NAME="cleanup_state.py"
# 定义logrotate配置文件名称
LOGROTATE_CONFIG_NAME="ecmwf_fetcher"
# 定义日志文件路径
LOG_FILE="/var/log/ecmwf_fetcher.log"
# 定义状态文件路径
STATE_FILE_PATH="${INSTALL_BASE_DIR}/downloaded_state.txt" # 在基础目录下
# 定义CSV输出目录 (确保与主脚本中的 CSV_OUTPUT_DIR 匹配)
CSV_OUTPUT_DIR="/path/to/output/csv/on/B/" # <--- 重要: 修改为实际CSV输出路径
# 定义虚拟环境目录名称 (修改为更有意义的名称)
VENV_NAME="ecmwf_fetcher_env" # <--- 修改点
# --- 配置结束 ---

echo ">>> 开始安装 ECMWF 数据获取与转换脚本 (使用虚拟环境: ${VENV_NAME})..." # <--- 修改点: 日志输出

# 获取 install.sh 脚本所在的目录 (即部署包解压后的根目录)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
echo "    部署包路径: ${SCRIPT_DIR}"

# 检查 Python 3 是否可用
echo ">>> 检查 Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "错误：找不到 Python 3 命令。请先在服务器 B 上安装 Python 3。"
    exit 1
fi
PYTHON_EXECUTABLE=$(command -v python3)
echo "    找到 Python 3: ${PYTHON_EXECUTABLE}"

# 检查 SFTP 命令是否可用
echo ">>> 检查 SFTP 命令..."
if ! command -v sftp &> /dev/null; then
    echo "错误：找不到 sftp 命令。请先在服务器 B 上安装 OpenSSH 客户端。"
    exit 1
fi
SFTP_EXECUTABLE=$(command -v sftp)
echo "    找到 SFTP: ${SFTP_EXECUTABLE}"

# 创建目标安装目录 (如果不存在)
echo ">>> 创建安装目录: ${INSTALL_BASE_DIR}"
mkdir -p "${INSTALL_BASE_DIR}"
if [ $? -ne 0 ]; then
    echo "错误：创建安装目录失败，请检查权限。"
    exit 1
fi

# --- 创建 Python 虚拟环境 ---
VENV_DIR="${INSTALL_BASE_DIR}/${VENV_NAME}" # <--- 使用新的 VENV_NAME
echo ">>> 创建 Python 虚拟环境 (${VENV_NAME})..."
if [ ! -d "${VENV_DIR}" ]; then
    ${PYTHON_EXECUTABLE} -m venv "${VENV_DIR}"
    if [ $? -ne 0 ]; then
        echo "错误：创建虚拟环境失败。"
        exit 1
    fi
    echo "    虚拟环境已创建在: ${VENV_DIR}"
else
    echo "    虚拟环境已存在: ${VENV_DIR}"
fi

# --- 在虚拟环境中安装依赖 ---
echo ">>> 在虚拟环境中 (${VENV_NAME}) 安装依赖库..."
# 优先使用 requirements.txt 文件（如果存在于部署包中）
REQUIREMENTS_FILE="${SCRIPT_DIR}/requirements.txt"
PYTHON_IN_VENV="${VENV_DIR}/bin/python3" # <--- 路径会自动更新
PIP_IN_VENV="${VENV_DIR}/bin/pip"       # <--- 路径会自动更新

if [ -f "${REQUIREMENTS_FILE}" ]; then
    echo "    发现 requirements.txt，开始安装..."
    ${PIP_IN_VENV} install -r "${REQUIREMENTS_FILE}"
    if [ $? -ne 0 ]; then
        echo "警告：使用 requirements.txt 安装依赖库失败。请检查文件内容和网络连接。"
    else
         echo "    使用 requirements.txt 安装依赖成功。"
    fi
else
    echo "    未找到 requirements.txt，尝试直接安装核心依赖 (pandas, numpy)..."
    ${PIP_IN_VENV} install pandas numpy
    if [ $? -ne 0 ]; then
        echo "错误：直接安装核心依赖库 (pandas, numpy) 失败。请检查网络连接或手动安装。"
        exit 1
    else
         echo "    直接安装核心依赖成功。"
    fi
fi

# --- 复制脚本文件 ---
FINAL_SCRIPT_PATH="${INSTALL_BASE_DIR}/${SCRIPT_NAME}"
echo ">>> 复制主脚本到: ${FINAL_SCRIPT_PATH}"
cp "${SCRIPT_DIR}/${SCRIPT_NAME}" "${FINAL_SCRIPT_PATH}"
# chmod +x "${FINAL_SCRIPT_PATH}" # Python 脚本通常不需要执行权限

# --- 安装维护脚本和配置 ---
echo ">>> 设置维护工具..."

# 复制状态文件清理脚本
FINAL_CLEANUP_PATH="${INSTALL_BASE_DIR}/${CLEANUP_SCRIPT_NAME}"
if [ -f "${SCRIPT_DIR}/${CLEANUP_SCRIPT_NAME}" ]; then
    echo ">>> 复制状态文件清理脚本到: ${FINAL_CLEANUP_PATH}"
    cp "${SCRIPT_DIR}/${CLEANUP_SCRIPT_NAME}" "${FINAL_CLEANUP_PATH}"
else
    echo "错误：无法找到清理脚本 ${CLEANUP_SCRIPT_NAME}，请确保它与主脚本在同一目录"
    exit 1
fi

# 创建logrotate配置 (逻辑不变)
LOGROTATE_CONFIG="/etc/logrotate.d/${LOGROTATE_CONFIG_NAME}"
if [ ! -f "${LOGROTATE_CONFIG}" ]; then
    echo ">>> 创建logrotate配置..."
    SOURCE_LOGROTATE_FILE="${SCRIPT_DIR}/${LOGROTATE_CONFIG_NAME}.conf"
    if [ -f "${SOURCE_LOGROTATE_FILE}" ]; then
        cp "${SOURCE_LOGROTATE_FILE}" "${LOGROTATE_CONFIG}"
        echo "    使用部署包中的 logrotate 配置。"
    else
        cat > "${LOGROTATE_CONFIG}" << EOF
# /etc/logrotate.d/${LOGROTATE_CONFIG_NAME}
${LOG_FILE} {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root # 根据实际运行用户调整权限，或让应用自行创建
    sharedscripts
    postrotate
        # 不需要特殊操作
    endscript
}
EOF
        echo "    创建默认 logrotate 配置。"
    fi
    chmod 644 "${LOGROTATE_CONFIG}"
    echo "    logrotate配置已安装到: ${LOGROTATE_CONFIG}"
else
    echo "    logrotate配置已存在: ${LOGROTATE_CONFIG}"
fi

# 设置每月清理状态文件的cron任务 (使用虚拟环境的 Python)
echo ">>> 设置状态文件清理的cron任务..."
CRON_CLEANUP_JOB="0 0 1 * * ${PYTHON_IN_VENV} ${FINAL_CLEANUP_PATH} --keep-days 180 >> /var/log/ecmwf_state_cleanup.log 2>&1" # <--- 路径会自动更新

# 检查是否已设置cron任务
if crontab -l 2>/dev/null | grep -q "${CLEANUP_SCRIPT_NAME}"; then
    echo "    状态清理cron任务已存在 (请确认是否使用了正确的 Python 路径: ${PYTHON_IN_VENV})" # <--- 更新提示信息
else
    echo "    添加状态清理cron任务..."
    (crontab -l 2>/dev/null; echo "${CRON_CLEANUP_JOB}") > /tmp/ecmwf_crontab
    crontab /tmp/ecmwf_crontab
    rm -f /tmp/ecmwf_crontab
    echo "    每月自动清理任务已设置 (保留最近180天的记录)"
fi

echo ""
echo ">>> 安装和维护任务配置完成！"
echo "--------------------------------------------------"
echo ">>> 后续重要步骤 (请务必执行):"
echo "1. 配置脚本参数: 使用编辑器 (如 nano 或 vim) 修改 ${FINAL_SCRIPT_PATH}"
echo "   例如: sudo nano ${FINAL_SCRIPT_PATH}"
echo "   ***务必修改*** 以下配置项为实际值:"
# (配置项列表不变)
echo "   - REMOTE_HOST, REMOTE_PORT, REMOTE_USER, SSH_KEY_PATH"
echo "   - REMOTE_BASE_DIR"
echo "   - LOCAL_DOWNLOAD_DIR, LOCAL_TEMP_DIR, CSV_OUTPUT_DIR" # <-- 强调CSV输出目录
echo "   - STATE_FILE, LOG_FILE, LOCK_FILE"
echo ""
echo "2. 配置SSH密钥认证 (服务器 B -> 服务器 C): (与之前相同)"
echo ""
echo "3. 创建所需目录并设置权限:"
echo "   - sudo mkdir -p ${LOCAL_DOWNLOAD_DIR}"
echo "   - sudo mkdir -p ${LOCAL_TEMP_DIR}"
echo "   - sudo mkdir -p ${CSV_OUTPUT_DIR}" # <-- 确保创建CSV目录
echo "   - sudo mkdir -p $(dirname ${STATE_FILE})"
echo "   - sudo mkdir -p $(dirname ${LOG_FILE})"
echo "   - 确定运行脚本的用户和组 (例如 'ecs-user:ecs-user')"
echo "   - sudo chown -R ecs-user:ecs-user ${INSTALL_BASE_DIR}" # <-- 确保包含新的venv目录 ${VENV_NAME}
echo "   - sudo chown -R ecs-user:ecs-user ${LOCAL_DOWNLOAD_DIR}"
echo "   - sudo chown -R ecs-user:ecs-user ${CSV_OUTPUT_DIR}" # <-- 确保CSV目录权限正确
echo "   - sudo touch ${LOG_FILE} && sudo chown ecs-user:ecs-user ${LOG_FILE}"
echo "   - sudo touch /var/log/ecmwf_state_cleanup.log && sudo chown ecs-user:ecs-user /var/log/ecmwf_state_cleanup.log"
echo "   - (请将 'ecs-user:ecs-user' 替换为实际的用户和组)"
echo ""
echo "4. 手动测试脚本:"
echo "   以运行脚本的用户身份执行 (注意使用虚拟环境的 Python: ${PYTHON_IN_VENV}):" # <--- 更新提示信息
echo "   sudo -u ecs-user ${PYTHON_IN_VENV} ${FINAL_SCRIPT_PATH}"
echo "   检查日志 (${LOG_FILE})、E文本下载目录 (${LOCAL_DOWNLOAD_DIR}) 和 CSV 输出目录 (${CSV_OUTPUT_DIR})。"
echo ""
echo "5. 设置 Cron 定时任务 (例如，每 15 分钟运行一次):"
echo "   以运行脚本的用户身份编辑 crontab: sudo crontab -e -u ecs-user"
echo "   添加类似下面的一行 (注意使用虚拟环境的 Python: ${PYTHON_IN_VENV}):" # <--- 更新提示信息
echo "   */15 * * * * ${PYTHON_IN_VENV} ${FINAL_SCRIPT_PATH} >> /var/log/ecmwf_fetcher_cron.log 2>&1"
echo "   创建并设置 Cron 日志文件的权限:"
echo "   sudo touch /var/log/ecmwf_fetcher_cron.log"
echo "   sudo chown ecs-user:ecs-user /var/log/ecmwf_fetcher_cron.log"
echo "   sudo chmod 644 /var/log/ecmwf_fetcher_cron.log"
echo "   (请根据需要调整执行频率 '*/15' 和用户 'ecs-user')"
echo ""
echo "6. 维护工具使用: (与之前类似)"
echo "   - 日志轮转会自动由系统处理"
echo "   - 状态文件将每月自动清理"
echo "   - 测试状态文件清理 (使用虚拟环境Python: ${PYTHON_IN_VENV}): ${PYTHON_IN_VENV} ${FINAL_CLEANUP_PATH} --keep-days 180 --dry-run" # <--- 更新提示信息
echo "   - 手动运行日志轮转: sudo logrotate -f ${LOGROTATE_CONFIG}"
echo "--------------------------------------------------"

exit 0