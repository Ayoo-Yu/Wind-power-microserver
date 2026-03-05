<template>
  <div class="system-settings page-shell">
    <div class="page-header">
      <h2>系统基础配置</h2>
      <p>统一维护节假日、数据字典与全局参数，作为系统底座能力</p>
    </div>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card class="card-shell">
          <template #header>节假日/特殊日历配置</template>
          <el-date-picker v-model="holidayDate" type="date" value-format="YYYY-MM-DD" />
          <el-input v-model.trim="holidayNote" placeholder="例如：国庆节假期" style="margin-top: 8px" />
          <div class="actions">
            <el-button type="primary" @click="addHoliday">添加</el-button>
          </div>
          <el-table :data="holidays" size="small" style="margin-top: 10px">
            <el-table-column prop="date" label="日期" />
            <el-table-column prop="note" label="说明" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="card-shell">
          <template #header>数据字典</template>
          <el-form label-width="100px">
            <el-form-item label="机组型号">
              <el-input v-model="dict.turbineModels" placeholder="逗号分隔" />
            </el-form-item>
            <el-form-item label="厂商列表">
              <el-input v-model="dict.vendors" placeholder="逗号分隔" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="card-shell" style="margin-top: 12px">
      <template #header>全局参数</template>
      <el-form inline>
        <el-form-item label="历史数据保留(月)">
          <el-input-number v-model="params.retentionMonths" :min="1" :max="36" />
        </el-form-item>
        <el-form-item label="日志保留(天)">
          <el-input-number v-model="params.logRetentionDays" :min="7" :max="365" />
        </el-form-item>
        <el-form-item label="磁盘告警阈值(%)">
          <el-input-number v-model="params.diskAlertPercent" :min="60" :max="95" />
        </el-form-item>
      </el-form>
      <el-button type="primary">保存配置</el-button>
    </el-card>
  </div>
</template>

<script>
import { reactive, ref } from 'vue'

export default {
  name: 'SystemSettings',
  setup() {
    const holidayDate = ref('')
    const holidayNote = ref('')
    const holidays = ref([{ date: '2026-10-01', note: '国庆节' }])
    const dict = reactive({
      turbineModels: 'GW121, GW155, EN171',
      vendors: '金风, 远景, 明阳'
    })
    const params = reactive({
      retentionMonths: 12,
      logRetentionDays: 180,
      diskAlertPercent: 85
    })

    const addHoliday = () => {
      if (!holidayDate.value) return
      holidays.value.unshift({ date: holidayDate.value, note: holidayNote.value || '特殊日历' })
      holidayDate.value = ''
      holidayNote.value = ''
    }

    return {
      holidayDate,
      holidayNote,
      holidays,
      dict,
      params,
      addHoliday
    }
  }
}
</script>

<style scoped>
.system-settings { min-height: 100%; padding: 20px; }
.page-header h2 { margin: 0; color: var(--text-primary); }
.page-header p { margin: 8px 0 14px; color: var(--text-secondary); }
.card-shell { background: rgba(6, 21, 34, 0.86); border: 1px solid rgba(130, 178, 212, 0.2); }
.actions { margin-top: 8px; }
</style>
