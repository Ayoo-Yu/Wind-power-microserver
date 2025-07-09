<template>
  <div class="model-selector">
    <!-- 未上传文件时的提示 -->
    <div v-if="!fileId" class="empty-model-selector">
      <el-icon class="empty-icon"><InfoFilled /></el-icon>
      <p class="empty-text">请先上传训练数据集文件</p>
    </div>
    
    <div v-else>
      <!-- 模型选择 -->
      <div style="display: flex; align-items: center; margin-top: 20px;">
        <el-select 
          v-model="selectedModelLocal" 
          placeholder="请选择模型" 
          style="width: 200px;"
          @change="onModelChange"
        >
          <el-option label="LGBM-GBDT" value="GBDT"></el-option>
          <el-option label="LGBM-DART" value="DART"></el-option>
          <el-option label="LGBM-GOSS" value="GOSS"></el-option>
          <el-option label="自定义模型" value="CUSTOM"></el-option>
        </el-select>
        
        <el-button 
          type="warning" 
          size="small" 
          style="margin-left: 10px;"
          :disabled="processing"
          @click="onResetClick"
        >
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
      </div>
      
      <!-- 风电场装机容量输入框及提示文字 -->
      <div v-if="selectedModelLocal" style="margin-top: 20px;">
        <label for="wfCapacity" style="margin-right: 10px;color: #909399">整场装机容量 (MW)：</label>
        <el-input
          id="wfCapacity"
          v-model="wfCapacityLocal"
          placeholder="请输入风电场总装机容量（MW）"
          style="width: 400px;"
          @change="onWindFarmCapacityChange"
          :input-style="{ color: '#909399' }"
        ></el-input>
      </div>

      <!-- 训练集占比输入框及提示文字 -->
      <div v-if="selectedModelLocal" style="margin-top: 20px;">
        <label for="trainRatio" style="margin-right: 10px;color: #909399">训练集占比：</label>
        <el-slider
          id="trainRatio"
          v-model="trainRatioLocal"
          :min="0.1"
          :max="0.95"
          :step="0.05"
          :format-tooltip="formatTooltip"
          style="width: 400px;"
          @change="onTrainRatioChange"
        ></el-slider>
      </div>

      <!-- 自定义模型超参数设置 -->
      <div v-if="selectedModelLocal === 'CUSTOM'" style="margin-top: 20px;">
        <h3 style="margin-bottom: 15px; color: #606266;">自定义模型超参数</h3>
        
        <!-- 提升类型选择 -->
        <div class="param-item">
          <label for="boosting_type" style="color: #909399">提升类型：</label>
          <el-select 
            id="boosting_type"
            v-model="customParams.boosting_type" 
            placeholder="选择提升类型" 
            style="width: 200px;"
          >
            <el-option label="GBDT" value="gbdt"></el-option>
            <el-option label="DART" value="dart"></el-option>
            <el-option label="GOSS" value="goss"></el-option>
          </el-select>
        </div>
        
        <!-- 学习率 -->
        <div class="param-item">
          <label for="learning_rate" style="color: #909399">学习率：</label>
          <el-input-number
            id="learning_rate"
            v-model="customParams.learning_rate"
            :min="0.001"
            :max="1"
            :step="0.001"
            :precision="3"
            style="width: 200px;"
          ></el-input-number>
        </div>
        
        <!-- 叶子节点数 -->
        <div class="param-item">
          <label for="num_leaves" style="color: #909399">叶子节点数：</label>
          <el-input-number
            id="num_leaves"
            v-model="customParams.num_leaves"
            :min="2"
            :max="256"
            :step="1"
            style="width: 200px;"
          ></el-input-number>
        </div>
        
        <!-- 特征抽样比例 -->
        <div class="param-item">
          <label for="feature_fraction" style="color: #909399">特征抽样比例：</label>
          <el-slider
            id="feature_fraction"
            v-model="customParams.feature_fraction"
            :min="0.1"
            :max="1"
            :step="0.1"
            :format-tooltip="(val) => (val * 100).toFixed(0) + '%'"
            style="width: 200px;"
          ></el-slider>
        </div>
        
        <!-- DART特有参数 -->
        <div v-if="customParams.boosting_type === 'dart'" class="param-item">
          <label for="drop_rate" style="color: #909399">丢弃率：</label>
          <el-slider
            id="drop_rate"
            v-model="customParams.drop_rate"
            :min="0.1"
            :max="0.9"
            :step="0.1"
            :format-tooltip="(val) => (val * 100).toFixed(0) + '%'"
            style="width: 200px;"
          ></el-slider>
        </div>
        
        <!-- GOSS特有参数 -->
        <div v-if="customParams.boosting_type === 'goss'" class="param-item">
          <label for="top_rate" style="color: #909399">顶部样本比例：</label>
          <el-slider
            id="top_rate"
            v-model="customParams.top_rate"
            :min="0.1"
            :max="0.9"
            :step="0.1"
            :format-tooltip="(val) => (val * 100).toFixed(0) + '%'"
            style="width: 200px;"
          ></el-slider>
        </div>
        
        <div v-if="customParams.boosting_type === 'goss'" class="param-item">
          <label for="other_rate" style="color: #909399">其他样本比例：</label>
          <el-slider
            id="other_rate"
            v-model="customParams.other_rate"
            :min="0.1"
            :max="0.9"
            :step="0.1"
            :format-tooltip="(val) => (val * 100).toFixed(0) + '%'"
            style="width: 200px;"
          ></el-slider>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { InfoFilled, Refresh } from '@element-plus/icons-vue'

export default {
  name: 'ModelSelector',
  components: {
    InfoFilled,
    Refresh
  },
  props: {
    fileId: {
      type: [String, Number],
      required: true
    },
    processing: {
      type: Boolean,
      default: false
    },
    selectedModel: {
      type: String,
      default: null
    },
    predictionstate: {
      type: Boolean,
    },
    wfCapacity: {
      type: Number,
      default: 453.5,
    },
    trainRatio: {
      type: Number,
      default: 0.9,
    }
  },
  data() {
    return {
      selectedModelLocal: this.selectedModel,
      wfCapacityLocal: this.wfCapacity,
      trainRatioLocal: this.trainRatio,
      customParams: {
        boosting_type: 'gbdt',
        learning_rate: 0.05,
        num_leaves: 31,
        feature_fraction: 0.9,
        drop_rate: 0.1,
        top_rate: 0.2,
        other_rate: 0.1
      }
    };
  },
  methods: {
    onModelChange(value) {
      this.$emit('model-selected', value);
      if (value === 'CUSTOM') {
        this.$emit('custom-params-change', this.customParams);
      }
    },
    onWindFarmCapacityChange(value) {
      if (value <= 0) {
        this.$message.error('请输入正确的数值！');
      }
      this.$emit('model_wf_capacity', value);
    },
    onTrainRatioChange(value) {
      this.$emit('train-ratio-change', value);
    },
    formatTooltip(val) {
      return (val * 100).toFixed(0) + '%';
    },
    onResetClick() {
      // 发送重置事件，让父组件处理确认对话框
      this.$emit('reset');
    }
  },
  watch: {
    selectedModel(val) {
      this.selectedModelLocal = val;
    },
    wfCapacity(val) {
      this.wfCapacityLocal = val;
    },
    trainRatio(val) {
      this.trainRatioLocal = val;
    },
    'customParams': {
      handler(newVal) {
        if (this.selectedModelLocal === 'CUSTOM') {
          this.$emit('custom-params-change', newVal);
        }
      },
      deep: true
    }
  }
};
</script>

<style scoped>
.model-selector {
  width: 100%;
}

.empty-model-selector {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px dashed #dcdfe6;
}

.empty-icon {
  font-size: 24px;
  color: #909399;
  margin-bottom: 12px;
}

.empty-text {
  color: #909399;
  font-size: 14px;
  text-align: center;
  margin: 0;
}

.param-item {
  margin-bottom: 15px;
  display: flex;
  align-items: center;
}

.param-item label {
  width: 120px;
  text-align: right;
  margin-right: 10px;
}

/* 新增placeholder样式 */
:deep(.el-input__inner::placeholder) {
  color: #909399;
  opacity: 1;
}
</style>
