<template>
  <div class="step-hint-box">
    <div class="step-item">
      <span class="step-number">1</span>
      <span class="step-label">预测数据集：</span>
      <span class="step-status" :class="{ 'status-null': !csvfileid }">
        {{ csvfileid ? csvfileid : 'null' }}
      </span>
    </div>
    <div class="step-item">
      <span class="step-number">2</span>
      <span class="step-label">预测模型：</span>
      <span class="step-status" :class="{ 'status-null': !modelfileid }">
        {{ modelfileid ? modelfileid : 'null' }}
      </span>
    </div>
    <div class="step-item">
      <span class="step-number">3</span>
      <span class="step-label">归一化模型：</span>
      <span class="step-status" :class="{ 'status-null': !scalerfileid }">
        {{ scalerfileid ? scalerfileid : 'null' }}
      </span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'StepHintBox',
  props: {
    csvfileid: {
      type: [String, Number],
      default: null
    },
    modelfileid: {
      type: [String, Number],
      default: null
    },
    scalerfileid: {
      type: [String, Number],
      default: null
    }
  }
}
</script>

<style scoped>
.step-hint-box {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 12px;
  background: #0077ED;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.step-label {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 500;
}

.step-status {
  color: #0077ED;
  font-size: 14px;
  font-family: monospace;
}

.status-null {
  color: #ff3b30;
  font-style: italic;
}
</style>