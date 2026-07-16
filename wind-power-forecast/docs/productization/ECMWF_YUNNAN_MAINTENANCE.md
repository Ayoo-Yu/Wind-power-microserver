# 云南 ECMWF 服务收敛记录

## 变更结果

2026 年 7 月 16 日 13:11 CST，在接收目录无待处理 GRIB 且两个进程 CPU 时间稳定的窗口完成服务收敛。

| 项目 | 变更后状态 |
| --- | --- |
| 保留服务 | `ecmwf-yunnan-processor.service`，enabled、active |
| 保留进程 | PID `32372`，维护前后未重启 |
| 旧服务 | `ecmwf-processor-yunnan.service`，disabled、非运行 |
| 云南处理进程数 | 1 |
| 接收目录待处理文件 | 0 |
| 巡检脚本 SHA256 | `699e8c49d22ebdab34664bd843bf8f0089e36679c5ff378700ef82bcaf100ce2` |
| 最新 DQYC SHA256 | `d17d9775f7b5b043bc87777d5fdd5ecdfea7e5e2e4f82dea79e6afe61cee27cb` |
| root 定时任务 SHA256 | `4a6b185636d7f09ddf89d302d6b0f835feb30d7d7be82d9957e01380589eaa24` |
| 远端备份目录 | `/root/ecmwf-maintenance-backups/20260716_131105` |

保留服务在维护前已经持续处理生产批次。此次操作只停用重复消费者并替换每日只读巡检，未修改 GRIB 处理代码、E 文本生成代码、预测算法、历史产物和定时任务。

## 巡检口径

新版 `/ECMWF/health_check.sh` 每日检查以下内容：

1. 主服务处于运行状态。
2. 旧服务处于停止状态。
3. 云南处理进程总数为 1。
4. 昨日 18Z 批次存在 DQYC。
5. DQYC 至少包含 508 个连续 15 分钟时刻。
6. 文件具有 1046 列、55 个唯一格点和 19 个变量，列集合与顺序符合生产契约。
7. 所有气象值均为有限数值。
8. 文件名时间与首行时间一致。

巡检保留原 cron 调用路径，日志继续写入 `/ECMWF/logs/health_check.log`。维护后的首次巡检结果为通过。

## 回滚方法

远端备份保存了两个 systemd 单元、原巡检脚本、变更前启用状态、变更前运行状态和独立回滚脚本。需要恢复时执行：

```bash
bash /root/ecmwf-maintenance-backups/20260716_131105/rollback.sh \
  --backup-dir /root/ecmwf-maintenance-backups/20260716_131105
```

回滚会先停止两个服务，恢复原文件和启用状态，再按照备份记录恢复运行状态。执行前仍应确认 `/ECMWF/yunnan_test` 没有待处理 GRIB。
