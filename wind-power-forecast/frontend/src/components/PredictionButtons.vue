<!-- src/components/PredictionButtons.vue -->
<template>
  <div class="prediction-buttons">
    <div class="button-grid" :class="{ 'single-row-layout': downloadUrl && !processing }">
      <el-button 
        v-if="!fileId"
        type="primary" 
        @click="confirmAction('upload', '确定要上传数据集吗？')" 
        :disabled="!selectedFile || uploading || processing"
        :loading="uploading"
        class="action-btn"
      >
        上传数据集
      </el-button>
      
      <el-button 
        v-else-if="fileId && (!downloadUrl && !processing)" 
        type="primary" 
        @click="confirmAction('prediction', '确定要开始模型训练吗？\n训练过程可能需要较长时间，请耐心等待。')" 
        :disabled="processing || !fileId"
        :loading="processing"
        class="action-btn"
      >
        <el-icon><Promotion /></el-icon>
        开始模型训练
      </el-button>

      <el-button 
        v-if="processing && !downloadUrl" 
        type="warning" 
        @click="$emit('check-status')" 
        class="action-btn"
      >
        <el-icon><Refresh /></el-icon>
        检查训练状态
      </el-button>
      
      <el-button 
        v-if="downloadUrl"
        type="success" 
        @click="$emit('download-file', downloadUrl)" 
        :disabled="processing"
        class="action-btn"
      >
        <el-icon><Download /></el-icon>
        {{ processing ? '下载预测结果' : '预测结果' }}
      </el-button>
      
      <el-button 
        v-if="reportDownloadUrl"
        type="info" 
        @click="$emit('download-file', reportDownloadUrl)" 
        :disabled="processing"
        class="action-btn"
      >
        <el-icon><Document /></el-icon>
        {{ processing ? '下载评估报告' : '评估报告' }}
      </el-button>
      
      <el-button 
        v-if="modelDownloadUrl"
        type="warning" 
        @click="$emit('download-file', modelDownloadUrl)" 
        :disabled="processing"
        class="action-btn"
      >
        <el-icon><Files /></el-icon>
        {{ processing ? '下载模型文件' : '模型文件' }}
      </el-button>
      
      <el-button 
        v-if="scalerDownloadUrl"
        @click="$emit('download-file', scalerDownloadUrl)" 
        :disabled="processing"
        class="action-btn"
      >
        <el-icon><Collection /></el-icon>
        {{ processing ? '下载标准化器' : '标准化器' }}
      </el-button>
      
      <el-button 
        v-if="fileId && !processing && downloadUrl"
        type="danger" 
        @click="confirmAction('chart', '确定要生成评估图表吗？')" 
        class="action-btn"
      >
        <el-icon><DataAnalysis /></el-icon>
        {{ processing ? '生成评估图表' : '评估图表' }}
      </el-button>
    </div>
  </div>
</template>

<script>
import { Refresh, Download, Document, DataAnalysis, Files, Collection, Promotion } from '@element-plus/icons-vue'

export default {
  name: 'PredictionButtons',
  components: {
    Refresh,
    Download,
    Document,
    DataAnalysis,
    Files,
    Collection,
    Promotion
  },
  props: {
    selectedFile: {
      type: Object,
      default: null
    },
    uploading: {
      type: Boolean,
      default: false
    },
    processing: {
      type: Boolean,
      default: false
    },
    fileId: {
      type: String,
      default: ''
    },
    wfCapacity: {
      type: Number,
      default: 453.5
    },
    downloadUrl: {
      type: String,
      default: ''
    },
    reportDownloadUrl: {
      type: String,
      default: ''
    },
    modelDownloadUrl: {
      type: String,
      default: ''
    },
    scalerDownloadUrl: {
      type: String,
      default: ''
    }
  },
  methods: {
    confirmAction(action, message) {
      this.$confirm(message, '操作确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }).then(() => {
        // 用户点击确定后触发相应事件
        if (action === 'upload') {
          this.$emit('start-upload');
        } else if (action === 'prediction') {
          this.$emit('start-prediction');
        } else if (action === 'chart') {
          this.$emit('fetch-daily-metrics');
        }
      }).catch(() => {
        // 用户点击取消，不执行任何操作
        this.$message({
          type: 'info',
          message: '已取消操作'
        });
      });
    }
  }
};
</script>

<style scoped>
.prediction-buttons {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.button-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: minmax(40px, auto);
  gap: 16px;
  align-items: stretch;
}

.button-grid.single-row-layout {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.button-grid.single-row-layout .action-btn {
  width: auto !important;
  flex-grow: 1;
  max-width: 180px;
}

/* 统一按钮样式 */
.action-btn {
  width: 100% !important;
  height: 100% !important;
  min-height: 40px !important;
  text-align: center !important;
  line-height: 1.2 !important;
  padding: 8px 12px !important;
  border-radius: 4px !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
}

/* 确保按钮内部内容居中 - 增强优先级 */
:deep(.action-btn span) {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
  height: 100% !important;
  text-align: center !important;
}

/* 增强按钮内部文本居中效果 */
:deep(.action-btn .el-button__text) {
  width: 100% !important;
  text-align: center !important;
  display: inline-block !important;
}

/* 按钮图标与文字间距 */
:deep(.el-icon) {
  margin-right: 6px;
  font-size: 16px;
}

/* 添加全局样式覆盖 */
:deep(.el-button) {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
}

:deep(.el-button span) {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
}

@media (max-width: 767px) {
  .button-grid:not(.single-row-layout) {
    grid-template-columns: repeat(2, 1fr);
  }
  .button-grid.single-row-layout {
    /* For smaller screens, single-row might stack if too many buttons or too wide */
    /* flex-direction: column; */ /* Uncomment if stacking is preferred on small screens */
  }
}

@media (max-width: 480px) {
  .button-grid:not(.single-row-layout) {
    grid-template-columns: 1fr;
  }
  .button-grid.single-row-layout {
    /* flex-direction: column; */ /* Uncomment if stacking is preferred on very small screens */
  }
}

.action-btn.el-button--primary {
  background-color: var(--el-color-primary) !important;
  border-color: var(--el-color-primary) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--primary:hover,
.action-btn.el-button--primary:focus {
  background-color: var(--el-color-primary-light-3) !important;
  border-color: var(--el-color-primary-light-3) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--primary:active {
  background-color: var(--el-color-primary-dark-2) !important;
  border-color: var(--el-color-primary-dark-2) !important;
  color: var(--el-color-white) !important;
}

.action-btn.el-button--success {
  background-color: var(--el-color-success) !important;
  border-color: var(--el-color-success) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--success:hover,
.action-btn.el-button--success:focus {
  background-color: var(--el-color-success-light-3) !important;
  border-color: var(--el-color-success-light-3) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--success:active {
  background-color: var(--el-color-success-dark-2) !important;
  border-color: var(--el-color-success-dark-2) !important;
  color: var(--el-color-white) !important;
}

.action-btn.el-button--info {
  background-color: var(--el-color-info) !important;
  border-color: var(--el-color-info) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--info:hover,
.action-btn.el-button--info:focus {
  background-color: var(--el-color-info-light-3) !important;
  border-color: var(--el-color-info-light-3) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--info:active {
  background-color: var(--el-color-info-dark-2) !important;
  border-color: var(--el-color-info-dark-2) !important;
  color: var(--el-color-white) !important;
}

.action-btn.el-button--warning {
  background-color: var(--el-color-warning) !important;
  border-color: var(--el-color-warning) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--warning:hover,
.action-btn.el-button--warning:focus {
  background-color: var(--el-color-warning-light-3) !important;
  border-color: var(--el-color-warning-light-3) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--warning:active {
  background-color: var(--el-color-warning-dark-2) !important;
  border-color: var(--el-color-warning-dark-2) !important;
  color: var(--el-color-white) !important;
}

.action-btn.el-button--danger {
  background-color: var(--el-color-danger) !important;
  border-color: var(--el-color-danger) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--danger:hover,
.action-btn.el-button--danger:focus {
  background-color: var(--el-color-danger-light-3) !important;
  border-color: var(--el-color-danger-light-3) !important;
  color: var(--el-color-white) !important;
}
.action-btn.el-button--danger:active {
  background-color: var(--el-color-danger-dark-2) !important;
  border-color: var(--el-color-danger-dark-2) !important;
  color: var(--el-color-white) !important;
}

/* Override for default button (no type specified, e.g., 下载标准化器) */
.action-btn:not([class*="el-button--primary"]):not([class*="el-button--success"]):not([class*="el-button--warning"]):not([class*="el-button--danger"]):not([class*="el-button--info"]) {
  background-color: var(--el-fill-color-blank) !important;
  color: var(--el-text-color-primary) !important; /* Use primary text color for better visibility on light bg */
  border-color: var(--el-border-color) !important;
}
.action-btn:not([class*="el-button--primary"]):not([class*="el-button--success"]):not([class*="el-button--warning"]):not([class*="el-button--danger"]):not([class*="el-button--info"]):hover,
.action-btn:not([class*="el-button--primary"]):not([class*="el-button--success"]):not([class*="el-button--warning"]):not([class*="el-button--danger"]):not([class*="el-button--info"]):focus {
  color: var(--el-color-primary) !important;
  border-color: var(--el-color-primary-light-7) !important;
  background-color: var(--el-color-primary-light-9) !important;
}
.action-btn:not([class*="el-button--primary"]):not([class*="el-button--success"]):not([class*="el-button--warning"]):not([class*="el-button--danger"]):not([class*="el-button--info"]):active {
  border-color: var(--el-color-primary-dark-2) !important;
  color: var(--el-color-primary-dark-2) !important;
  background-color: var(--el-color-white) !important; /* Ensure active state is distinct */
}

/* Disabled state override for all action buttons to ensure they are not blue */
.action-btn.is-disabled,
.action-btn.is-disabled:hover,
.action-btn.is-disabled:focus {
  background-color: var(--el-button-disabled-bg-color, #f5f7fa) !important; 
  border-color: var(--el-button-disabled-border-color, #e9e9eb) !important;
  color: var(--el-button-disabled-text-color, #c0c4cc) !important;
  /* Reset any type-specific disabled colors if necessary */
}
</style>
