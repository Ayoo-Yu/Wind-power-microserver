<!-- src/components/UploadProgress.vue -->
 <!-- 展示文件上传进度 -->
<template>
  <transition name="progress-fade">
    <div
      v-if="visible"
      :class="[
        'upload-progress',
        'digital-panel',
        'digital-panel--interactive',
        statusClass,
        { 'panel--pulse': status === 'success' }
      ]"
    >
      <div class="progress-header">
        <span class="progress-label">上传进度</span>
        <span class="progress-value" :class="{ 'progress-value--complete': status === 'success' }">
          {{ progressValue }}%
        </span>
      </div>
      <div class="progress-ambient">
        <div class="progress-ambient__line" :style="{ width: progressValue + '%' }" />
      </div>
      <el-progress
        :percentage="progressValue"
        :status="status"
        :stroke-width="10"
        :show-text="false"
      />
    </div>
  </transition>
</template>

<script>
export default {
  name: 'UploadProgress',
  props: {
    visible: {
      type: Boolean,
      required: true
    },
    percentage: {
      type: Number,
      required: true
    },
    status: {
      type: String,
      default: 'active' // 'active', 'success'
    }
  },
  computed: {
    progressValue() {
      const value = Number.isFinite(this.percentage) ? this.percentage : 0
      return Math.min(100, Math.max(0, Math.round(value)))
    },
    statusClass() {
      return this.status === 'success' ? 'upload-progress--success' : 'upload-progress--active'
    }
  }
};
</script>

<style scoped>
.upload-progress {
  position: relative;
  padding: 20px 22px;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: hidden;
  isolation: isolate;
}

.upload-progress::before {
  content: '';
  position: absolute;
  inset: -120% -120% auto;
  height: 240%;
  background: conic-gradient(from 0deg, rgba(66, 195, 255, 0), rgba(66, 195, 255, 0.25), rgba(34, 246, 170, 0), rgba(66, 195, 255, 0));
  animation: uploadShimmer 8s linear infinite;
  opacity: 0.4;
  pointer-events: none;
  z-index: -1;
}

.upload-progress--success::before {
  background: conic-gradient(from 0deg, rgba(34, 246, 170, 0.05), rgba(34, 246, 170, 0.4), rgba(34, 246, 170, 0.05));
  animation-duration: 4s;
  opacity: 0.55;
}

.panel--pulse {
  border-color: rgba(66, 195, 255, 0.32) !important;
  box-shadow: 0 22px 54px rgba(34, 246, 170, 0.25);
  animation: panelPulse 0.9s ease;
}

.panel--pulse::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: radial-gradient(circle at 30% 20%, rgba(66, 195, 255, 0.32), transparent 60%);
  opacity: 0.45;
}

@keyframes panelPulse {
  0% {
    box-shadow: 0 0 0 rgba(34, 246, 170, 0.3);
  }
  50% {
    box-shadow: 0 26px 60px rgba(34, 246, 170, 0.45);
  }
  100% {
    box-shadow: 0 0 0 rgba(34, 246, 170, 0.18);
  }
}

@keyframes uploadShimmer {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.progress-label {
  font-size: 13px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.progress-value {
  font-family: 'Rajdhani', 'Inter', sans-serif;
  font-size: 22px;
  letter-spacing: 0.16em;
  color: var(--accent-primary, #38c4ff);
  transition: transform 0.45s ease, color 0.45s ease;
}

.progress-value--complete {
  color: #22f6aa;
  animation: valuePop 0.9s ease;
}

@keyframes valuePop {
  0% {
    transform: scale(0.9);
  }
  55% {
    transform: scale(1.08);
  }
  100% {
    transform: scale(1);
  }
}

.progress-ambient {
  position: relative;
  height: 6px;
  border-radius: 999px;
  background: rgba(66, 195, 255, 0.08);
  overflow: hidden;
}

.progress-ambient__line {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(66, 195, 255, 0.2), rgba(34, 246, 170, 0.45));
  box-shadow: 0 0 18px rgba(66, 195, 255, 0.4);
  transition: width 0.4s ease;
}

.upload-progress :deep(.el-progress-bar__outer) {
  background: rgba(66, 195, 255, 0.14);
  border-radius: 999px;
  overflow: hidden;
}

.upload-progress :deep(.el-progress-bar__inner) {
  background-image: linear-gradient(90deg, rgba(66, 195, 255, 0.85), rgba(34, 246, 170, 0.85));
  box-shadow: 0 0 22px rgba(66, 195, 255, 0.45);
  border-radius: 999px;
  transition: width 0.3s ease;
}

.upload-progress :deep(.el-progress-bar__inner::after) {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.4) 50%, transparent 100%);
  mix-blend-mode: screen;
  animation: barSweep 2.6s ease-in-out infinite;
  opacity: 0.65;
}

@keyframes barSweep {
  0% {
    transform: translateX(-100%);
  }
  50% {
    transform: translateX(0%);
  }
  100% {
    transform: translateX(100%);
  }
}

.upload-progress :deep(.el-progress__text) {
  color: var(--text-primary);
  font-family: 'Rajdhani', 'Inter', sans-serif;
  letter-spacing: 0.1em;
}

.progress-fade-enter-active,
.progress-fade-leave-active {
  transition: all 0.25s ease;
}

.progress-fade-enter-from,
.progress-fade-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}
</style>
