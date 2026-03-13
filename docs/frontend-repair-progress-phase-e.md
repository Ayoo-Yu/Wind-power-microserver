# 前后端联动修复进展 E

## 本轮目标

- 将【数据质量与限电标记】从前端 `localStorage` 过渡方案切换为后端持久化方案
- 建立质量标记的后端模型、接口、`/api/v1` 兼容路由
- 将前端页面改为真实调用质量标记 CRUD 接口

## 已完成修复

### 1. 后端新增数据质量标记模型

涉及文件：

- `D:\my-vue-project\wind-power-forecast\backend\db_models\report_config.py`
- `D:\my-vue-project\wind-power-forecast\backend\db_models\__init__.py`

新增模型：

- `DataQualityMarker`

当前字段：

- `id`
- `farm_code`
- `start_time`
- `end_time`
- `marker_type`
- `reason`
- `exclude_from_score`
- `created_by`
- `created_at`
- `updated_at`

说明：

- 该表用于承接质量异常、限电停机、设备维护等人工标记
- 项目启动时会通过现有 `Base.metadata.create_all(...)` 自动建表

### 2. 后端新增质量标记 CRUD 接口

涉及文件：

- `D:\my-vue-project\wind-power-forecast\backend\routes\report_management_router.py`
- `D:\my-vue-project\wind-power-forecast\backend\routes\v1_compat.py`

新增接口：

- `GET /api/report/quality-markers`
- `POST /api/report/quality-markers`
- `PUT /api/report/quality-markers/<marker_id>`
- `DELETE /api/report/quality-markers/<marker_id>`

兼容接口：

- `GET /api/v1/report/quality-markers`
- `POST /api/v1/report/quality-markers`
- `PUT /api/v1/report/quality-markers/<marker_id>`
- `DELETE /api/v1/report/quality-markers/<marker_id>`

当前能力：

- 支持按 `farm_code` 过滤
- 支持按 `month=YYYY-MM` 过滤
- 支持创建、删除、更新质量标记
- 返回时会补充 `farm_name`

### 3. 前端 API 封装补齐

涉及文件：

- `D:\my-vue-project\wind-power-forecast\frontend\src\api\reportApi.js`

新增方法：

- `getQualityMarkers`
- `createQualityMarker`
- `updateQualityMarker`
- `deleteQualityMarker`

说明：

- 继续沿用现有 `v1 -> legacy` fallback 策略

### 4. 数据质量页切到真实后端标记

涉及文件：

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\DataQualityManagement.vue`

本轮改动：

- 去掉“标记存储：localStorage 过渡方案”提示
- 标记列表改为从后端接口加载
- 新增标记改为调用后端创建接口
- 新增删除操作，直接删除后端标记
- 顶部统计卡片继续使用真实 `report/statistics` 数据
- 场站、月份变化时自动刷新统计和标记列表
- 创建人从当前登录用户信息中提取

## 当前页面状态

【数据质量与限电标记】已从“前端静态卡片 + 本地标记数组”升级为：

- 真实统计数据
- 真实后端标记列表
- 真实后端新增/删除能力

## 仍未完成的点

- 页面尚未提供“编辑质量标记”入口，虽然接口已补 `PUT`
- 质量标记尚未与准确率报表、功率对比页面形成服务端联动剔除逻辑
- 标记类型字典仍写死在前端页面中，尚未中心化
- 尚未补后端操作审计

## 验证情况

前端：

- `npm.cmd run lint -- src/components/DataQualityManagement.vue src/api/reportApi.js`
- 结果：`No lint errors found`

后端：

- `python -m py_compile ...report_config.py ...__init__.py ...report_management_router.py ...v1_compat.py`
- 结果：编译通过

## 下一步建议

下一刀建议继续做：

- 系统基础配置后端化

原因：

- 当前系统配置仍完全依赖 `localStorage`
- 这会继续影响“可部署”“可审计”“多用户共享配置”三个核心目标
