<!-- src/components/LogViewer.vue -->
<template>
  <div class="log-viewer">
    <div class="log-content" v-html="formattedLogs"></div>
    <div class="log-actions">
      <el-button type="text" size="small" @click="$emit('clear-logs')">
        清空日志
      </el-button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LogViewer',
  props: {
    logs: {
      type: String,
      default: ''
    }
  },
  computed: {
    formattedLogs() {
      return this.logs.replace(/\n/g, '<br>');
    }
  }
};
</script>

<style scoped>
.log-viewer {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: monospace;
}

.log-actions {
  padding: 8px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #ebeef5;
}

:deep(.log-content) {
  line-height: 1.6;
}
</style>
