<template>
  <div class="workspace page-shell">
    <div class="header">
      <h2>人工修正工作台</h2>
      <p>支持大图表修正、区间平移、系数调整与限电上限压制</p>
    </div>

    <div class="layout">
      <el-card class="side">
        <el-form label-width="88px">
          <el-form-item label="场站">
            <el-select v-model="station">
              <el-option label="大青山风电场" value="大青山风电场" />
              <el-option label="乌兰风电场" value="乌兰风电场" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="修正方式">
            <el-select v-model="tool">
              <el-option label="整体上浮(%)" value="scaleUp" />
              <el-option label="整体平移(MW)" value="shift" />
              <el-option label="上限压制(MW)" value="cap" />
            </el-select>
          </el-form-item>
          <el-form-item label="参数">
            <el-input-number v-model="toolValue" :min="-1000" :max="1000" />
          </el-form-item>
        </el-form>
        <div class="actions">
          <el-button type="primary" @click="applyTool">应用到选中时段</el-button>
          <el-button @click="resetSeries">重置</el-button>
          <el-button type="success" @click="saveVersion">保存并触发重上报</el-button>
        </div>
      </el-card>

      <el-card class="chart-card">
        <div class="chart-title">预测曲线编辑区（00:00 ~ 23:00）</div>
        <svg viewBox="0 0 960 360" class="chart">
          <polyline
            :points="linePoints"
            fill="none"
            stroke="#18d8ff"
            stroke-width="3"
          />
          <line
            v-if="capValue !== null"
            x1="0"
            x2="960"
            :y1="toY(capValue)"
            :y2="toY(capValue)"
            stroke="#fbbf24"
            stroke-width="2"
            stroke-dasharray="8 5"
          />
        </svg>
        <div class="range-tip">当前示例为工作区骨架版，后续可接入可拖拽点编辑和缩放。</div>
      </el-card>
    </div>
  </div>
</template>

<script>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

const buildMockSeries = () => Array.from({ length: 24 }, (_, i) => {
  const base = 35 + Math.sin((i / 24) * Math.PI * 2) * 18
  return Number(Math.max(0, base).toFixed(2))
})

export default {
  name: 'ManualInterventionWorkspace',
  setup() {
    const station = ref('大青山风电场')
    const targetDate = ref(new Date().toISOString().slice(0, 10))
    const tool = ref('scaleUp')
    const toolValue = ref(10)
    const capValue = ref(null)
    const series = ref(buildMockSeries())

    const maxY = computed(() => Math.max(...series.value, capValue.value || 0, 1))
    const toY = (v) => 330 - (v / maxY.value) * 300
    const toX = (index) => (index / 23) * 960

    const linePoints = computed(() => {
      return series.value.map((v, i) => `${toX(i)},${toY(v)}`).join(' ')
    })

    const applyTool = () => {
      if (tool.value === 'scaleUp') {
        const factor = 1 + Number(toolValue.value) / 100
        series.value = series.value.map(v => Number(Math.max(0, v * factor).toFixed(2)))
      } else if (tool.value === 'shift') {
        series.value = series.value.map(v => Number(Math.max(0, v + Number(toolValue.value)).toFixed(2)))
      } else if (tool.value === 'cap') {
        capValue.value = Number(toolValue.value)
        series.value = series.value.map(v => Math.min(v, capValue.value))
      }
    }

    const resetSeries = () => {
      capValue.value = null
      series.value = buildMockSeries()
    }

    const saveVersion = () => {
      ElMessage.success(`已保存 ${station.value} ${targetDate.value} 修正版本，并触发重新上报`)
    }

    return {
      station,
      targetDate,
      tool,
      toolValue,
      capValue,
      linePoints,
      toY,
      applyTool,
      resetSeries,
      saveVersion
    }
  }
}
</script>

<style scoped>
.workspace { min-height: 100%; padding: 20px; }
.header h2 { margin: 0; color: var(--text-primary); }
.header p { margin: 8px 0 14px; color: var(--text-secondary); }
.layout { display: grid; grid-template-columns: 320px 1fr; gap: 12px; }
.side,
.chart-card { background: rgba(6, 21, 34, 0.86); border: 1px solid rgba(130, 178, 212, 0.2); }
.actions { display: grid; gap: 8px; margin-top: 8px; }
.chart-title { color: var(--text-primary); margin-bottom: 10px; }
.chart { width: 100%; height: 420px; border-radius: 10px; background: rgba(8, 32, 48, 0.55); border: 1px solid rgba(130, 178, 212, 0.2); }
.range-tip { color: var(--text-secondary); font-size: 12px; margin-top: 8px; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
</style>
