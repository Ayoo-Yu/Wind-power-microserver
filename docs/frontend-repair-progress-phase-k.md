# 前后端联动修复进展 Phase K

## 本轮目标

- 收口【场站管理】页面最后一块仍依赖前端本地存储的扩展配置。
- 将场站扩展字段从前端 `localStorage` 迁移到后端持久化，统一由场站接口返回。

## 已完成修复

### 1. 后端新增场站扩展配置模型

- 新增文件：
  - `D:\my-vue-project\wind-power-forecast\backend\db_models\farm_profile.py`
- 新增模型：
  - `FarmProfileConfig`
- 持久化内容：
  - `commissioning_date`
  - `province`
  - `region`
  - `longitude`
  - `latitude`
  - `altitude`
  - `turbine_count`
  - `hub_height`
  - `met_tower_count`
  - `power_curve_file_name`
  - `power_curve_url`
  - `supershort_model`
  - `short_model`
  - `lower_power_limit`
  - `curtailment_threshold`
  - `point_act_power`
  - `point_wind_speed`
  - `point_avail_count`
  - `scada_status`
  - `nwp_status`
  - `current_actual_power`

### 2. 场站管理接口改为读写扩展配置

- 修改文件：
  - `D:\my-vue-project\wind-power-forecast\backend\routes\farm_management.py`
  - `D:\my-vue-project\wind-power-forecast\backend\db_models\__init__.py`
- 新增能力：
  - 场站列表接口返回主表字段 + 扩展配置字段
  - 场站详情接口返回主表字段 + 扩展配置字段
  - 场站创建时同步写入扩展配置
  - 场站更新时同步更新扩展配置
  - 场站删除时同步清理扩展配置

### 3. 前端场站管理页停止依赖本地缓存作为数据源

- 修改文件：
  - `D:\my-vue-project\wind-power-forecast\frontend\src\components\FarmManagement.vue`
- 调整结果：
  - 页面表单提交仍继续携带扩展字段
  - 页面展示优先使用后端返回的扩展字段
  - 原本的本地缓存辅助函数不再读写 `localStorage`
  - 页面“卡片 / 表格 / 地图散点视图”都改为消费统一后端返回

## 验证

### 前端

```bash
npm.cmd run lint -- src/components/FarmManagement.vue
```

结果：

- `No lint errors found`

### 后端

```bash
python -m py_compile "D:\my-vue-project\wind-power-forecast\backend\db_models\farm_profile.py" "D:\my-vue-project\wind-power-forecast\backend\routes\farm_management.py" "D:\my-vue-project\wind-power-forecast\backend\db_models\__init__.py"
```

结果：

- 通过

## 本轮结论

- 【场站管理】已从“后端主数据 + 前端本地扩展配置”混合页，调整为“后端统一返回主数据和扩展配置”的页面。
- 这轮收口后，之前修复计划里“场站扩展配置去本地化”这一项已经完成第一轮落地。

## 仍建议后续继续处理的非阻塞尾项

- `ReportManagement.vue` 仍有一组报文配置元数据通过 `localStorage` 过渡保存。
- `systemSettingsStore.js`、`dataQualityStore.js` 目前已不是主数据源，可在后续做清理或下线。
