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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Rajdhani:wght@500;600;700&display=swap');

:root {
  --app-bg: radial-gradient(circle at 20% 20%, rgba(20, 148, 255, 0.18), transparent 55%),
            radial-gradient(circle at 80% 10%, rgba(0, 208, 132, 0.22), transparent 50%),
            #030712;
  --grid-overlay: rgba(35, 143, 255, 0.08);
  --surface-glass: rgba(10, 22, 45, 0.82);
  --surface-card: rgba(13, 28, 54, 0.9);
  --surface-border: rgba(66, 195, 255, 0.18);
  --surface-border-strong: rgba(66, 195, 255, 0.32);
  --surface-shadow: 0 24px 80px rgba(2, 16, 42, 0.55);
  --text-primary: #ECF6FF;
  --text-secondary: rgba(236, 246, 255, 0.64);
  --text-muted: rgba(236, 246, 255, 0.45);
  --accent-primary: #38C4FF;
  --accent-secondary: #22F6AA;
  --accent-gradient: linear-gradient(135deg, #38C4FF 0%, #22F6AA 100%);
  --accent-gradient-strong: linear-gradient(135deg, #23E0FF 0%, #1EFFA3 50%, #2B7BFF 100%);
  --accent-shadow: 0 12px 45px rgba(34, 246, 170, 0.35);
  --accent-glow-soft: 0 0 22px rgba(56, 196, 255, 0.25);
  --divider-color: rgba(255, 255, 255, 0.08);
  --chart-blue: #3AA4FF;
  --chart-green: #21E3AA;
  --chart-purple: #776BFF;
  --status-success: #3AD68B;
  --status-warning: #F7C341;
  --status-danger: #FF5D7A;

  --el-color-primary: #38C4FF;
  --el-color-primary-light-3: #6DD7FF;
  --el-color-primary-light-5: #94E4FF;
  --el-color-primary-light-7: #BDEEFF;
  --el-color-primary-light-9: #E6F9FF;
  --el-color-primary-dark-2: #2398CC;
  --el-bg-color-overlay: rgba(10, 22, 45, 0.92);
  --el-bg-color: rgba(7, 17, 35, 0.92);
  --el-text-color-regular: var(--text-secondary);
  --el-text-color-primary: var(--text-primary);
  --el-text-color-secondary: var(--text-muted);
  --el-border-color: rgba(56, 196, 255, 0.2);
  --el-border-color-light: rgba(56, 196, 255, 0.12);
  --el-border-color-lighter: rgba(56, 196, 255, 0.08);
  --el-border-radius-base: 14px;
}

html, body {
  height: 100%;
}

body {
  margin: 0;
  font-family: 'Inter', 'Rajdhani', 'Segoe UI', 'Roboto', sans-serif;
  background: var(--app-bg);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(90deg, transparent 23%, var(--grid-overlay) 24%, transparent 25%),
    linear-gradient(0deg, transparent 23%, var(--grid-overlay) 24%, transparent 25%),
    radial-gradient(circle at 50% 20%, rgba(0, 140, 255, 0.18), transparent 60%),
    radial-gradient(circle at 10% 80%, rgba(0, 255, 178, 0.12), transparent 55%);
  background-size: 160px 160px, 160px 160px, 100% 100%, 100% 100%;
  opacity: 0.65;
  pointer-events: none;
  z-index: 0;
}

#app {
  position: relative;
  min-height: 100%;
  isolation: isolate;
}

.app-container {
  min-height: 100vh;
  background: transparent;
  transition: background 0.6s ease, box-shadow 0.6s ease;
}

.el-card {
  background: var(--surface-card) !important;
  border: 1px solid var(--surface-border) !important;
  border-radius: 18px !important;
  box-shadow: var(--surface-shadow) !important;
  backdrop-filter: blur(18px);
}

.el-card__header {
  border-bottom: 1px solid var(--divider-color) !important;
}

.el-button {
  border-radius: 12px !important;
  height: 44px;
  font-weight: 600;
  letter-spacing: 0.32px;
  display: inline-flex !important;
  justify-content: center !important;
  align-items: center !important;
  padding: 0 22px !important;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.el-button span {
  display: inline-flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
}

.el-button--primary {
  background: var(--accent-gradient-strong) !important;
  border: none !important;
  box-shadow: var(--accent-shadow);
}

.el-button--primary:hover {
  transform: translateY(-2px) scale(1.01);
  box-shadow: 0 18px 55px rgba(34, 246, 170, 0.45);
}

.el-button--default,
.el-button--info,
.el-button--success,
.el-button--warning,
.el-button--danger {
  background: rgba(16, 42, 76, 0.92) !important;
  border: 1px solid var(--surface-border) !important;
  color: var(--text-primary) !important;
}

.el-button--default:hover,
.el-button--info:hover,
.el-button--success:hover,
.el-button--warning:hover,
.el-button--danger:hover {
  border-color: var(--surface-border-strong) !important;
  box-shadow: var(--accent-glow-soft);
}

.el-input__wrapper,
.el-textarea,
.el-select .el-input__wrapper,
.el-date-editor,
.el-input__inner {
  background: rgba(6, 18, 36, 0.82) !important;
  border-radius: 12px !important;
  border: 1px solid var(--surface-border) !important;
  box-shadow: inset 0 0 0 1px rgba(18, 155, 255, 0.12);
  color: var(--text-primary) !important;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.el-input__wrapper:hover,
.el-select .el-input__wrapper.is-focus,
.el-input.is-focus .el-input__wrapper,
.el-input__wrapper.is-focus {
  border-color: var(--surface-border-strong) !important;
  box-shadow: 0 0 16px rgba(56, 196, 255, 0.28);
}

.el-input__inner::placeholder {
  color: var(--text-muted) !important;
}

input,
textarea,
.el-select-dropdown__item,
.el-date-table td,
.el-picker-panel,
.el-dropdown-menu__item,
.el-table,
.el-table th,
.el-table tr,
.el-table td,
.el-dialog,
.el-drawer,
.el-popover,
.el-tooltip {
  color: var(--text-primary) !important;
}

.el-table,
.el-table__body-wrapper,
.el-table th,
.el-table tr,
.el-table td {
  background-color: transparent !important;
  border-color: var(--el-border-color) !important;
}

.el-table--border::before,
.el-table--group::before {
  background-color: transparent !important;
}

.el-table thead th {
  background-color: rgba(25, 49, 86, 0.95) !important;
  color: var(--text-secondary) !important;
}

.el-table__body tr:hover>td {
  background: rgba(33, 164, 255, 0.08) !important;
}

.page-title,
h1.page-title,
.container .page-title {
  font-family: 'Rajdhani', 'Inter', sans-serif;
  font-size: 44px !important;
  font-weight: 600;
  color: var(--text-primary) !important;
  text-align: center;
  margin-bottom: 36px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.el-picker-panel__footer,
.el-time-panel__footer {
  display: flex !important;
  justify-content: flex-end !important;
  align-items: center !important;
  padding: 8px 12px !important;
  text-align: right !important;
  border-top: 1px solid var(--divider-color) !important;
  background: rgba(8, 21, 40, 0.92) !important;
}

.el-picker-panel__footer .el-button,
.el-time-panel__footer .el-button,
.el-picker-panel__footer button,
.el-time-panel__footer button,
.el-picker-panel__link-btn,
.el-time-panel__btn {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  margin-left: 8px !important;
  height: 34px !important;
  padding: 0 16px !important;
  border-radius: 10px !important;
  width: auto !important;
}

body .el-date-picker__footer button,
body .el-date-range-picker__footer button,
body .el-time-panel__footer button {
  position: static !important;
}

.main-content {
  position: relative;
  z-index: 1;
}

*::selection {
  background: rgba(56, 196, 255, 0.28);
  color: var(--text-primary);
}

body::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

body::-webkit-scrollbar-track {
  background: rgba(6, 18, 36, 0.4);
}

body::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(56, 196, 255, 0.9) 0%, rgba(34, 246, 170, 0.9) 100%);
  border-radius: 999px;
  border: 2px solid rgba(3, 12, 24, 0.6);
}

body::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(56, 196, 255, 1) 0%, rgba(34, 246, 170, 1) 100%);
}

:deep(.el-switch) {
  margin-left: 8px;
}

:deep(.el-switch__label) {
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
