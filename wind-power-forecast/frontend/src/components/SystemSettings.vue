<template>
  <div class="system-settings page-shell">
    <div class="page-header">
      <div>
        <h2>系统基础配置</h2>
        <p>系统参数、字典与节假日配置已切换到后端存储，支持统一保存与恢复默认。</p>
      </div>
      <el-tag type="success" effect="dark">后端配置中心已接入</el-tag>
    </div>

    <el-alert
      :closable="false"
      type="info"
      show-icon
      class="top-alert"
      title="当前页面保存的是系统共享配置，刷新页面或切换账号后会回显同一份后端配置。"
    />

    <el-alert
      v-if="errorMessage"
      :closable="false"
      type="warning"
      show-icon
      class="top-alert"
      :title="errorMessage"
    />

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card class="card-shell">
          <template #header>节假日与免考核日期</template>
          <el-date-picker v-model="holidayDate" type="date" value-format="YYYY-MM-DD" />
          <el-input
            v-model.trim="holidayNote"
            placeholder="填写节假日备注，例如：国庆节"
            style="margin-top: 8px"
          />
          <div class="actions">
            <el-button type="primary" @click="addHoliday">新增</el-button>
          </div>
          <el-table
            v-loading="loading"
            :data="holidays"
            size="small"
            style="margin-top: 10px"
            empty-text="暂无节假日配置"
          >
            <el-table-column prop="date" label="日期" />
            <el-table-column prop="note" label="备注" />
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
              <el-input v-model="dict.turbineModels" placeholder="多个机型使用英文逗号分隔" />
            </el-form-item>
            <el-form-item label="厂家列表">
              <el-input v-model="dict.vendors" placeholder="多个厂家使用英文逗号分隔" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="card-shell retention-card">
      <template #header>保留策略</template>
      <el-form inline>
        <el-form-item label="数据保留(月)">
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
        <el-button type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
        <el-button :loading="resetting" @click="resetSettings">恢复默认</el-button>
      </div>
      <div class="footer-tip">
        最近保存时间：{{ savedAt || '尚未保存' }}
        <span v-if="updatedBy"> / 最近操作人：{{ updatedBy }}</span>
      </div>
    </el-card>
  </div>
</template>

<script>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSystemSettings, saveSystemSettings as saveSystemSettingsApi, resetSystemSettings } from '../api/systemApi'

function buildSavedAt(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function buildDefaultSettings() {
  return {
    holidays: [],
    dict: {
      turbineModels: '',
      vendors: ''
    },
    params: {
      retentionMonths: 12,
      logRetentionDays: 180,
      diskAlertPercent: 85
    }
  }
}

function getStoredUserName() {
  try {
    const raw = localStorage.getItem('user')
    if (!raw) return '当前用户'
    const parsed = JSON.parse(raw)
    return parsed?.real_name || parsed?.username || parsed?.name || '当前用户'
  } catch {
    return '当前用户'
  }
}

export default {
  name: 'SystemSettings',
  setup() {
    const holidayDate = ref('')
    const holidayNote = ref('')
    const holidays = ref([])
    const savedAt = ref('')
    const updatedBy = ref('')
    const loading = ref(false)
    const saving = ref(false)
    const resetting = ref(false)
    const errorMessage = ref('')

    const dict = reactive({
      turbineModels: '',
      vendors: ''
    })

    const params = reactive({
      retentionMonths: 12,
      logRetentionDays: 180,
      diskAlertPercent: 85
    })

    const applySettings = (payload = {}) => {
      const next = {
        ...buildDefaultSettings(),
        ...(payload || {})
      }
      holidays.value = Array.isArray(next.holidays) ? next.holidays : []
      dict.turbineModels = next.dict?.turbineModels || ''
      dict.vendors = next.dict?.vendors || ''
      params.retentionMonths = Number(next.params?.retentionMonths || 12)
      params.logRetentionDays = Number(next.params?.logRetentionDays || 180)
      params.diskAlertPercent = Number(next.params?.diskAlertPercent || 85)
    }

    const buildPayload = () => ({
      holidays: holidays.value,
      dict: {
        turbineModels: dict.turbineModels,
        vendors: dict.vendors
      },
      params: {
        retentionMonths: params.retentionMonths,
        logRetentionDays: params.logRetentionDays,
        diskAlertPercent: params.diskAlertPercent
      }
    })

    const loadSettings = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        const response = await getSystemSettings()
        applySettings(response.data?.data)
        savedAt.value = buildSavedAt(response.data?.updated_at)
        updatedBy.value = response.data?.updated_by || ''
      } catch {
        applySettings()
      } finally {
        loading.value = false
      }
    }

    const addHoliday = () => {
      if (!holidayDate.value) {
        ElMessage.warning('请先选择节假日日期')
        return
      }

      holidays.value.unshift({
        date: holidayDate.value,
        note: holidayNote.value || '节假日'
      })
      holidayDate.value = ''
      holidayNote.value = ''
      ElMessage.success('节假日已加入待保存列表')
    }

    const removeHoliday = (index) => {
      holidays.value.splice(index, 1)
      ElMessage.success('节假日已移出待保存列表')
    }

    const saveSettings = async () => {
      saving.value = true
      try {
        const response = await saveSystemSettingsApi({
          data: buildPayload(),
          updated_by: getStoredUserName()
        })
        applySettings(response.data?.data)
        savedAt.value = buildSavedAt(response.data?.updated_at)
        updatedBy.value = response.data?.updated_by || ''
        ElMessage.success(response.data?.message || '系统基础配置保存成功')
      } catch (error) {
        console.warn('保存系统基础配置失败:', error)
      } finally {
        saving.value = false
      }
    }

    const resetSettings = async () => {
      await ElMessageBox.confirm(
        '恢复默认会覆盖当前后端保存的节假日、字典和保留策略，确认继续吗？',
        '恢复默认',
        { type: 'warning' }
      )

      resetting.value = true
      try {
        const response = await resetSystemSettings({
          updated_by: getStoredUserName()
        })
        applySettings(response.data?.data)
        savedAt.value = buildSavedAt(response.data?.updated_at)
        updatedBy.value = response.data?.updated_by || ''
        ElMessage.success(response.data?.message || '系统基础配置已恢复默认')
      } catch (error) {
        if (error !== 'cancel') {
          console.warn('恢复系统基础配置失败:', error)
        }
      } finally {
        resetting.value = false
      }
    }

    onMounted(async () => {
      await loadSettings()
    })

    return {
      holidayDate,
      holidayNote,
      holidays,
      dict,
      params,
      savedAt,
      updatedBy,
      loading,
      saving,
      resetting,
      errorMessage,
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
