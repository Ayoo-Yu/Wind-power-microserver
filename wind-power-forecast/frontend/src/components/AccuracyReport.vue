<template>
  <div class="accuracy-report page-shell">
    <div class="page-header">
      <h2>准确率/合格率考核报表</h2>
      <p>支持月报导出，且自动剔除被标记为“免考”的异常时段</p>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-date-picker v-model="month" type="month" value-format="YYYY-MM" />
        <el-select v-model="station" placeholder="选择场站">
          <el-option label="全部场站" value="all" />
          <el-option label="大青山风电场" value="大青山风电场" />
          <el-option label="乌兰风电场" value="乌兰风电场" />
        </el-select>
        <el-button type="primary">查询</el-button>
        <el-button>导出月报</el-button>
      </div>

      <el-table :data="rows" border stripe>
        <el-table-column prop="station" label="场站" min-width="140" />
        <el-table-column prop="month" label="月份" width="120" />
        <el-table-column prop="accuracy" label="平均准确率(%)" width="140" />
        <el-table-column prop="qualified" label="合格率(%)" width="120" />
        <el-table-column prop="excludedHours" label="免考时长(小时)" width="140" />
        <el-table-column prop="note" label="备注" min-width="260" />
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { ref } from 'vue'

export default {
  name: 'AccuracyReport',
  setup() {
    const month = ref(new Date().toISOString().slice(0, 7))
    const station = ref('all')
    const rows = ref([
      { station: '大青山风电场', month: '2026-03', accuracy: 94.62, qualified: 92.10, excludedHours: 12, note: '已剔除限电时段' },
      { station: '乌兰风电场', month: '2026-03', accuracy: 92.33, qualified: 90.08, excludedHours: 6, note: '已剔除测风塔结冰时段' }
    ])
    return { month, station, rows }
  }
}
</script>

<style scoped>
.accuracy-report { min-height: 100%; padding: 20px; }
.page-header h2 { margin: 0; color: var(--text-primary); }
.page-header p { margin: 8px 0 14px; color: var(--text-secondary); }
.card-shell { background: rgba(6, 21, 34, 0.86); border: 1px solid rgba(130, 178, 212, 0.2); }
.toolbar { display: flex; gap: 8px; margin-bottom: 10px; align-items: center; flex-wrap: wrap; }
</style>
