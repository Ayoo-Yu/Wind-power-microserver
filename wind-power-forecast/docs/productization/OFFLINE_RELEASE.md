# 内网离线发布与更新

## 构建原则

发布包只能在受控构建机生成。构建机固定依赖版本、容器基础镜像和源代码提交。场站服务器只执行校验、镜像导入和容器切换，不访问公网软件仓库。

## 生成发布包

```powershell
.\deploy\export-release.ps1 `
  -ReleaseVersion 2026.07.15-rc1 `
  -PackageType Full `
  -SigningKeyPath C:\secure\release-private.pem `
  -SigningPublicKeyPath C:\secure\release-public.pem
```

日常更新包使用：

```powershell
.\deploy\export-release.ps1 `
  -ReleaseVersion 2026.07.15-patch1 `
  -PackageType Upgrade `
  -SigningKeyPath C:\secure\release-private.pem `
  -SigningPublicKeyPath C:\secure\release-public.pem
```

默认拒绝从有未提交改动的工作树构建。紧急验证可显式使用 `-AllowDirty`，生成的清单会记录 `dirty: true`，此类包不得进入正式场站。

发布目录包含：

1. 固定标签的业务镜像归档。
2. 首次安装包中的数据库镜像归档。
3. 首次安装包中的可选种子数据备份。
4. 精简部署脚本、Compose 文件和分区代理。
5. `release-manifest.json`，记录 Git 提交、镜像标签和每个制品摘要。
6. `application-sbom.cdx.json`，记录实际预测镜像 Python 包、前端锁定依赖和容器镜像摘要。
7. `SHA256SUMS` 与可选签名文件。

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

`.env` 中必须替换数据库密码、JWT 密钥、凭据加密密钥和接入令牌。实际接入验收完成后再打开对应能力开关。

`DATA_ROOT` 必须设置为发布包目录外的固定 Linux 绝对路径，例如 `/opt/wind-power/data`。数据库、Redis、模型、日志、E 文本、上传文件和预测输出都放在这个目录下，升级发布包时继续复用。

`CREDENTIAL_ENCRYPTION_KEY` 专门保护上报服务器密码、气象连接密码和私钥口令，长度至少为 32 个字符。该密钥与数据库备份一同保存在受控介质中，访问权限应独立审批。丢失密钥后，已有密文无法恢复。升级包含历史凭据的数据库前必须先配置该密钥，迁移会在同一事务中把原有明文转换为 `enc:v1` 密文。日常更新应沿用原密钥，变更密钥前需要执行专门的重加密流程。

可以在受控运维机生成随机密钥：`python -c "import secrets; print(secrets.token_urlsafe(48))"`。生成后不要写入发布包、源码仓库或普通操作日志。

需要使用只读密钥文件时，可以清空 `CREDENTIAL_ENCRYPTION_KEY` 并设置 `CREDENTIAL_ENCRYPTION_KEY_FILE`。标准 Compose 文件只传递容器内路径，部署方还需通过受控覆盖文件将密钥文件只读挂载到相同路径。

全新数据库首次安装时，还需要临时填写 `BOOTSTRAP_ADMIN_PASSWORD`。密码长度至少为 16 个字符，且不能使用示例值或历史默认值。管理员创建并确认能够登录后，立即清空该变量并再次执行 `bash deploy.sh start`，让后端容器在不保留引导密码的配置下重新创建。已有数据库升级时保持该变量为空，启动过程不会修改现有管理员密码。

需要人工重置管理员密码时，在后端容器的交互终端执行 `python -m reset_admin`。自动化运维只能通过一次性只读文件设置 `RESET_ADMIN_PASSWORD_FILE`，执行完成后应立即销毁该文件。

启动前会自动执行：

```bash
bash validate-field-config.sh .env
```

校验规则包括场站模式、严格迁移、固定镜像标签、数据库、JWT 与凭据加密密钥强度、模型自动审批关闭，以及 SCADA 和统一接入的网段与令牌要求。校验失败时不会启动业务容器。

## 更新

1. 记录当前发布版本和镜像标签。
2. 备份数据库，导出当前 `.env`，确认磁盘空间。
3. 校验新发布包。
4. 执行新包的 `deploy.sh install` 导入固定标签镜像。
5. 将旧 `.env` 中的场站密钥合并到新模板。
6. 确认新 `.env` 继续指向原 `DATA_ROOT`。
7. 在业务窗口执行 `deploy.sh upgrade`。
8. 完成健康检查、预测抽样、接入测试和上报回执测试。
9. 在运行控制中心确认 SCADA、NWP、预测输入和上报队列均达到验收状态。

`upgrade` 会导入业务镜像、执行数据库迁移门禁、重建后端、前端、SCADA Manager、接入处理器和 Celery 服务。它不会导入 `03_seed_data.dump`。只有首次演示库初始化时才执行 `deploy.sh init-seed`。

## 回滚

每个发布包使用独立镜像标签。回滚时切回上一发布目录，恢复对应 `.env` 镜像变量，并执行 `bash deploy.sh upgrade`。数据库结构通过 Alembic 管理，应用升级前先在生产副本执行迁移演练。涉及不可逆数据变换时优先采用向前修复迁移，避免在现场直接删除新结构。
