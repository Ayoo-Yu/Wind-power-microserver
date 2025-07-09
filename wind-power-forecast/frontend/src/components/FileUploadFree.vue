<!-- src/components/FileUploader.vue -->
<template>
  <el-upload
    ref="upload"
    class="upload-demo"
    drag
    action=""
    :before-upload="beforeUpload"
    :disabled="processing"
    :accept="acceptTypes"
  >
    <div class="el-upload__text">
      将文件拖到此处，或<em>点击上传</em>
    </div>
  </el-upload>
</template>

<script>
export default {
  name: 'FileUploader',
  props: {
    processing: {
      type: Boolean,
      default: false
    },
    // 将 acceptedFormats 定义为数组，方便多种格式的支持
    acceptedFormats: {
      type: Array,
      default: () => ['csv']
    }
  },
  computed: {
    // 生成 el-upload 需要的 accept 属性字符串
    acceptTypes() {
      return this.acceptedFormats.map(format => {
        // 根据文件扩展名返回对应的 MIME 类型
        switch (format.toLowerCase()) {
          case 'csv':
            return 'text/csv';
          case 'xls':
            return 'application/vnd.ms-excel';
          case 'xlsx':
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
          // 添加更多格式的 MIME 类型
          default:
            return `.${format}`;
        }
      }).join(',');
    }
  },
  methods: {
    beforeUpload(file) {
      const fileExtension = file.name.split('.').pop().toLowerCase();
      const isAccepted = this.acceptedFormats.map(format => format.toLowerCase()).includes(fileExtension);
      const isLt500M = file.size / 1024 / 1024 < 500;

      if (!isAccepted) {
        this.$message.error(`只能上传以下格式的文件：${this.acceptedFormats.join(', ').toUpperCase()}！`);
      }
      if (!isLt500M) {
        this.$message.error('文件大小不能超过500MB！');
      }
      if (isAccepted && isLt500M) {
        this.$emit('file-selected', file);
        return false; // 阻止自动上传
      }
      return false;
    }
  }
};
</script>

<style scoped>
/* 您的样式 */
</style>
