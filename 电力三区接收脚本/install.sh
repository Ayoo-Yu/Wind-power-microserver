#!/bin/bash

# --- 配置 ---
# 定义脚本和虚拟环境的目标安装基础目录
INSTALL_BASE_DIR="/opt/scripts/ecmwf_fetcher" 
# 定义最终的 Python 脚本名称
SCRIPT_NAME="fetch_data_from_c.py"
# 定义状态文件清理脚本名称
CLEANUP_SCRIPT_NAME="cleanup_state.py"
# 定义logrotate配置文件名称
LOGROTATE_CONFIG_NAME="ecmwf_fetcher"
# 定义日志文件路径
LOG_FILE="/var/log/ecmwf_fetcher.log"
# 定义状态文件路径
STATE_FILE_PATH="/opt/scripts/ecmwf_fetcher/downloaded_state.txt"
# --- 配置结束 ---

echo ">>> 开始安装 ECMWF 数据获取脚本..."

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

# 将主 Python 脚本复制到安装目录
FINAL_SCRIPT_PATH="${INSTALL_BASE_DIR}/${SCRIPT_NAME}"
echo ">>> 复制主脚本到: ${FINAL_SCRIPT_PATH}"
cp "${SCRIPT_DIR}/${SCRIPT_NAME}" "${FINAL_SCRIPT_PATH}"
chmod +x "${FINAL_SCRIPT_PATH}" # 添加执行权限

# --- 安装维护脚本和配置 ---
echo ">>> 设置维护工具..."

# 复制状态文件清理脚本
FINAL_CLEANUP_PATH="${INSTALL_BASE_DIR}/${CLEANUP_SCRIPT_NAME}"
if [ -f "${SCRIPT_DIR}/${CLEANUP_SCRIPT_NAME}" ]; then
    echo ">>> 复制状态文件清理脚本到: ${FINAL_CLEANUP_PATH}"
    cp "${SCRIPT_DIR}/${CLEANUP_SCRIPT_NAME}" "${FINAL_CLEANUP_PATH}"
    chmod +x "${FINAL_CLEANUP_PATH}"
else
    echo ">>> 无法找到清理脚本 ${CLEANUP_SCRIPT_NAME}，请确保它与主脚本在同一目录"
    exit 1
fi

# 创建logrotate配置
LOGROTATE_CONFIG="/etc/logrotate.d/${LOGROTATE_CONFIG_NAME}"
if [ ! -f "${LOGROTATE_CONFIG}" ]; then
    echo ">>> 创建logrotate配置..."
    if [ -f "${SCRIPT_DIR}/${LOGROTATE_CONFIG_NAME}" ]; then
        # 如果源目录中有配置文件，直接复制
        cp "${SCRIPT_DIR}/${LOGROTATE_CONFIG_NAME}" "${LOGROTATE_CONFIG}"
    else
        # 否则创建一个新的配置
        cat > "${LOGROTATE_CONFIG}" << EOF
# /etc/logrotate.d/ecmwf_fetcher
# 配置文件用于管理ECMWF数据获取脚本的日志轮转

${LOG_FILE} {
    daily                  # 每天轮转一次
    rotate 14              # 保留14份旧日志文件(约两周)
    compress               # 压缩旧的日志文件 (使用gzip)
    delaycompress          # 下次轮转时再压缩上一份日志
    missingok              # 如果日志文件不存在，不报错
    notifempty             # 如果日志文件为空，不进行轮转
    create 0640 root root  # 创建新日志文件，指定权限和所有者/组
    sharedscripts          
    postrotate
        # 这里不需要特别操作，Python脚本每次运行时会重新打开日志文件
    endscript
}
EOF
    fi
    chmod 644 "${LOGROTATE_CONFIG}"
    echo "    logrotate配置已安装到: ${LOGROTATE_CONFIG}"
else
    echo "    logrotate配置已存在: ${LOGROTATE_CONFIG}"
fi

# 设置每月清理状态文件的cron任务
echo ">>> 设置状态文件清理的cron任务..."
CRON_CLEANUP_JOB="0 0 1 * * python3 ${FINAL_CLEANUP_PATH} --keep-days 180 >> /var/log/ecmwf_state_cleanup.log 2>&1"

# 检查是否已设置cron任务
if crontab -l 2>/dev/null | grep -q "${CLEANUP_SCRIPT_NAME}"; then
    echo "    状态清理cron任务已存在"
else
    echo "    添加状态清理cron任务..."
    # 将cron任务添加到临时文件
    (crontab -l 2>/dev/null; echo "${CRON_CLEANUP_JOB}") > /tmp/ecmwf_crontab
    # 应用新的crontab
    crontab /tmp/ecmwf_crontab
    # 清理临时文件
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
echo "   - REMOTE_HOST (服务器 C 的 IP 或主机名)"
echo "   - REMOTE_PORT (服务器 C 的 SSH 端口)"
echo "   - REMOTE_USER (用于连接服务器 C 的 SFTP 用户名)"
echo "   - SSH_KEY_PATH (用于连接服务器 C 的SSH私钥路径，比如 /home/username/.ssh/id_rsa)"
echo "   - LOCAL_DOWNLOAD_DIR (服务器 B 上存放下载文件的目录)"
echo "   - LOCAL_TEMP_DIR (服务器 B 上的临时下载目录)"
echo "   - STATE_FILE (服务器 B 上状态文件的路径)"
echo "   - LOG_FILE (服务器 B 上日志文件的路径)"
echo "   - LOCK_FILE (服务器 B 上锁文件的路径)"
echo ""
echo "2. 配置SSH密钥认证 (服务器 B -> 服务器 C):"
echo "   - 生成SSH密钥对: ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa"
echo "   - 将公钥复制到服务器 C: ssh-copy-id -i ~/.ssh/id_rsa.pub ${REMOTE_USER}@${REMOTE_HOST}"
echo "   - 或手动添加公钥到服务器 C 的 ~/.ssh/authorized_keys 文件"
echo "   - 确保在脚本中设置的 SSH_KEY_PATH 指向正确的私钥路径"
echo "   - 测试SSH密钥连接: ssh -i ~/.ssh/id_rsa ${REMOTE_USER}@${REMOTE_HOST}"
echo "   - 注意: 脚本使用系统SFTP命令进行文件传输，确保执行脚本的用户有权限访问SSH密钥"
echo ""
echo "3. 创建所需目录并设置权限:"
echo "   - sudo mkdir -p /data/from_server_c/temp"
echo "   - sudo mkdir -p /opt/scripts/ecmwf_fetcher" # 状态文件目录 (可能已创建)
echo "   - sudo mkdir -p /var/log" # 日志文件父目录
echo "   - 确定运行脚本的用户和组 (例如 'windpower:windgroup')"
echo "   - sudo chown windpower:windgroup /data/from_server_c -R"
echo "   - sudo chown windpower:windgroup /opt/scripts/ecmwf_fetcher -R"
echo "   - sudo touch /var/log/ecmwf_fetcher.log && sudo chown windpower:windgroup /var/log/ecmwf_fetcher.log" # 创建并授权日志文件
echo "   - sudo touch /var/log/ecmwf_state_cleanup.log && sudo chown windpower:windgroup /var/log/ecmwf_state_cleanup.log" # 创建状态清理日志文件
echo "   - sudo chown windpower:windgroup /tmp/ecmwf_fetcher.lock" # 确保锁文件可被用户读写 (如果需要，或放在用户可写目录下)
echo "   (请将 'windpower:windgroup' 替换为实际的用户和组)"
echo ""
echo "4. 手动测试脚本:"
echo "   sudo -u windpower python3 ${FINAL_SCRIPT_PATH}"
echo "   检查日志 (${LOG_FILE}) 和下载目录 (${LOCAL_DOWNLOAD_DIR})。"
echo ""
echo "5. 设置 Cron 定时任务 (例如，每 15 分钟运行一次):"
echo "   以运行脚本的用户身份编辑 crontab: sudo crontab -e -u windpower"
echo "   添加类似下面的一行:"
echo "   */15 * * * * python3 ${FINAL_SCRIPT_PATH} >> /var/log/ecmwf_fetcher_cron.log 2>&1"
echo "   添加类似下面的一行:"
echo "   sudo touch /var/log/ecmwf_fetcher_cron.log"
echo "   sudo chown ecs-user:ecs-user /var/log/ecmwf_fetcher_cron.log"
echo "   sudo chmod 644 /var/log/ecmwf_fetcher_cron.log"
echo "   (请根据需要调整执行频率 '*/15')"
echo ""
echo "6. 维护工具使用:"
echo "   - 日志轮转会自动由系统处理 (通常每天)"
echo "   - 状态文件将每月1日自动清理，保留最近180天的记录"
echo "   - 测试状态文件清理: python3 ${FINAL_CLEANUP_PATH} --keep-days 180 --dry-run"
echo "   - 手动运行日志轮转: sudo logrotate -f ${LOGROTATE_CONFIG}"
echo "--------------------------------------------------"

exit 0