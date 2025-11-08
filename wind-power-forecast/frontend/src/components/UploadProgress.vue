<!-- src/components/UploadProgress.vue -->
 <!-- 展示文件上传进度 -->
<template>
  <transition name="progress-fade">
    <div
      v-if="visible"
      class="upload-progress digital-panel digital-panel--interactive"
    >
      <div class="progress-header">
        <span class="progress-label">上传进度</span>
        <span class="progress-value">{{ percentage }}%</span>
      </div>
      <el-progress
        :percentage="percentage"
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
  }
};
</script>

<style scoped>
.upload-progress {
  padding: 18px 20px;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 260px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.progress-label {
  font-size: 14px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.progress-value {
  font-family: 'Rajdhani', 'Inter', sans-serif;
  font-size: 20px;
  letter-spacing: 0.1em;
  color: var(--text-primary);
}

.upload-progress :deep(.el-progress-bar__outer) {
  background: rgba(66, 195, 255, 0.16);
  border-radius: 999px;
}

.upload-progress :deep(.el-progress-bar__inner) {
  background-image: linear-gradient(90deg, rgba(66, 195, 255, 0.85), rgba(34, 246, 170, 0.85));
  box-shadow: 0 0 18px rgba(66, 195, 255, 0.45);
  border-radius: 999px;
  transition: width 0.3s ease;
}

.upload-progress :deep(.el-progress__text) {
  color: var(--text-primary);
  font-family: 'Rajdhani', 'Inter', sans-serif;
  letter-spacing: 0.1em;
}

.progress-fade-enter-active,
.progress-fade-leave-active {
  transition: all 0.2s ease;
}

.progress-fade-enter-from,
.progress-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
