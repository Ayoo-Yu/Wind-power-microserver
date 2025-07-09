<!-- src/App.vue -->
<template>
  <div class="app-container">
    <router-view></router-view>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { ensureFormControlsTextColor } from './utils/styleCheck';

// 此处不再需要背景切换逻辑，由 AppLayout 中统一控制

// 在组件挂载后检查并修复文字颜色
onMounted(() => {
  ensureFormControlsTextColor();
});
</script>

<style>
/* 全局样式 */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  background: var(--background-dark);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 全局覆盖Element Plus组件的文字颜色 - 最高优先级 */
body .el-input__inner, 
body .el-textarea__inner,
body .el-select-dropdown__item,
body .el-date-editor .el-input__inner,
body .el-date-editor .el-range-input,
body .el-form-item__label,
body .el-table,
body .el-table th, 
body .el-table tr, 
body .el-table td,
body .el-dropdown-menu__item,
body .el-dialog,
body .el-drawer,
body .el-popover,
body .el-tooltip,
body .el-input input,
body .el-input__wrapper input,
body .el-select input,
body .el-date-picker input,
body .el-picker-panel,
body .el-date-table td,
body .el-date-table th {
  color: #333 !important;
}

/* 确保白色背景下的文字颜色为深色 */
body .el-date-picker {
  color: #333 !important;
}

/* 主题色定义 */
:root {
  --background-dark: #0A0A0A;
  --card-dark: #1C1C1E;
  --text-primary: #FFFFFF;
  --text-secondary: rgba(255, 255, 255, 0.7);
  --border-color: rgba(255, 255, 255, 0.1);
  --primary-gradient: linear-gradient(135deg, #34C759 0%, #2ECC71 100%);
  --card-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  --hover-shadow: 0 12px 32px rgba(0, 0, 0, 0.3);
}

/* 卡片基础样式 */
.el-card {
  background: var(--card-dark);
  border: 1px solid var(--border-color);
  border-radius: 16px;
}

/* 按钮样式 */
.el-button {
  border-radius: 8px;
  height: 40px;
  font-weight: 500;
  letter-spacing: 0.3px;
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
}

.el-button span {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
}

.el-button--primary {
  background: var(--primary-gradient);
  border: none;
}

/* 输入框样式 */
.el-input__inner {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

/* 全局标题样式 - 增加优先级 */
.page-title,
h1.page-title,
.container .page-title {
  font-size: 42px !important;
  font-weight: 600;
  color: #1d1d1f;
  text-align: center;
  margin-bottom: 48px;
  letter-spacing: -0.003em;
}

/* 日期时间选择器面板底部按钮容器样式 */
.el-picker-panel__footer,
.el-time-panel__footer {
  display: flex !important;
  justify-content: flex-end !important;
  align-items: center !important;
  padding: 8px 12px !important;
  text-align: right !important;
  border-top: 1px solid #EBEEF5 !important;
}

/* 底部按钮样式 */
.el-picker-panel__footer .el-button,
.el-time-panel__footer .el-button,
.el-picker-panel__footer button,
.el-time-panel__footer button,
.el-picker-panel__link-btn,
.el-time-panel__btn {
  display: inline-block !important;
  float: none !important;
  margin: 0 0 0 8px !important;
  height: 32px !important;
  line-height: 32px !important;
  font-size: 14px !important;
  padding: 0 15px !important;
  border-radius: 4px !important;
  vertical-align: middle !important;
  width: auto !important;
  text-align: center !important;
}

/* 使用更高特异性选择器覆盖元素样式 */
body .el-date-picker__footer button,
body .el-date-range-picker__footer button,
body .el-time-panel__footer button {
  display: inline-block !important;
  position: static !important;
}

.app-container {
  min-height: 100vh;
  background: #ffffff;
  transition: background 0.3s ease;
}

/* 确保内容在动画背景上方 */
.main-content {
  position: relative;
  z-index: 1;
}

/* 开关样式优化 */
:deep(.el-switch) {
  margin-left: 8px;
}

:deep(.el-switch__label) {
  color: #1d1d1f;
  font-size: 14px;
}
</style>
