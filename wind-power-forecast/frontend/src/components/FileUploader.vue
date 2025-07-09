<!-- src/components/FileUploader.vue -->
<template>
  <div class="upload-container">
    <input
      ref="fileInput"
      type="file"
      :accept="acceptedFormats.map(format => `.${format}`).join(',')"
      style="display: none"
      @change="handleFileChange"
    >
    <div 
      class="upload-dragger"
      :class="{ 'is-disabled': processing, 'is-dragover': isDragover }"
      @click="triggerFileInput"
      @drop.prevent="handleDrop"
      @dragover.prevent="handleDragover"
      @dragleave.prevent="handleDragleave"
    >
      <div class="upload-content">
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="upload-text">
          {{ uploadText || '将文件拖到此处，或点击上传' }}
        </div>
        <div class="upload-tip" v-if="acceptedFormats.length">
          支持的文件格式: {{ acceptedFormats.join(', ') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { ref, onMounted } from 'vue'

export default {
  name: 'FileUploader',
  components: {
    UploadFilled
  },
  props: {
    processing: {
      type: Boolean,
      default: false
    },
    acceptedFormats: {
      type: Array,
      default: () => []
    },
    uploadText: {
      type: String,
      default: ''
    }
  },
  setup(props, { emit }) {
    const fileInput = ref(null)
    const isDragover = ref(false)

    const validateFile = (file) => {
      if (!file) return false
      
      if (props.acceptedFormats.length) {
        const extension = file.name.split('.').pop().toLowerCase()
        if (!props.acceptedFormats.includes(extension)) {
          ElMessage.error(`只支持 ${props.acceptedFormats.join(', ')} 格式的文件！`)
          return false
        }
      }
      return true
    }

    const triggerFileInput = () => {
      if (props.processing) return
      
      if (fileInput.value) {
        fileInput.value.click()
      } else {
        ElMessage.error('上传组件初始化失败，请刷新页面重试')
      }
    }

    const handleFileChange = (event) => {
      if (!event.target) return
      
      const file = event.target.files[0]
      if (file && validateFile(file)) {
        emit('file-selected', file)
      }
      // 重置 input 的值，使得选择相同文件时也能触发 change 事件
      event.target.value = ''
    }

    const handleDrop = (event) => {
      if (props.processing) return
      isDragover.value = false
      
      const file = event.dataTransfer?.files[0]
      if (file && validateFile(file)) {
        emit('file-selected', file)
      }
    }

    const handleDragover = () => {
      if (!props.processing) {
        isDragover.value = true
      }
    }

    const handleDragleave = () => {
      isDragover.value = false
    }

    onMounted(() => {
      if (!fileInput.value) {
        console.error('File input element not found')
      }
    })

    return {
      fileInput,
      isDragover,
      triggerFileInput,
      handleFileChange,
      handleDrop,
      handleDragover,
      handleDragleave
    }
  }
}
</script>

<style scoped>
.upload-container {
  width: 100%;
}

.upload-dragger {
  width: 100%;
  height: auto;
  background: #ffffff;
  border: 2px dashed #dcdfe6;
  border-radius: 12px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: all 0.3s;
}

.upload-dragger:hover:not(.is-disabled) {
  border-color: #409eff;
  background: #f5f7fa;
}

.upload-dragger.is-dragover {
  background-color: #f5f7fa;
  border-color: #409eff;
}

.upload-dragger.is-disabled {
  cursor: not-allowed;
  background: #f5f7fa;
  border-color: #e4e7ed;
  opacity: 0.7;
}

.upload-content {
  padding: 32px 16px;
  text-align: center;
}

.el-icon--upload {
  font-size: 48px;
  color: #8c939d;
  margin-bottom: 16px;
}

.upload-text {
  color: #606266;
  font-size: 14px;
  margin-bottom: 8px;
}

.upload-tip {
  color: #86868b;
  font-size: 12px;
}
</style>
