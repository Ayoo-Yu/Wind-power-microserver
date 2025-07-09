<template>
  <div class="file-info-content">
    <div class="file-details" v-if="fileInfo">
      <div class="info-row">
        <span class="label">文件名称：</span>
        <span class="value">{{ fileInfo.name || '-' }}</span>
      </div>
      <div class="info-row">
        <span class="label">文件大小：</span>
        <span class="value">{{ formatFileSize(fileInfo.size) }}</span>
      </div>
      <div class="info-row">
        <span class="label">文件类型：</span>
        <span class="value">{{ fileInfo.type || '-' }}</span>
      </div>
      <div class="info-row">
        <span class="label">上传时间：</span>
        <span class="value">{{ fileInfo.uploadDate || '-' }}</span>
      </div>
    </div>
    <div class="action-buttons">
      <el-button 
        type="primary" 
        class="action-button" 
        @click="$emit('start-upload')"
        :disabled="!fileInfo"
      >上传文件</el-button>
      <el-button 
        type="danger" 
        class="action-button" 
        @click="$emit('remove-file')"
        :disabled="!fileInfo"
      >删除</el-button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FileInfo',
  props: {
    fileInfo: {
      type: Object,
      required: true
    }
  },
  methods: {
    formatFileSize(bytes) {
      if (!bytes) return '-';
      const units = ['B', 'KB', 'MB', 'GB'];
      let size = bytes;
      let unitIndex = 0;
      
      while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
      }
      
      return `${size.toFixed(2)} ${units[unitIndex]}`;
    }
  }
};
</script>

<style scoped>
.file-info-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.file-details {
  display: grid;
  gap: 12px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  color: #86868b;
  min-width: 80px;
}

.value {
  color: #1d1d1f;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.action-button {
  flex: 1;
  height: 40px !important;  /* 强制统一高度 */
  padding: 0 20px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  transition: all 0.3s ease !important;
}

.action-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 覆盖 el-button 的默认样式 */
:deep(.el-button) {
  margin: 0;
  height: 40px;
  line-height: 40px;
}
</style>