<!-- src/components/UploadProgress.vue -->
 <!-- 展示文件上传进度 -->
<template>
  <div v-if="visible" class="upload-progress">
    <span class="progress-label">文件上传进度条</span>
    <el-progress :percentage="percentage" :status="status"></el-progress>
    <span>{{ percentage }}%</span>
  </div>
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
  margin-top: 10px;
  display: flex;
  align-items: center;
}
.upload-progress span {
  margin-left: 10px;
}
.progress-label {
  font-size:15px;
  margin-right: 10px;
}
</style>
