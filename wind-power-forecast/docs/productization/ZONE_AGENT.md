# 电力分区统一代理

## 定位

现有二区、三区脚本继续承担协议连接和格式转换等适配工作。文件去重、校验、断点状态、跨区传递和故障恢复统一交给分区代理。这样可以保留已验证的场站接口代码，同时消除每个脚本自建状态文件和重试逻辑的情况。

代理只依赖 Python 标准库。离线服务器无需执行 `pip install`。

## 安装

1. 在有网构建环境生成离线发布包并完成审批。
2. 在目标 Linux 服务器执行 `verify-release.sh`。
3. 使用 root 权限运行：

```bash
bash wind-power-forecast/deploy/zone-agent/install-zone-agent.sh
```

4. 修改 `/etc/windpower-zone-agent.env`。
5. 将接入令牌写入 `/etc/windpower-zone-agent.token`，文件权限保持 0640。
6. 启动并检查：

```bash
systemctl restart windpower-zone-agent.service
systemctl status windpower-zone-agent.service
journalctl -u windpower-zone-agent.service -f
```

## 两种下一跳

`AGENT_TARGET_MODE=http` 适合允许单向 HTTP 的分区边界。目标为统一接入 API。

`AGENT_TARGET_MODE=directory` 适合安全设备映射目录、人工摆渡介质或单向文件通道。目标目录仍采用同一套可靠队列结构。

## 场站适配步骤

1. 原协议脚本先写临时文件。
2. 文件完整关闭后原子改名到 `AGENT_INPUT_DIR`。
3. 代理等待 `AGENT_MINIMUM_AGE_SECONDS`，确认文件稳定后封装。
4. 下一跳校验清单、大小和 SHA256。
5. 业务适配器从接入箱读取数据并写入业务表。

## 排障

```bash
PYTHONPATH=/opt/windpower-zone-agent/current \
python3 -m integration.cli status \
  --spool /var/lib/windpower-zone-agent/spool
```

`retry` 表示临时链路故障。`quarantine` 表示需要人工处理的数据或配置问题。不要直接修改数据包内容，修正源文件或配置后生成新消息。
