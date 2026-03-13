# 前后端联动修复进展 - Phase O

## 本轮目标

补齐【统一告警中心】中尚未完成的“告警规则配置”和“通知策略配置”能力，让页面从“告警列表查看页”进一步升级为“告警治理配置页”。

## 已完成内容

### 1. 后端新增告警规则与通知策略持久化模型

涉及文件：
- [backend/db_models/alarm.py](D:/my-vue-project/wind-power-forecast/backend/db_models/alarm.py)
- [backend/db_models/__init__.py](D:/my-vue-project/wind-power-forecast/backend/db_models/__init__.py)

新增模型：
- `AlarmRule`
- `AlarmNotificationPolicy`

当前能力：
- 告警规则可持久化保存名称、模块、等级、关键词、启停状态、描述
- 通知策略可持久化保存渠道、接收人、适用等级、启停状态、静默时间、备注

### 2. 后端新增规则/策略 CRUD 接口

涉及文件：
- [backend/routes/alarm_router.py](D:/my-vue-project/wind-power-forecast/backend/routes/alarm_router.py)

新增接口：
- `GET /api/v1/alarm-rules`
- `POST /api/v1/alarm-rules`
- `PUT /api/v1/alarm-rules/<rule_id>`
- `DELETE /api/v1/alarm-rules/<rule_id>`
- `GET /api/v1/alarm-policies`
- `POST /api/v1/alarm-policies`
- `PUT /api/v1/alarm-policies/<policy_id>`
- `DELETE /api/v1/alarm-policies/<policy_id>`

补充说明：
- 首次进入时，如果数据库中不存在规则和策略，后端会自动初始化一组默认配置
- 历史告警列表、通知记录、确认、关闭接口继续保留

### 3. 前端补齐规则/策略 API 封装

涉及文件：
- [frontend/src/api/systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js)

新增函数：
- `getAlarmRules`
- `createAlarmRule`
- `updateAlarmRule`
- `deleteAlarmRule`
- `getAlarmPolicies`
- `createAlarmPolicy`
- `updateAlarmPolicy`
- `deleteAlarmPolicy`

### 4. 告警中心页面接入规则/策略管理

涉及文件：
- [frontend/src/components/AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)

新增页面能力：
- 展示告警规则列表
- 新增/编辑/删除告警规则
- 启用/停用告警规则
- 展示通知策略列表
- 新增/编辑/删除通知策略
- 启用/停用通知策略

保留能力：
- 告警列表查看
- 告警确认
- 告警关闭
- 通知记录查看
- WebSocket 实时消息接入

## 当前状态判断

本轮完成后，【统一告警中心】已经从“只看告警结果”扩展为“结果 + 规则 + 通知策略”的一体化页面。

但仍有两个边界需要明确：
- 当前“告警规则”主要用于前端与后端配置沉淀，尚未形成复杂规则引擎
- 当前告警生成仍保留基于系统日志的种子补数逻辑，后续如需完全业务化，还需引入更明确的告警事件源

## 验证结果

### 前端

执行：

```bash
npm.cmd run lint -- src/components/AlarmCenter.vue src/api/systemApi.js
```

结果：
- 通过，无 lint 报错

### 后端

执行：

```bash
python -m py_compile backend/db_models/alarm.py backend/routes/alarm_router.py backend/db_models/__init__.py
```

结果：
- 通过，无语法错误

## 对剩余计划的影响

本轮完成后，剩余未完全收口的重点进一步集中到：
- 人工修正版本比对 / 回滚增强
- 页面口径统一
- 页面 query 联动统一
