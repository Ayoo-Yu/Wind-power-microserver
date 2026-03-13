# 前后端联动修复进展（阶段 J）

## 本轮目标

- 人工修正版本化与历史追踪

## 已完成内容

### 1. 后端新增人工修正版本模型

- 新增 `ManualInterventionVersion`
- 保存字段包括：
  - 配置 ID
  - 场站编码
  - 报文类型
  - 目标日期
  - 版本名称
  - 修正工具与修正值
  - 修正后的 payload
  - 创建人 / 创建时间
  - 应用人 / 应用时间

### 2. 后端新增版本接口

- `GET /report/manual-intervention/versions`
- `POST /report/manual-intervention/versions`
- `GET /report/manual-intervention/versions/:id`
- `POST /report/manual-intervention/versions/:id/apply`

并补齐了 `/api/v1/report/*` 兼容路径。

### 3. 前端工作台升级为“编辑 + 版本历史 + 上报”闭环

- 保留真实预览加载能力
- 保留修正工具与曲线编辑能力
- 新增版本名称输入
- 新增版本历史表
- 支持一键加载历史版本到当前工作台
- 手工上报与“保存版本”拆成两个动作，不再混在一起

## 影响文件

- `backend/db_models/manual_intervention.py`
- `backend/db_models/__init__.py`
- `backend/routes/report_management_router.py`
- `backend/routes/v1_compat.py`
- `frontend/src/api/reportApi.js`
- `frontend/src/components/ManualInterventionWorkspace.vue`

## 当前实现边界

- “应用版本”当前表示应用到工作台上下文，并记录应用人/应用时间
- 真正发送仍通过现有 `manual-report` 完成
- 还没有做版本差异比对、审批流、版本备注详情页

## 下一步建议

- 告警规则与通知策略配置化
- 场站扩展配置去本地化
- 报表与质量/告警/人工修正之间的统一审计链路
