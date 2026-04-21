<template>
  <div class="data-quality page-shell">
    <div class="page-header">
      <div>
        <h2>数据质量与限电标记</h2>
        <p>基于真实统计接口展示各场站完整率与及时率，并将人工标记持久化到后端。</p>
      </div>
      <el-tag type="success" effect="dark">质量标记已切换为后端存储</el-tag>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-date-picker
          v-model="month"
          type="month"
          value-format="YYYY-MM"
          placeholder="选择统计月份"
          :clearable="false"
        />
        <el-select v-model="selectedFarm" filterable placeholder="选择场站">
          <el-option label="全部场站" value="all" />
          <el-option
            v-for="item in farms"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button type="primary" :loading="loadingStats || loadingMarkers" @click="reloadAll">
          刷新数据
        </el-button>
      </div>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="warning"
        :closable="false"
        show-icon
        class="result-alert"
      />

      <div class="quality-grid">
        <div v-for="item in completenessCards" :key="item.station" class="quality-card">
          <div class="title">{{ item.station }}</div>
          <div class="meta">
            平均完整率 {{ formatPercent(item.completeness) }} / 平均及时率 {{ formatPercent(item.timeliness) }}
          </div>
          <div class="bars">
            <el-progress
              :percentage="item.completeness"
              :stroke-width="8"
              :status="item.completeness < 90 ? 'exception' : 'success'"
            />
            <el-progress
              :percentage="item.timeliness"
              :stroke-width="8"
              :status="item.timeliness < 90 ? 'exception' : 'success'"
            />
          </div>
          <div class="meta-tip">统计来源：report/statistics.daily_stats</div>
        </div>
      </div>

      <div class="table-header">
        <h3>限电 / 异常标记</h3>
        <el-button type="primary" @click="openDialog">新增标记</el-button>
      </div>

      <el-table
        v-loading="loadingMarkers"
        :data="markers"
        border
        stripe
        empty-text="暂无质量标记"
      >
        <el-table-column prop="farm_name" label="场站" min-width="140" />
        <el-table-column prop="start_time_display" label="开始时间" min-width="170" />
        <el-table-column prop="end_time_display" label="结束时间" min-width="170" />
        <el-table-column prop="marker_type" label="标记类型" min-width="140" />
        <el-table-column prop="reason" label="原因说明" min-width="260" show-overflow-tooltip />
        <el-table-column prop="exclude_from_score" label="免考核" width="100">
          <template #default="{ row }">
            <el-tag :type="row.exclude_from_score ? 'success' : 'info'" effect="plain">
              {{ row.exclude_from_score ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="创建人" min-width="120" />
        <el-table-column prop="created_at_display" label="创建时间" min-width="170" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确认删除这条标记吗？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="新增限电 / 异常标记" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="场站">
          <el-select v-model="form.farmCode" filterable placeholder="请选择场站">
            <el-option
              v-for="item in farms"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
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
          <el-select v-model="form.markerType">
            <el-option label="数据缺失" value="数据缺失" />
            <el-option label="限电停机" value="限电停机" />
            <el-option label="设备维护" value="设备维护" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因说明">
          <el-input v-model="form.reason" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="免考核">
          <el-switch v-model="form.excludeFromScore" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMarker">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createQualityMarker,
  deleteQualityMarker,
  getQualityMarkers,
  getReportFarms,
  getReportStatistics
} from '../api/reportApi'

function formatMonthDefault() {
  return new Date().toISOString().slice(0, 7)
}

function normalizeFarmItem(item) {
  const farmCode = item?.farm_code || item?.code || item?.value || item?.id
  if (!farmCode) return null
  return {
    value: String(farmCode),
    label: item?.farm_name || item?.name || String(farmCode)
  }
}

function formatDateTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function getStoredUserName() {
  try {
    const raw = localStorage.getItem('user')
    if (!raw) return '当前用户'
    const parsed = JSON.parse(raw)
    return parsed?.real_name || parsed?.username || parsed?.name || '当前用户'
  } catch (error) {
    return '当前用户'
  }
}

export default {
  name: 'DataQualityManagement',
  setup() {
    const month = ref(formatMonthDefault())
    const selectedFarm = ref('all')
    const farms = ref([])
    const statistics = ref([])
    const markers = ref([])
    const loadingStats = ref(false)
    const loadingMarkers = ref(false)
    const submitting = ref(false)
    const errorMessage = ref('')
    const showDialog = ref(false)
    const form = reactive({
      farmCode: '',
      range: [],
      markerType: '数据缺失',
      reason: '',
      excludeFromScore: true
    })

    const formatPercent = (value) => {
      const numeric = Number(value)
      if (Number.isNaN(numeric)) return '--'
      return `${numeric.toFixed(2)}%`
    }

    const completenessCards = computed(() => {
      const bucket = new Map()
      statistics.value.forEach((item) => {
        const key = item?.farm_code || item?.farm_name || 'UNKNOWN'
        if (!bucket.has(key)) {
          bucket.set(key, {
            station: item?.farm_name || item?.farm_code || '未知场站',
            completenessSum: 0,
            timelinessSum: 0,
            count: 0
          })
        }
        const current = bucket.get(key)
        current.completenessSum += Number(item?.overall_completeness_rate || 0)
        current.timelinessSum += Number(item?.overall_timeliness_rate || 0)
        current.count += 1
      })

      return Array.from(bucket.values()).map((item) => ({
        station: item.station,
        completeness: item.count > 0 ? Number((item.completenessSum / item.count).toFixed(2)) : 0,
        timeliness: item.count > 0 ? Number((item.timelinessSum / item.count).toFixed(2)) : 0
      }))
    })

    const resetForm = () => {
      form.farmCode = selectedFarm.value !== 'all' ? selectedFarm.value : ''
      form.range = []
      form.markerType = '数据缺失'
      form.reason = ''
      form.excludeFromScore = true
    }

    const loadFarms = async () => {
      try {
        const response = await getReportFarms()
        farms.value = (Array.isArray(response.data) ? response.data : []).map(normalizeFarmItem).filter(Boolean)
        if (selectedFarm.value !== 'all' && !farms.value.some((item) => item.value === selectedFarm.value)) {
          selectedFarm.value = 'all'
        }
      } catch (error) {
        farms.value = []
        ElMessage.error(error.response?.data?.error || '获取场站列表失败')
      }
    }

    const loadQualityStats = async () => {
      loadingStats.value = true
      errorMessage.value = ''
      try {
        const params = { month: month.value }
        if (selectedFarm.value !== 'all') {
          params.farm_code = selectedFarm.value
        }
        const response = await getReportStatistics(params)
        statistics.value = Array.isArray(response.data?.daily_stats) ? response.data.daily_stats : []
      } catch (error) {
        statistics.value = []
        errorMessage.value = error.response?.data?.error || '获取质量统计失败'
        ElMessage.error(errorMessage.value)
      } finally {
        loadingStats.value = false
      }
    }

    const loadMarkers = async () => {
      loadingMarkers.value = true
      try {
        const params = { month: month.value }
        if (selectedFarm.value !== 'all') {
          params.farm_code = selectedFarm.value
        }
        const response = await getQualityMarkers(params)
        const rows = Array.isArray(response.data) ? response.data : []
        markers.value = rows.map((item) => ({
          ...item,
          start_time_display: formatDateTime(item.start_time),
          end_time_display: formatDateTime(item.end_time),
          created_at_display: formatDateTime(item.created_at)
        }))
      } catch (error) {
        markers.value = []
        ElMessage.error(error.response?.data?.error || '获取质量标记失败')
      } finally {
        loadingMarkers.value = false
      }
    }

    const reloadAll = async () => {
      await Promise.all([loadQualityStats(), loadMarkers()])
    }

    const openDialog = () => {
      if (!form.farmCode) {
        form.farmCode = selectedFarm.value !== 'all' ? selectedFarm.value : farms.value[0]?.value || ''
      }
      showDialog.value = true
    }

    const submitMarker = async () => {
      if (!form.farmCode || !Array.isArray(form.range) || form.range.length !== 2) {
        ElMessage.warning('请完整填写场站和时间范围')
        return
      }

      submitting.value = true
      try {
        await createQualityMarker({
          farm_code: form.farmCode,
          start_time: form.range[0],
          end_time: form.range[1],
          marker_type: form.markerType,
          reason: form.reason,
          exclude_from_score: form.excludeFromScore,
          created_by: getStoredUserName()
        })
        showDialog.value = false
        resetForm()
        await loadMarkers()
        ElMessage.success('质量标记已保存到后端')
      } catch (error) {
        ElMessage.error(error.response?.data?.error || '保存质量标记失败')
      } finally {
        submitting.value = false
      }
    }

    const handleDelete = async (row) => {
      try {
        await deleteQualityMarker(row.id)
        await loadMarkers()
        ElMessage.success('质量标记已删除')
      } catch (error) {
        ElMessage.error(error.response?.data?.error || '删除质量标记失败')
      }
    }

    watch([month, selectedFarm], () => {
      reloadAll()
    })

    onMounted(async () => {
      await loadFarms()
      resetForm()
      await reloadAll()
    })

    return {
      month,
      selectedFarm,
      farms,
      markers,
      form,
      showDialog,
      loadingStats,
      loadingMarkers,
      submitting,
      errorMessage,
      completenessCards,
      formatPercent,
      reloadAll,
      openDialog,
      submitMarker,
      handleDelete
    }
  }
}
</script>

<style scoped>
.data-quality {
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

.card-shell {
  background: var(--gradient-card);
  border: 1px solid var(--border-color);
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.result-alert {
  margin-bottom: 12px;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.quality-card {
  background: var(--gradient-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 10px;
}

.quality-card .title {
  color: var(--text-primary);
  font-weight: 600;
}

.quality-card .meta,
.meta-tip {
  color: var(--text-secondary);
  font-size: 12px;
  margin: 4px 0 8px;
}

.bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.table-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
}

@media (max-width: 1100px) {
  .page-header,
  .table-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .quality-grid {
    grid-template-columns: 1fr;
  }
}
</style>
