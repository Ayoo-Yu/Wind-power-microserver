# 前后端联动修复进展 F

## 本轮目标

- 将【系统基础配置】从前端 `localStorage` 过渡方案切换为后端持久化方案
- 新增系统基础配置后端模型与接口
- 将前端页面改为真实读取、保存、恢复默认

## 已完成修复

### 1. 后端新增系统配置模型

涉及文件：

- `D:\my-vue-project\wind-power-forecast\backend\db_models\system_settings.py`
- `D:\my-vue-project\wind-power-forecast\backend\db_models\__init__.py`

新增模型：

- `SystemSetting`

当前字段：

- `id`
- `settings_key`
- `payload`
- `updated_by`
- `created_at`
- `updated_at`

说明：

- 当前以 `settings_key = default` 存储系统基础配置快照
- `payload` 中保存节假日、字典配置、保留策略三块结构化数据

### 2. 后端新增系统基础配置接口

涉及文件：

- `D:\my-vue-project\wind-power-forecast\backend\routes\system_settings_router.py`
- `D:\my-vue-project\wind-power-forecast\backend\app.py`
- `D:\my-vue-project\wind-power-forecast\backend\routes\v1_compat.py`

新增接口：

- `GET /api/system/settings`
- `PUT /api/system/settings`
- `POST /api/system/settings/reset`

兼容接口：

- `GET /api/v1/system/settings`
- `PUT /api/v1/system/settings`
- `POST /api/v1/system/settings/reset`

当前能力：

- 获取系统基础配置
- 保存系统基础配置
- 恢复默认配置
- 返回最近更新人和更新时间

### 3. 前端系统接口封装补齐

涉及文件：

- `D:\my-vue-project\wind-power-forecast\frontend\src\api\systemApi.js`

新增方法：

- `getSystemSettings`
- `saveSystemSettings`
- `resetSystemSettings`

### 4. 系统基础配置页切到真实后端

涉及文件：

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\SystemSettings.vue`

本轮改动：

- 去掉“localStorage 过渡方案”提示
- 页面初始化时读取后端配置
- 保存按钮改为真实调用后端接口
- 恢复默认改为真实调用后端接口
- 保存成功后展示更新时间与最近操作人
- 节假日、字典、保留策略统一提交到后端

## 当前页面状态

【系统基础配置】已从“仅本地浏览器存储”升级为：

- 真实后端读取
- 真实后端保存
- 真实后端恢复默认
- 最近修改人/修改时间回显

## 仍未完成的点

- 目前系统配置仍采用“单条 JSON 快照”模式，尚未拆成更细粒度的业务表
- 节假日与字典尚未和其他业务页面形成联动消费
- 页面未接入服务端审计日志

## 验证情况

前端：

- `npm.cmd run lint -- src/components/SystemSettings.vue src/api/systemApi.js`
- 结果：`No lint errors found`

后端：

- `python -m py_compile ...system_settings.py ...system_settings_router.py ...v1_compat.py ...app.py`
- 结果：编译通过

## 下一步建议

下一刀建议继续做：

- 用户扩展元数据后端化

原因：

- 当前用户页里的手机号、管理场站范围仍是前端本地补充数据
- 这是“账号体系去本地化”的关键剩余项
