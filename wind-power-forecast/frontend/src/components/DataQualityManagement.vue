<template>
  <div class="data-quality page-shell">
    <div class="page-header">
      <div>
        <h2>数据质量与限电标记</h2>
        <p>质量卡片接入上报质量统计，质量标记先以本地可追溯方式沉淀，等待后端标记接口补齐。</p>
      </div>
      <el-tag type="warning" effect="dark">标记存储：localStorage 过渡方案</el-tag>
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
        <el-button type="primary" :loading="loading" @click="loadQualityStats">查询质量</el-button>
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
            月完整率 {{ formatPercent(item.completeness) }} / 月及时率 {{ formatPercent(item.timeliness) }}
          </div>
          <div class="bars">
            <el-progress :percentage="item.completeness" :stroke-width="8" :status="item.completeness < 90 ? 'exception' : 'success'" />
            <el-progress :percentage="item.timeliness" :stroke-width="8" :status="item.timeliness < 90 ? 'exception' : 'success'" />
          </div>
          <div class="meta-tip">数据源：report/statistics.daily_stats 聚合</div>
        </div>
      </div>

      <div class="table-header">
        <h3>异常/限电标记清单</h3>
        <el-button type="primary" @click="openDialog">新增标记</el-button>
      </div>

      <el-table :data="filteredMarkers" border stripe empty-text="暂无质量标记">
        <el-table-column prop="station" label="场站" min-width="140" />
        <el-table-column prop="start" label="开始时间" min-width="170" />
        <el-table-column prop="end" label="结束时间" min-width="170" />
        <el-table-column prop="type" label="标记类型" min-width="140" />
        <el-table-column prop="reason" label="原因" min-width="280" show-overflow-tooltip />
        <el-table-column prop="excludeFromScore" label="是否免考" width="110">
          <template #default="{ row }">
            <el-tag :type="row.excludeFromScore ? 'success' : 'info'" effect="plain">
              {{ row.excludeFromScore ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="记录时间" min-width="170" />
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="新增异常/限电标记" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="场站">
          <el-select v-model="form.station" filterable placeholder="选择场站">
            <el-option
              v-for="item in farms"
              :key="item.value"
              :label="item.label"
              :value="item.label"
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
          <el-select v-model="form.type">
            <el-option label="数据异常" value="数据异常" />
            <el-option label="场站限电" value="场站限电" />
            <el-option label="气象缺测" value="气象缺测" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="form.reason" type="textarea" />
        </el-form-item>
        <el-form-item label="是否免考">
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getReportFarms, getReportStatistics } from '../api/reportApi'
import { appendDataQualityMarker, listDataQualityMarkers } from '../utils/dataQualityStore'

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

export default {
  name: 'DataQualityManagement',
  setup() {
    const month = ref(formatMonthDefault())
    const selectedFarm = ref('all')
    const farms = ref([])
    const loading = ref(false)
    const errorMessage = ref('')
    const statistics = ref([])
    const markers = ref([])
    const showDialog = ref(false)
    const form = reactive({
      station: '',
      range: [],
      type: '数据异常',
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

    const filteredMarkers = computed(() => {
      if (selectedFarm.value === 'all') return markers.value
      const selected = farms.value.find((item) => item.value === selectedFarm.value)
      const farmLabel = selected?.label || selectedFarm.value
      return markers.value.filter((item) => item.station === farmLabel || item.farmCode === selectedFarm.value)
    })

    const resetForm = () => {
      form.station = ''
      form.range = []
      form.type = '数据异常'
      form.reason = ''
      form.excludeFromScore = true
    }

    const loadFarms = async () => {
      try {
        const response = await getReportFarms()
        farms.value = (Array.isArray(response.data) ? response.data : []).map(normalizeFarmItem).filter(Boolean)
      } catch (error) {
        console.error('加载场站失败:', error)
        farms.value = []
        ElMessage.error(error.response?.data?.error || '加载场站失败')
      }
    }

    const loadQualityStats = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        const params = { month: month.value }
        if (selectedFarm.value && selectedFarm.value !== 'all') {
          params.farm_code = selectedFarm.value
        }
        const response = await getReportStatistics(params)
        statistics.value = Array.isArray(response.data?.daily_stats) ? response.data.daily_stats : []
      } catch (error) {
        console.error('加载质量统计失败:', error)
        statistics.value = []
        errorMessage.value = error.response?.data?.error || '加载质量统计失败，质量卡片已回退为空。'
        ElMessage.error(errorMessage.value)
      } finally {
        loading.value = false
      }
    }

    const loadMarkers = () => {
      markers.value = listDataQualityMarkers()
    }

    const openDialog = () => {
      if (farms.value.length > 0 && !form.station) {
        form.station = farms.value[0].label
      }
      showDialog.value = true
    }

    const submitMarker = () => {
      if (!form.station || !Array.isArray(form.range) || form.range.length !== 2) {
        ElMessage.warning('请补全场站和时间范围')
        return
      }

      const linkedFarm = farms.value.find((item) => item.label === form.station)
      const marker = {
        id: `marker-${Date.now()}`,
        station: form.station,
        farmCode: linkedFarm?.value || '',
        start: form.range[0],
        end: form.range[1],
        type: form.type,
        reason: form.reason || '未填写原因',
        excludeFromScore: form.excludeFromScore,
        createdAt: new Date().toLocaleString('zh-CN', { hour12: false })
      }

      markers.value = appendDataQualityMarker(marker)
      showDialog.value = false
      resetForm()
      ElMessage.success('质量标记已保存到本地，等待后端接口补齐后可迁移')
    }

    onMounted(async () => {
      loadMarkers()
      await loadFarms()
      await loadQualityStats()
    })

    return {
      month,
      selectedFarm,
      farms,
      loading,
      errorMessage,
      completenessCards,
      markers,
      filteredMarkers,
      showDialog,
      form,
      formatPercent,
      loadQualityStats,
      openDialog,
      submitMarker
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
  background: rgba(6, 21, 34, 0.86);
  border: 1px solid rgba(130, 178, 212, 0.2);
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
  border: 1px solid rgba(130, 178, 212, 0.2);
  border-radius: 10px;
  padding: 10px;
  background: rgba(13, 36, 55, 0.5);
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
