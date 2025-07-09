<template>
  <el-upload
    ref="modelupload"
    class="upload-demo"
    drag
    action=""
    :before-upload="beforeUpload"
    :disabled="processing"
    :accept="acceptedFileTypes"
    multiple
  >
    <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
    <template #tip>
      <div class="el-upload__tip">支持的文件格式: {{ acceptedExtensions }}</div>
    </template>
  </el-upload>
</template>

<script>
export default {
  name: 'ModelUploader',
  props: {
    processing: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      acceptedExtensions: '.joblib',
      acceptedFileTypes: '.joblib',
      modelFile: null, // 用来保存模型文件
      scalerFile: null, // 用来保存 scaler 文件
    };
  },
  methods: {
    beforeUpload(file) {
      const isJoblib = file.name.endsWith('.joblib'); // 只允许 .joblib 格式的文件
      const isLt500M = file.size / 1024 / 1024 < 500; // 文件大小限制为 500MB

      if (!isJoblib) {
        this.$message.error('只能上传 .joblib 格式的文件！');
        return false;
      }

      if (!isLt500M) {
        this.$message.error('文件大小不能超过500MB！');
        return false;
      }

      // 如果是模型文件
      if (!this.modelFile) {
        this.modelFile = file;
        this.$emit('model-selected', file); // 触发模型文件事件
      }
      // 如果是 scaler 文件
      else if (!this.scalerFile) {
        this.scalerFile = file;
        this.$emit('scaler-selected', file); // 触发 scaler 文件事件
      } else {
        this.$message.error('只能上传一个模型文件和一个 scaler 文件！');
        return false;
      }

      return false; // 阻止自动上传
    },

    // 校验是否上传了模型文件
    validateUpload() {
      if (!this.modelFile) {
        this.$message.error('请上传至少一个模型文件！');
        return false;
      }
      return true;
    }
  }
};
</script>

<style scoped>
.upload-demo {
  border: 1px dashed #d9d9d9;
  padding: 20px;
  text-align: center;
  cursor: pointer;
}
.el-upload__text {
  font-size: 14px;
  color: #666;
}
.el-upload__tip {
  font-size: 12px;
  color: #999;
}
</style>
