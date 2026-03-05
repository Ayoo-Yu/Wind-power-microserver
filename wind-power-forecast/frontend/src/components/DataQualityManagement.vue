<template>
  <div class="data-quality page-shell">
    <div class="page-header">
      <h2>数据质量与限电标记</h2>
      <p>监控 SCADA/测风塔完整率，标记“限电/大修/结冰”等时段并用于免考剔除</p>
    </div>

    <el-card class="card-shell">
      <div class="quality-grid">
        <div v-for="item in completeness" :key="item.station" class="quality-card">
          <div class="title">{{ item.station }}</div>
          <div class="meta">SCADA {{ item.scada }}% · 测风塔 {{ item.mast }}%</div>
          <div class="bars">
            <el-progress :percentage="item.scada" :stroke-width="8" :status="item.scada < 90 ? 'exception' : 'success'" />
            <el-progress :percentage="item.mast" :stroke-width="8" :status="item.mast < 90 ? 'exception' : 'success'" />
          </div>
        </div>
      </div>

      <div class="table-header">
        <h3>异常时段标记（免考剔除）</h3>
        <el-button type="primary" @click="openDialog">新增标记</el-button>
      </div>

      <el-table :data="markers" border stripe>
        <el-table-column prop="station" label="场站" min-width="140" />
        <el-table-column prop="start" label="开始时间" min-width="160" />
        <el-table-column prop="end" label="结束时间" min-width="160" />
        <el-table-column prop="type" label="标记类型" min-width="130" />
        <el-table-column prop="reason" label="说明" min-width="320" />
        <el-table-column prop="excludeFromScore" label="准确率免考" width="120">
          <template #default="{ row }">
            <el-tag :type="row.excludeFromScore ? 'success' : 'info'" effect="plain">
              {{ row.excludeFromScore ? '剔除' : '保留' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="新增异常标记" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="场站">
          <el-input v-model="form.station" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="form.range"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="标记类型">
          <el-select v-model="form.type">
            <el-option label="限电时段" value="限电时段" />
            <el-option label="风机大修时段" value="风机大修时段" />
            <el-option label="测风塔结冰时段" value="测风塔结冰时段" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.reason" type="textarea" />
        </el-form-item>
        <el-form-item label="准确率免考">
          <el-switch v-model="form.excludeFromScore" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMarker">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { reactive, ref } from 'vue'

export default {
  name: 'DataQualityManagement',
  setup() {
    const completeness = ref([
      { station: '大青山风电场', scada: 98, mast: 96 },
      { station: '乌兰风电场', scada: 91, mast: 87 },
      { station: '海西风电场', scada: 88, mast: 85 }
    ])
    const markers = ref([
      {
        station: '大青山风电场',
        start: '2026-03-05 08:00:00',
        end: '2026-03-05 10:00:00',
        type: '限电时段',
        reason: '电网临时限发指令',
        excludeFromScore: true
      }
    ])

    const showDialog = ref(false)
    const form = reactive({
      station: '',
      range: [],
      type: '限电时段',
      reason: '',
      excludeFromScore: true
    })

    const openDialog = () => {
      showDialog.value = true
    }

    const submitMarker = () => {
      if (!form.station || !Array.isArray(form.range) || form.range.length !== 2) return
      markers.value.unshift({
        station: form.station,
        start: form.range[0],
        end: form.range[1],
        type: form.type,
        reason: form.reason,
        excludeFromScore: form.excludeFromScore
      })
      showDialog.value = false
    }

    return {
      completeness,
      markers,
      showDialog,
      form,
      openDialog,
      submitMarker
    }
  }
}
</script>

<style scoped>
.data-quality { min-height: 100%; padding: 20px; }
.page-header h2 { margin: 0; color: var(--text-primary); }
.page-header p { margin: 8px 0 14px; color: var(--text-secondary); }
.card-shell { background: rgba(6, 21, 34, 0.86); border: 1px solid rgba(130, 178, 212, 0.2); }
.quality-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
.quality-card { border: 1px solid rgba(130, 178, 212, 0.2); border-radius: 10px; padding: 10px; background: rgba(13, 36, 55, 0.5); }
.quality-card .title { color: var(--text-primary); font-weight: 600; }
.quality-card .meta { color: var(--text-secondary); font-size: 12px; margin: 4px 0 8px; }
.bars { display: flex; flex-direction: column; gap: 6px; }
.table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.table-header h3 { margin: 0; color: var(--text-primary); font-size: 16px; }
@media (max-width: 1100px) {
  .quality-grid { grid-template-columns: 1fr; }
}
</style>
