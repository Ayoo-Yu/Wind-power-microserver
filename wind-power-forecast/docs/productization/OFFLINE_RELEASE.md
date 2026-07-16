# 内网离线发布与更新

## 构建原则

发布包只能在受控构建机生成。构建机固定依赖版本、容器基础镜像和源代码提交。场站服务器只执行校验、镜像导入和容器切换，不访问公网软件仓库。

## 生成发布包

```powershell
.\deploy\export-release.ps1 `
  -ReleaseVersion 2026.07.15-rc1 `
  -SigningKeyPath C:\secure\release-private.pem `
  -SigningPublicKeyPath C:\secure\release-public.pem
```

默认拒绝从有未提交改动的工作树构建。紧急验证可显式使用 `-AllowDirty`，生成的清单会记录 `dirty: true`，此类包不得进入正式场站。

发布目录包含：

1. 固定标签的数据库和业务镜像归档。
2. 可选的种子数据备份。
3. 精简部署脚本、Compose 文件和分区代理。
4. `release-manifest.json`，记录 Git 提交、镜像标签和每个制品摘要。
5. `application-sbom.cdx.json`，记录实际预测镜像 Python 包、前端锁定依赖和容器镜像摘要。
6. `SHA256SUMS` 与可选签名文件。

## 场站接收

```bash
cd /approved-media/release_2026.07.15-rc1
bash wind-power-forecast/deploy/verify-release.sh .
```

正式场站要求签名时执行：

```bash
REQUIRE_RELEASE_SIGNATURE=true bash wind-power-forecast/deploy/verify-release.sh .
```

校验失败时停止安装并保留介质，记录文件名、期望摘要和实际摘要。签名公钥应通过独立审批渠道预置或核验指纹。

## 首次安装

```bash
cd wind-power-forecast/deploy
cp .env.example .env
vi .env
bash deploy.sh install
bash deploy.sh start
bash deploy.sh status
```

`.env` 中必须替换数据库密码、JWT 密钥和接入令牌。实际接入验收完成后再打开对应能力开关。

全新数据库首次安装时，还需要临时填写 `BOOTSTRAP_ADMIN_PASSWORD`。密码长度至少为 16 个字符，且不能使用示例值或历史默认值。管理员创建并确认能够登录后，立即清空该变量并再次执行 `bash deploy.sh start`，让后端容器在不保留引导密码的配置下重新创建。已有数据库升级时保持该变量为空，启动过程不会修改现有管理员密码。

需要人工重置管理员密码时，在后端容器的交互终端执行 `python -m reset_admin`。自动化运维只能通过一次性只读文件设置 `RESET_ADMIN_PASSWORD_FILE`，执行完成后应立即销毁该文件。

启动前会自动执行：

```bash
bash validate-field-config.sh .env
```

校验规则包括场站模式、严格迁移、固定镜像标签、数据库与 JWT 密钥强度、模型自动审批关闭，以及 SCADA 和统一接入的网段与令牌要求。校验失败时不会启动业务容器。

## 更新

1. 记录当前发布版本和镜像标签。
2. 备份数据库，导出当前 `.env`，确认磁盘空间。
3. 校验新发布包。
4. 执行新包的 `deploy.sh install` 导入固定标签镜像。
5. 将旧 `.env` 中的场站密钥合并到新模板。
6. 在业务窗口执行 `deploy.sh stop` 和新版本 `deploy.sh start`。
7. 完成健康检查、预测抽样、接入测试和上报回执测试。
8. 在运行控制中心确认 SCADA、NWP、预测输入和上报队列均达到验收状态。

## 回滚

每个发布包使用独立镜像标签。回滚时切回上一发布目录，恢复对应 `.env` 镜像变量并重新启动。数据库结构通过 Alembic 管理，应用升级前先在生产副本执行迁移演练。涉及不可逆数据变换时优先采用向前修复迁移，避免在现场直接删除新结构。
