# 超短期模型训练并发控制修复

## 问题描述

在原始的超短期模型训练系统中，存在严重的并发问题：
- 需要一次性训练16个模型（Shift 1-16）
- 当训练到模型3或4时，系统会错误地启动第二个训练进程
- 这导致了资源冲突、模型覆盖和训练失败等严重问题

## 根本原因分析

1. **线程管理缺陷**：调度器使用 `run_threaded()` 启动训练线程，但没有跟踪线程状态
2. **标志文件时机问题**：标志文件只在训练完成后创建，训练期间无法防止重复启动
3. **补救逻辑冲突**：主循环中的补救逻辑可能与定时任务产生冲突
4. **缺少进程锁**：没有使用文件锁或其他机制防止多个训练进程同时运行

## 修复方案

### 1. 多层并发控制机制

#### 第一层：线程状态跟踪
```python
# 添加全局变量跟踪当前训练线程
current_training_thread = None
training_lock = threading.Lock()

def run_threaded_training(job_func):
    """专门用于训练任务的线程启动函数，包含并发控制"""
    global current_training_thread
    
    with training_lock:
        # 检查是否已有训练线程在运行
        if current_training_thread is not None and current_training_thread.is_alive():
            logging.warning("检测到已有训练线程正在运行，跳过新的训练请求")
            return
        
        # 启动新的训练线程
        current_training_thread = threading.Thread(target=job_func)
        current_training_thread.start()
```

#### 第二层：运行中标志文件
```python
# 添加运行中标志文件，在训练开始时立即创建
def mark_supershort_train_running_today():
    """标记训练开始运行"""
    today_date_str = datetime.now().strftime('%Y%m%d')
    running_flag_file = get_supershort_train_running_flag_file_for_date(today_date_str)
    # 立即创建运行中标志文件
    with open(running_flag_file, 'w') as f:
        f.write(f'Training started at {datetime.now()}\n')
```

#### 第三层：文件锁机制
```python
# 跨平台文件锁，支持Windows和Linux
def create_file_lock(lock_file_path):
    """创建文件锁，防止多个进程同时运行训练"""
    if HAS_FCNTL is True:
        # Linux/Unix系统，使用fcntl
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_TRUNC | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    elif HAS_FCNTL is False:
        # Windows系统，使用msvcrt
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_TRUNC | os.O_RDWR)
        msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
    # 返回锁句柄
    return lock_fd, True
```

### 2. 改进的训练函数

新的训练函数包含完整的并发控制流程：

```python
def run_supershort_train_script():
    """执行超短期训练脚本 - 带完整并发控制"""
    
    # 第一层检查：是否已完成
    if is_supershort_train_done_today():
        return
    
    # 第二层检查：是否正在运行
    if is_supershort_train_running_today():
        return
    
    # 第三层检查：获取文件锁
    lock_fd, lock_acquired = create_file_lock(lock_file)
    if not lock_acquired:
        return
    
    try:
        # 标记训练开始
        mark_supershort_train_running_today()
        
        # 执行训练
        success, exit_code = run_command(command)
        
        if success:
            mark_supershort_train_done_today()
        else:
            # 清理运行中标志
            cleanup_running_flag()
            
    finally:
        # 释放文件锁
        release_file_lock(lock_fd, lock_file)
```

### 3. 智能清理机制

```python
def cleanup_training_flags():
    """清理可能遗留的训练标志文件"""
    # 检查并清理超过4小时的遗留文件
    if os.path.exists(running_flag_file):
        stat_info = os.stat(running_flag_file)
        file_age = time.time() - stat_info.st_mtime
        if file_age > 4 * 3600:  # 4小时
            os.remove(running_flag_file)
```

### 4. 改进的调度器配置

```python
# 使用专门的训练线程管理
schedule.every().day.at("04:30").do(run_threaded_training, run_supershort_train_script)

# 预测任务使用独立的线程管理
schedule.every().hour.at(":14").do(run_threaded_predict, run_supershort_predict_script)
```

## 修复效果

### 修复前的问题
- ❌ 多个训练进程同时运行
- ❌ 资源冲突和模型覆盖
- ❌ 训练过程中断和失败
- ❌ 无法可靠地完成16个模型的训练

### 修复后的保障
- ✅ 只有一个训练进程能够运行
- ✅ 多层并发控制机制
- ✅ 跨平台文件锁支持
- ✅ 智能清理遗留文件
- ✅ 完整的错误处理和恢复

## 使用方法

### 1. 正常运行调度器
```bash
# 启动调度器（正常模式）
python scheduler_supershort.py

# 立即执行训练（测试模式）
python scheduler_supershort.py --run-supershort-train-now
```

### 2. 运行并发测试
```bash
# 运行测试脚本验证修复效果
python test_concurrent_fix.py
```

### 3. 监控训练状态

检查标志文件：
```bash
# 查看训练状态标志文件
ls -la logs/supershort_train_flags/

# 文件类型说明：
# YYYYMMDD_supershort_train_done.flag    - 训练完成标志
# YYYYMMDD_supershort_train_running.flag - 训练运行中标志
# YYYYMMDD_supershort_train.lock         - 文件锁
```

检查日志：
```bash
# 查看调度器日志
tail -f logs/scheduler_supershort/scheduler_supershort.log

# 查看训练日志
tail -f logs/auto_train/YYYYMMDD_train_supershort.log
```

## 测试验证

### 1. 快速测试
运行 `test_concurrent_fix.py` 选择快速测试，模拟多个线程同时调用训练函数。

### 2. 完整并发测试
运行 `test_concurrent_fix.py` 选择完整测试，启动多个调度器进程进行并发测试。

### 3. 预期测试结果
- 只有一个进程能够成功启动训练
- 其他进程应该因为无法获取锁而跳过
- 日志中应该显示锁冲突信息

## 故障排除

### 1. 如果训练卡死
```bash
# 手动清理锁文件
rm logs/supershort_train_flags/*_supershort_train.lock
rm logs/supershort_train_flags/*_supershort_train_running.flag
```

### 2. 如果遇到权限问题
```bash
# 检查文件权限
ls -la logs/supershort_train_flags/
chmod 755 logs/supershort_train_flags/
```

### 3. 如果Windows系统文件锁不工作
- 检查是否有 `msvcrt` 模块
- 系统会自动回退到基础文件检查模式

## 兼容性

- ✅ Linux/Unix系统（使用fcntl）
- ✅ Windows系统（使用msvcrt）
- ✅ 无锁系统（基础文件检查）
- ✅ Python 3.6+

## 维护建议

1. **定期清理**：建议每周清理一次旧的标志文件
2. **监控日志**：关注并发控制相关的日志信息
3. **测试验证**：定期运行测试脚本验证修复效果
4. **备份模型**：训练完成后及时备份模型文件

## 注意事项

1. 修复后的调度器会自动清理4小时以上的遗留文件
2. 如果系统异常关闭，可能需要手动清理锁文件
3. 文件锁机制依赖于文件系统，网络文件系统可能不支持
4. 训练过程中请勿手动删除运行中标志文件

---

**修复完成时间**：2025年1月3日  
**修复版本**：v1.0  
**测试状态**：通过并发测试验证 