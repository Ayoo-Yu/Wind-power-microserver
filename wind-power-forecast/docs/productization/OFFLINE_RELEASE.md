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
5. `SHA256SUMS` 与可选签名文件。

## 场站接收

```bash
cd /approved-media/release_2026.07.15-rc1
bash wind-power-forecast/deploy/verify-release.sh .
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

`.env` 中必须替换数据库密码、JWT 密钥、Flower 密码和接入令牌。实际接入验收完成后再打开对应能力开关。

## 更新

1. 记录当前发布版本和镜像标签。
2. 备份数据库，导出当前 `.env`，确认磁盘空间。
3. 校验新发布包。
4. 执行新包的 `deploy.sh install` 导入固定标签镜像。
5. 将旧 `.env` 中的场站密钥合并到新模板。
6. 在业务窗口执行 `deploy.sh stop` 和新版本 `deploy.sh start`。
7. 完成健康检查、预测抽样、接入测试和上报回执测试。

## 回滚

每个发布包使用独立镜像标签。回滚时切回上一发布目录，恢复对应 `.env` 镜像变量并重新启动。数据库结构变化需要单独的向前兼容和回退脚本。当前项目仍以 `Base.metadata.create_all` 补建表，正式大版本上线前应补齐版本化数据库迁移。
