<template>
  <div class="system-settings page-shell">
    <div class="page-header">
      <div>
        <h2>系统基础配置</h2>
        <p>当前仓库中未发现专门的配置保存接口，本页先提供本地持久化与回显能力，避免配置完全停留在一次性输入态。</p>
      </div>
      <el-tag type="warning" effect="dark">存储方式：localStorage 过渡方案</el-tag>
    </div>

    <el-alert
      :closable="false"
      type="info"
      show-icon
      class="top-alert"
      title="代码中未发现系统基础配置后端接口，本页保存仅写入浏览器本地存储。"
    />

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card class="card-shell">
          <template #header>节假日与免考说明配置</template>
          <el-date-picker v-model="holidayDate" type="date" value-format="YYYY-MM-DD" />
          <el-input
            v-model.trim="holidayNote"
            placeholder="输入节假日说明或免考备注"
            style="margin-top: 8px"
          />
          <div class="actions">
            <el-button type="primary" @click="addHoliday">新增</el-button>
          </div>
          <el-table :data="holidays" size="small" style="margin-top: 10px" empty-text="暂无节假日配置">
            <el-table-column prop="date" label="日期" />
            <el-table-column prop="note" label="说明" />
            <el-table-column label="操作" width="90">
              <template #default="{ $index }">
                <el-button link type="danger" @click="removeHoliday($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="card-shell">
          <template #header>字典配置</template>
          <el-form label-width="100px">
            <el-form-item label="机型列表">
              <el-input v-model="dict.turbineModels" placeholder="使用逗号分隔机型" />
            </el-form-item>
            <el-form-item label="厂商列表">
              <el-input v-model="dict.vendors" placeholder="使用逗号分隔厂商" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="card-shell retention-card">
      <template #header>保留策略</template>
      <el-form inline>
        <el-form-item label="预测数据保留(月)">
          <el-input-number v-model="params.retentionMonths" :min="1" :max="36" />
        </el-form-item>
        <el-form-item label="日志保留(天)">
          <el-input-number v-model="params.logRetentionDays" :min="7" :max="365" />
        </el-form-item>
        <el-form-item label="磁盘告警阈值(%)">
          <el-input-number v-model="params.diskAlertPercent" :min="60" :max="95" />
        </el-form-item>
      </el-form>
      <div class="actions">
        <el-button type="primary" @click="saveSettings">保存配置</el-button>
        <el-button @click="resetSettings">恢复默认</el-button>
      </div>
      <div class="footer-tip">最近保存：{{ savedAt || '尚未保存' }}</div>
    </el-card>
  </div>
</template>

<script>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDefaultSystemSettings, readSystemSettings, saveSystemSettings } from '../utils/systemSettingsStore'

function buildSavedAt() {
  return new Date().toLocaleString('zh-CN', { hour12: false })
}

export default {
  name: 'SystemSettings',
  setup() {
    const holidayDate = ref('')
    const holidayNote = ref('')
    const savedAt = ref('')

    const current = readSystemSettings()
    const holidays = ref(current.holidays)
    const dict = reactive({ ...current.dict })
    const params = reactive({ ...current.params })

    const persist = () => {
      saveSystemSettings({
        holidays: holidays.value,
        dict,
        params
      })
      savedAt.value = buildSavedAt()
    }

    const addHoliday = () => {
      if (!holidayDate.value) {
        ElMessage.warning('请选择节假日日期')
        return
      }

      holidays.value.unshift({
        date: holidayDate.value,
        note: holidayNote.value || '节假日'
      })
      holidayDate.value = ''
      holidayNote.value = ''
      persist()
      ElMessage.success('节假日配置已保存到本地')
    }

    const removeHoliday = (index) => {
      holidays.value.splice(index, 1)
      persist()
      ElMessage.success('节假日配置已删除')
    }

    const saveSettings = () => {
      persist()
      ElMessage.success('系统基础配置已保存到本地')
    }

    const resetSettings = async () => {
      await ElMessageBox.confirm('将恢复默认配置并覆盖本地保存内容，是否继续？', '恢复默认', {
        type: 'warning'
      })

      const next = getDefaultSystemSettings()
      holidays.value = next.holidays
      dict.turbineModels = next.dict.turbineModels
      dict.vendors = next.dict.vendors
      params.retentionMonths = next.params.retentionMonths
      params.logRetentionDays = next.params.logRetentionDays
      params.diskAlertPercent = next.params.diskAlertPercent
      persist()
      ElMessage.success('已恢复默认配置')
    }

    return {
      holidayDate,
      holidayNote,
      holidays,
      dict,
      params,
      savedAt,
      addHoliday,
      removeHoliday,
      saveSettings,
      resetSettings
    }
  }
}
</script>

<style scoped>
.system-settings {
  min-height: 100%;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.page-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.top-alert {
  margin-bottom: 12px;
}

.card-shell {
  background: rgba(6, 21, 34, 0.86);
  border: 1px solid rgba(130, 178, 212, 0.2);
}

.retention-card {
  margin-top: 12px;
}

.actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.footer-tip {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
