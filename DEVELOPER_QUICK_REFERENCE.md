# 开发者快速参考

## 常用命令
```bash
# 后端
python app.py

# 前端
npm install
npm run serve
```

## 常见路径
- 后端入口：`wind-power-forecast/backend/app.py`
- 前端入口：`wind-power-forecast/frontend/src/main.js`
- 兼容路由：`wind-power-forecast/backend/routes/v1_compat.py`

## 调试优先级
1. 先看 `/health`。
2. 再看后端日志。
3. 再检查数据库与对象存储连接。

## 提交前检查
- 代码无乱码。
- 页面面板文案为中文。
- 关键接口可用。
- 变更说明完整。
