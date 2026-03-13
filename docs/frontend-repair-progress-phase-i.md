# 前后端联动修复进展（阶段 I）

## 本轮目标

- 告警中心真正业务化

## 已完成内容

### 1. 后端新增告警实体与接口

- 新增告警模型 `AlarmRecord`
- 新增接口：
  - `GET /system/alarms`
  - `GET /system/alarms/notifications`
  - `POST /system/alarms/:id/ack`
  - `POST /system/alarms/:id/close`
- 同时注册了 `/api/v1/system/*` 兼容路径

### 2. 告警列表不再只是系统日志快照

- 后端会把系统日志快照归集为首批告警记录，避免新表为空时页面无内容
- 前端页面改为读取真实告警列表
- 支持告警状态：
  - `open`
  - `acked`
  - `closed`

### 3. 前端页面补齐确认/关闭/通知记录

- 页面增加状态筛选
- 表格增加“确认”“关闭”操作
- 新增通知记录表
- 保留 WebSocket 实时消息接入，作为后端告警列表的补充视图

## 影响文件

- `backend/db_models/alarm.py`
- `backend/routes/alarm_router.py`
- `backend/app.py`
- `backend/db_models/__init__.py`
- `frontend/src/api/systemApi.js`
- `frontend/src/components/AlarmCenter.vue`

## 当前实现边界

- 目前仍属于“轻量告警中心”，主要解决告警实体化和操作闭环问题
- WebSocket 实时消息暂时只用于前端追加展示，未自动写回后端告警表
- 告警规则、通知模板、短信网关和批量处置仍未服务端化

## 下一步建议

- 人工修正版本化与历史追踪
- 告警规则配置与通知策略后端化
- 告警与质量标记/审计日志的联动统一
