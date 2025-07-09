<!-- src/components/LoadingIndicator.vue -->
<template>
  <div v-if="visible" class="loading-overlay">
    <div class="loading-content">
      <el-spinner type="spinner" size="large"></el-spinner>
      <span class="loading-message">{{ message }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LoadingIndicator',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    message: {
      type: String,
      default: '加载中...'
    }
  }
};
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(255, 255, 255, 0.9);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.loading-message {
  font-size: 18px;
  color: #409EFF;
  font-weight: bold;
}

.el-spinner {
  font-size: 32px;
}
</style>
