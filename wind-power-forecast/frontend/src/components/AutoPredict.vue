<!-- src/components/AutoPredict.vue -->
<template>
  <div 
    class="autopredict-container power-predict-container" 
    v-loading="loading" 
    element-loading-text="加载中，请稍候..."
    :class="{'animated-background': isAnimatedBackground.value, 'static-background': !isAnimatedBackground.value}"
  >
    <header class="page-heading">
      <h1 class="page-title">预测任务与状态</h1>
      <p>集中查看各场站预测链路，批量控制任务，并处理需要人工复核的结果。</p>
    </header>
    <div class="fleet-overview" v-loading="fleetLoading">
      <div class="fleet-title">场站预测状态</div>
      <div class="degrade-strategy-tip">
        失败降级策略：NWP 缺失时可使用持续法/历史相似日法，状态将标记为“降级预测中”。
      </div>
      <div class="fleet-filter-row">
        <el-select
          v-model="selectedFleetFarmCodes"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          placeholder="筛选场站（默认显示全部）"
          class="fleet-farm-select"
        >
          <el-option
            v-for="farm in fleetStatus"
            :key="farm.farm_code"
            :label="`${farm.farm_name} (${farm.farm_code})`"
            :value="farm.farm_code"
          />
        </el-select>
        <el-checkbox-group v-model="selectedBatchTypes">
          <el-checkbox label="supershort">超短期</el-checkbox>
          <el-checkbox label="short">短期</el-checkbox>
          <el-checkbox label="medium">中期</el-checkbox>
        </el-checkbox-group>
        <el-button size="small" plain class="minor-action-btn" @click="selectAllVisibleMatrixRows">全选当前表格</el-button>
        <el-button size="small" plain class="minor-action-btn" @click="clearMatrixSelection">清空勾选</el-button>
        <el-button type="primary" plain size="small" :loading="matrixControlLoading" :disabled="!canManagePredictions" @click="handleControlMatrix('start')">批量启用</el-button>
        <el-button type="warning" plain size="small" :loading="matrixControlLoading" :disabled="!canManagePredictions" @click="handleControlMatrix('stop')">批量停止</el-button>
        <el-button type="danger" plain size="small" :loading="matrixControlLoading" :disabled="!canManagePredictions" @click="handleControlMatrix('delete')">批量删除</el-button>
      </div>
      <el-table
        ref="matrixTableRef"
        :data="fleetMatrixRows"
        border
        size="small"
        row-key="farm_code"
        @selection-change="handleMatrixSelectionChange"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column label="场站名称" min-width="180">
          <template #default="{ row }">
            <span class="fleet-name">{{ row.farm_name }}</span>
            <span class="fleet-code">({{ row.farm_code }})</span>
          </template>
        </el-table-column>
        <el-table-column label="NWP状态" width="120">
          <template #default="{ row }">
            <span class="biz-status" :class="`biz-${row.nwpState.level}`">{{ row.nwpState.text }}</span>
          </template>
        </el-table-column>
        <el-table-column label="超短期 (4h/15min)" min-width="150">
          <template #default="{ row }">
            <span class="biz-status" :class="`biz-${row.supershortState.level}`">{{ row.supershortState.text }}</span>
            <div class="model-tags" v-if="row.supershortModel">
              <span class="model-tag" :class="row.supershortModel.model_exists ? 'tag-ok' : 'tag-missing'" :title="row.supershortModel.model_exists ? '模型: ' + row.supershortModel.model_date : '无模型文件'">{{ row.supershortModel.model_exists ? 'M' : 'M-' }}</span>
              <span class="model-tag" :class="row.supershortModel.calib_exists ? 'tag-ok' : 'tag-missing'" :title="row.supershortModel.calib_exists ? '校准: ' + row.supershortModel.calib_date : '未校准'">{{ row.supershortModel.calib_exists ? 'C' : 'C-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="短期 (T+1日)" min-width="145">
          <template #default="{ row }">
            <span class="biz-status" :class="`biz-${row.shortState.level}`">{{ row.shortState.text }}</span>
            <div class="model-tags" v-if="row.shortModel">
              <span class="model-tag" :class="row.shortModel.model_exists ? 'tag-ok' : 'tag-missing'" :title="row.shortModel.model_exists ? '模型: ' + row.shortModel.model_date : '无模型文件'">{{ row.shortModel.model_exists ? 'M' : 'M-' }}</span>
              <span class="model-tag" :class="row.shortModel.calib_exists ? 'tag-ok' : 'tag-missing'" :title="row.shortModel.calib_exists ? '校准: ' + row.shortModel.calib_date : '未校准'">{{ row.shortModel.calib_exists ? 'C' : 'C-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="中期 (第4日)" min-width="145">
          <template #default="{ row }">
            <span class="biz-status" :class="`biz-${row.mediumState.level}`">{{ row.mediumState.text }}</span>
            <div class="model-tags" v-if="row.mediumModel">
              <span class="model-tag" :class="row.mediumModel.model_exists ? 'tag-ok' : 'tag-missing'" :title="row.mediumModel.model_exists ? '模型: ' + row.mediumModel.model_date : '无模型文件'">{{ row.mediumModel.model_exists ? 'M' : 'M-' }}</span>
              <span class="model-tag" :class="row.mediumModel.calib_exists ? 'tag-ok' : 'tag-missing'" :title="row.mediumModel.calib_exists ? '校准: ' + row.mediumModel.calib_date : '未校准'">{{ row.mediumModel.calib_exists ? 'C' : 'C-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="openFarmCurve(row)">查看曲线</el-button>
            <el-button size="small" text type="warning" @click="openManualCorrection(row)">人工修正</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div class="hero-section">
      <el-row :gutter="18">
        <el-col :span="8" v-for="(item, index) in predictions" :key="index">
          <el-card class="prediction-card smart-card" :class="`card-${item.name}`">
            <div class="card-top">
              <div class="card-title-group">
                <h3>
                  <el-icon class="title-icon"><DataAnalysis /></el-icon>
                  {{ item.title }}
                </h3>
                <div class="card-status">
                  <StatusDot :active="globalPredictStatus[item.name]" />
                  <span>{{ globalPredictStatus[item.name] ? '运行中' : '已停止' }}</span>
                </div>
              </div>
              <div class="card-actions">
                <el-switch
                  :model-value="globalPredictStatus[item.name]"
                  :disabled="!canManagePredictions"
                  :loading="isGlobalControlBusy(item.name)"
                  @change="(val) => handleGlobalSwitchToggle(item.name, val)"
                />
                <el-dropdown trigger="click" popper-class="predict-more-menu" @command="(cmd) => handleCardCommand(cmd, item)">
                  <el-button text class="more-btn">
                    <el-icon><MoreFilled /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="predict">手动补测</el-dropdown-item>
                      <el-dropdown-item command="train">手动补训练</el-dropdown-item>
                      <el-dropdown-item command="logs" divided>查看日志</el-dropdown-item>
                      <el-dropdown-item command="delete">删除任务</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>

            <div class="metric-list">
              <div class="metric-item">
                <span><el-icon><Clock /></el-icon>上次执行时间</span>
                <strong>{{ getPredictMetrics(item.name).lastRun }}</strong>
              </div>
              <div class="metric-item">
                <span><el-icon><Timer /></el-icon>执行耗时</span>
                <strong>{{ getPredictMetrics(item.name).duration }}</strong>
              </div>
              <div class="metric-item">
                <span><el-icon><AlarmClock /></el-icon>预计下次执行</span>
                <strong>{{ getPredictMetrics(item.name).nextRun }}</strong>
              </div>
              <div class="metric-item">
                <span><el-icon><Grid /></el-icon>场站聚合状态</span>
                <strong>
                  成功: {{ getPredictMetrics(item.name).aggregate.success }}
                  <span class="metric-divider">|</span>
                  <span
                    class="metric-failed"
                    :class="{ clickable: getPredictMetrics(item.name).aggregate.failed > 0 }"
                    @click="openFailedStationsDialog(item.name)"
                  >
                    失败: {{ getPredictMetrics(item.name).aggregate.failed }}
                  </span>
                  <span class="metric-divider">|</span>
                  未启用: {{ getPredictMetrics(item.name).aggregate.disabled }}
                </strong>
              </div>
            </div>

            <div class="countdown-box">
              <div class="countdown-label">距离下次执行</div>
              <div class="countdown-value">{{ getPredictMetrics(item.name).countdownText }}</div>
              <el-progress
                :percentage="getPredictMetrics(item.name).countdownProgress"
                :stroke-width="8"
                :show-text="false"
                status="success"
              />
              <div class="countdown-note">执行周期：{{ getPredictMetrics(item.name).scheduleLabel }}</div>
            </div>
            <div class="degraded-alert" v-if="getPredictMetrics(item.name).aggregate.degraded > 0">
              降级预测中：{{ getPredictMetrics(item.name).aggregate.degraded }} 个场站（建议人工复核）
            </div>

            <div class="trigger-progress" v-if="triggerProgress[item.name]">
              <div class="trigger-progress-header">
                <span class="trigger-progress-farm">{{ triggerProgress[item.name].farmDisplay }}</span>
                <span class="trigger-progress-action">{{ triggerProgress[item.name].typeLabel }}{{ triggerProgress[item.name].action }}</span>
              </div>
              <template v-if="triggerProgress[item.name].status === 'running'">
                <el-progress :percentage="100" :indeterminate="true" :stroke-width="6" :show-text="false" status="success" />
                <div class="trigger-progress-status">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  {{ triggerProgress[item.name].phase === 'queued' ? '排队中...' : '执行中...' }}
                  {{ triggerProgress[item.name].elapsed ? Math.floor(triggerProgress[item.name].elapsed) + 's' : '' }}
                </div>
              </template>
              <template v-else-if="triggerProgress[item.name].status === 'success'">
                <div class="trigger-progress-result trigger-success">
                  <el-icon><CircleCheck /></el-icon>
                  执行成功，耗时 {{ triggerProgress[item.name].duration }}
                  <el-button text size="small" @click="triggerProgress[item.name] = undefined">关闭</el-button>
                </div>
                <div class="trigger-detail" v-if="triggerProgress[item.name].result">
                  <template v-if="triggerProgress[item.name].result.meta">
                    <div class="detail-row"><span>训练样本</span><strong>{{ triggerProgress[item.name].result.meta.n_samples ?? '-' }}</strong></div>
                    <div class="detail-row"><span>验证样本</span><strong>{{ triggerProgress[item.name].result.meta.n_val_samples ?? '-' }}</strong></div>
                    <div class="detail-row"><span>测试样本</span><strong>{{ triggerProgress[item.name].result.meta.n_test_samples ?? '-' }}</strong></div>
                    <div class="detail-row"><span>特征数</span><strong>{{ triggerProgress[item.name].result.meta.n_features ?? '-' }}</strong></div>
                    <div class="detail-row" v-if="triggerProgress[item.name].result.training_lookback_days"><span>训练窗口</span><strong>最近 {{ triggerProgress[item.name].result.training_lookback_days }} 天</strong></div>
                    <template v-if="triggerProgress[item.name].result.meta.cal_accuracy">
                      <div class="detail-row"><span>准确率</span><strong>{{ (triggerProgress[item.name].result.meta.cal_accuracy.accuracy_percent ?? 0).toFixed(1) }}%</strong></div>
                      <div class="detail-row"><span>RMSE</span><strong>{{ (triggerProgress[item.name].result.meta.cal_accuracy.weighted_rmse ?? 0).toFixed(2) }}</strong></div>
                      <div class="detail-row"><span>MAE</span><strong>{{ (triggerProgress[item.name].result.meta.cal_accuracy.mae ?? 0).toFixed(2) }}</strong></div>
                      <div class="detail-row"><span>R²</span><strong>{{ (triggerProgress[item.name].result.meta.cal_accuracy.r2 ?? 0).toFixed(3) }}</strong></div>
                      <div class="detail-row"><span>偏差</span><strong>{{ (triggerProgress[item.name].result.meta.cal_accuracy.bias ?? 0).toFixed(2) }}</strong></div>
                    </template>
                    <div class="detail-row" v-if="triggerProgress[item.name].result.n_rows"><span>数据行数</span><strong>{{ triggerProgress[item.name].result.n_rows }}</strong></div>
                    <div class="detail-row" v-if="triggerProgress[item.name].result.n_shifts"><span>Shift数</span><strong>{{ triggerProgress[item.name].result.n_shifts }}</strong></div>
                    <div class="detail-row" v-if="triggerProgress[item.name].result.model_dir"><span>模型路径</span><strong class="detail-path">{{ triggerProgress[item.name].result.model_dir }}</strong></div>
                  </template>
                  <template v-else-if="triggerProgress[item.name].result.n_predictions != null">
                    <div class="detail-row"><span>预测点数</span><strong>{{ triggerProgress[item.name].result.n_predictions }}</strong></div>
                    <div class="detail-row" v-if="triggerProgress[item.name].result.target_date"><span>目标日期</span><strong>{{ triggerProgress[item.name].result.target_date }}</strong></div>
                    <div class="detail-row" v-if="triggerProgress[item.name].result.anchor_time"><span>锚定时间</span><strong>{{ triggerProgress[item.name].result.anchor_time }}</strong></div>
                  </template>
                  <template v-else-if="triggerProgress[item.name].result.alpha != null">
                    <div class="detail-row"><span>校准 alpha</span><strong>{{ (triggerProgress[item.name].result.alpha ?? 0).toFixed(4) }}</strong></div>
                    <div class="detail-row"><span>校准 beta</span><strong>{{ (triggerProgress[item.name].result.beta ?? 0).toFixed(3) }}</strong></div>
                    <div class="detail-row"><span>校准点数</span><strong>{{ triggerProgress[item.name].result.n_points ?? '-' }}</strong></div>
                    <div class="detail-row" v-if="triggerProgress[item.name].result.calib_dir"><span>参数路径</span><strong class="detail-path">{{ triggerProgress[item.name].result.calib_dir }}</strong></div>
                  </template>
                </div>
              </template>
              <template v-else-if="triggerProgress[item.name].status === 'failed'">
                <div class="trigger-progress-result trigger-failed">
                  <el-icon><CircleClose /></el-icon>
                  执行失败
                  <span v-if="triggerProgress[item.name].error" class="trigger-error-msg">{{ triggerProgress[item.name].error.slice(0, 120) }}</span>
                  <el-button text size="small" @click="triggerProgress[item.name] = undefined">关闭</el-button>
                </div>
              </template>
              <template v-else-if="triggerProgress[item.name].status === 'timeout'">
                <div class="trigger-progress-result trigger-timeout">
                  <el-icon><Warning /></el-icon>
                  等待超时，请查看日志确认结果
                  <el-button text size="small" @click="triggerProgress[item.name] = undefined">关闭</el-button>
                </div>
              </template>
            </div>

            <div class="card-footer">
              <el-button type="primary" :disabled="isControlBusy(item.name)" @click="fetchLogs(item.name)">查看日志</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 操作确认对话框 -->
    <el-dialog 
      :title="confirmDialog.title" 
      v-model="confirmDialog.visible" 
      width="30%"
    >
      <p>{{ confirmDialog.message }}</p>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button type="primary" @click="executeConfirmedAction">确定</el-button>
          <el-button @click="confirmDialog.visible = false">取消</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 定时重启设置对话框已移除 -->
    <!-- 脚本详情对话框已移除 -->

    <!-- 脚本日志对话框 -->
    <el-dialog 
      title="脚本日志" 
      v-model="logsDialogVisible" 
      width="80%"
    >
      <div class="logs-filters">
        <el-form :inline="true">
          <el-form-item label="日志类型">
            <el-select v-model="logsFilters.logType" placeholder="选择日志类型" @change="handleLogTypeChange" style="min-width: 180px;">
              <el-option v-for="option in getLogTypeOptions()" :key="option.value" :label="option.label" :value="option.value"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker
              v-model="logsFilters.date"
              type="date"
              placeholder="选择日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              style="min-width: 180px;"
            ></el-date-picker>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchLogsByFilter">查询</el-button>
            <el-button @click="resetLogsFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </div>
      <pre class="logs-content">{{ logsContent }}</pre>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button type="primary" @click="fetchLogsByFilter">刷新</el-button>
          <el-button @click="logsDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 错误详情对话框 -->
    <el-dialog 
      :title="errorTitle"
      v-model="errorDialogVisible" 
      width="50%"
    >
      <pre class="error-content">{{ errorDetails }}</pre>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button @click="errorDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      title="批量操作结果明细"
      v-model="batchResultDialogVisible"
      width="70%"
    >
      <div class="batch-summary">
        <el-tag type="info">类型：{{ batchResult.type || '-' }}</el-tag>
        <el-tag type="primary">动作：{{ batchResult.action || '-' }}</el-tag>
        <el-tag type="success">成功：{{ batchResult.summary?.success || 0 }}</el-tag>
        <el-tag type="danger">失败：{{ batchResult.summary?.failed || 0 }}</el-tag>
      </div>
      <div class="batch-result-toolbar">
        <el-select
          v-model="batchResultFarmFilter"
          clearable
          filterable
          placeholder="按场站筛选明细"
          class="batch-result-filter"
        >
          <el-option
            v-for="farmCode in batchResultFarmOptions"
            :key="farmCode"
            :label="farmCode"
            :value="farmCode"
          />
        </el-select>
        <el-button @click="batchResultFarmFilter = ''">清空筛选</el-button>
        <el-button type="warning" @click="exportFailedBatchItems">导出失败场站</el-button>
      </div>
      <el-table :data="filteredBatchResultItems" border size="small" style="width: 100%">
        <el-table-column prop="farm_code" label="场站编码" min-width="150" />
        <el-table-column prop="type" label="预测类型" width="110" />
        <el-table-column prop="status_code" label="HTTP状态" width="100" />
        <el-table-column label="结果" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.success ? 'success' : 'danger'">
              {{ scope.row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="260" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button type="primary" @click="batchResultDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      :title="`失败场站明细 - ${predictionTypeLabelMap[failedDialogPredictionType] || '-'}`"
      v-model="failedStationsDialogVisible"
      width="45%"
    >
      <el-table :data="failedStationsForDialog" border size="small">
        <el-table-column prop="farm_name" label="场站名称" min-width="140" />
        <el-table-column prop="farm_code" label="场站编码" min-width="120" />
        <el-table-column prop="reason" label="失败原因" min-width="180" />
      </el-table>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button type="primary" @click="failedStationsDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 任务历史记录对话框已移除 -->
    <!-- 历史记录详情对话框已移除 -->
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled, DataAnalysis, Clock, AlarmClock, Grid, Timer, Loading, CircleCheck, CircleClose, Warning } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import farmService from '../utils/farmService'
import { getAutoPredictStatus, getAutoPredictStatusAll, getAutoPredictOverview, controlAutoPredict, controlAutoPredictMatrix, getAutoPredictLogs, triggerAutoPredict, getAutoPredictRuns, getAutoPredictRunByTaskId } from '../api/autopredictApi'
import { getStoredUser, hasPermission } from '../utils/permission'
import StatusDot from './common/StatusDot.vue'

const isAnimatedBackground = inject('isAnimatedBackground')
const router = useRouter()
const currentUser = computed(() => getStoredUser())
const canManagePredictions = computed(() => hasPermission(currentUser.value, 'auto_predictions'))

const predictionTypeLabelMap = {
  supershort: '超短期',
  short: '短期',
  medium: '中期'
}

const predictionCycleMap = {
  supershort: { intervalMinutes: 15, anchorMinuteOfDay: 0, label: '每15分钟滚动执行' },
  short: { intervalMinutes: 1440, anchorMinuteOfDay: 530, label: '每天 08:50 定时执行' },
  medium: { intervalMinutes: 1440, anchorMinuteOfDay: 530, label: '每天 08:50 定时执行' }
}

const predictions = reactive([
  {
    name: 'supershort',
    title: '超短期风电功率预测',
    status: false
  },
  {
    name: 'short',
    title: '短期风电功率预测',
    status: false
  },
  {
    name: 'medium',
    title: '中期风电功率预测',
    status: false
  }
])

const loading = ref(true)
const controlBusyMap = reactive({
  supershort: false,
  short: false,
  medium: false
})

// 定时重启相关变量 - 已移除
// const scheduleDialogVisible = ref(false)
// const scheduleTime = ref('')
let currentPrediction = '' // Still needed for logs and other actions

// 脚本详情与日志相关变量
// const scriptInfoDialogVisible = ref(false) // Removed
// const scriptInfo = ref('') // Removed
const logsDialogVisible = ref(false)
const logsContent = ref('')
const logsFilters = reactive({
  logType: '',
  date: ''
})
const fleetStatus = ref([])
const fleetLoading = ref(false)
const selectedFleetFarmCodes = ref([])
const selectedMatrixFarmCodes = ref([])
const selectedBatchTypes = ref(['supershort', 'short', 'medium'])
const matrixControlLoading = ref(false)
const matrixTableRef = ref(null)
const globalControlBusyMap = reactive({
  supershort: false,
  short: false,
  medium: false
})
const nowTick = ref(Date.now())
const failedStationsDialogVisible = ref(false)
const failedDialogPredictionType = ref('supershort')

const errorDialogVisible = ref(false)
const errorDetails = ref('')
const errorTitle = ref('操作失败')
const batchResultDialogVisible = ref(false)
const batchResultFarmFilter = ref('')
const batchResult = reactive({
  action: '',
  type: '',
  summary: { total: 0, success: 0, failed: 0 },
  items: []
})
const batchResultFarmOptions = computed(() => {
  const items = Array.isArray(batchResult.items) ? batchResult.items : []
  return Array.from(new Set(items.map(item => item.farm_code).filter(Boolean)))
})
const filteredBatchResultItems = computed(() => {
  const items = Array.isArray(batchResult.items) ? batchResult.items : []
  const farmCode = batchResultFarmFilter.value
  if (!farmCode) {
    return items
  }
  return items.filter(item => item.farm_code === farmCode)
})

const confirmDialog = reactive({
  visible: false,
  title: '',
  message: '',
  action: '',
  params: null
})

// 任务历史记录相关变量 - 已移除
// const historyDialogVisible = ref(false)
// const historyRecords = ref([])
// const historyFilters = reactive({
//   taskType: '',
//   action: ''
// })
// const historyPagination = reactive({
//   currentPage: 1,
//   pageSize: 20,
//   total: 0
// })
// const historyDetailDialogVisible = ref(false)
// const historyDetailContent = ref('')

// 详情相关变量 - 已移除与详情弹窗相关的部分
// const taskStatus = reactive({
//   training: false,
//   prediction: false,
//   paramOpt: false,
//   trainingTime: '',
//   predictionTime: '',
//   paramOptTime: '',
//   predictionCount: 0,
//   predictionCompleted: false
// })

// const taskDateInfo = reactive({
//   selectedDate: new Date().toISOString().slice(0, 10).replace(/-/g, ''),
//   displayDate: '浠婂ぉ'
// })

const POLLING_INTERVAL = 60000
const MANUAL_TRIGGER_MAX_WAIT_SECONDS = 1000
const FARM_CHANGE_DEBOUNCE_MS = 300
let intervalId = null
let countdownTimerId = null
let farmChangeTimerId = null
let statusRequestSeq = 0
const currentFarm = ref(farmService.getCurrentFarm())
const statusUpdatedAt = ref(null)

const handleFarmChanged = (farmCode) => {
  currentFarm.value = farmCode
  if (farmChangeTimerId) {
    clearTimeout(farmChangeTimerId)
  }
  farmChangeTimerId = setTimeout(() => {
    fetchStatus()
    fetchFleetStatus()
  }, FARM_CHANGE_DEBOUNCE_MS)
}

const formatHms = (dateLike) => {
  if (!dateLike) return '--'
  const date = new Date(dateLike)
  if (Number.isNaN(date.getTime())) return '--'
  const hh = `${date.getHours()}`.padStart(2, '0')
  const mm = `${date.getMinutes()}`.padStart(2, '0')
  const ss = `${date.getSeconds()}`.padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

const formatCountdown = (seconds) => {
  if (!Number.isFinite(seconds) || seconds < 0) return '--:--'
  const hh = Math.floor(seconds / 3600)
  const mm = Math.floor((seconds % 3600) / 60)
  const ss = Math.floor(seconds % 60)
  if (hh > 0) {
    return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
  }
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

const computeNextRunByType = (predictionName) => {
  const cycle = predictionCycleMap[predictionName] || predictionCycleMap.short
  const now = new Date(nowTick.value)
  const startOfDay = new Date(now)
  startOfDay.setHours(0, 0, 0, 0)

  const nowMinute = now.getHours() * 60 + now.getMinutes()
  let nextMinute = cycle.anchorMinuteOfDay
  while (nextMinute <= nowMinute) {
    nextMinute += cycle.intervalMinutes
  }

  const dayOffset = Math.floor(nextMinute / 1440)
  const minuteInDay = nextMinute % 1440
  const next = new Date(startOfDay)
  next.setDate(next.getDate() + dayOffset)
  next.setMinutes(minuteInDay)
  next.setSeconds(0, 0)
  return next
}

const normalizeBizState = (statusObj) => {
  if (!statusObj) return { level: 'disabled', text: '未配置', reason: '未配置' }
  if (typeof statusObj === 'boolean') {
    return statusObj
      ? { level: 'ready', text: '已启用', reason: '' }
      : { level: 'disabled', text: '未启用', reason: '' }
  }
  if (typeof statusObj === 'object') {
    if (!statusObj.enabled) return { level: 'disabled', text: '未启用', reason: '' }
    const lastStatus = statusObj.last_predict_status || statusObj.last_train_status
    if (lastStatus === 'running') return { level: 'running', text: '执行中...', reason: '' }
    if (lastStatus === 'failed') return { level: 'failed', text: '失败', reason: statusObj.last_error || '' }
    if (lastStatus === 'success') {
      const updatedAt = statusObj.last_predict_at || statusObj.last_train_at
      const timeStr = updatedAt ? updatedAt.slice(11, 16) : ''
      return { level: 'ready', text: timeStr ? `${timeStr} 已更新` : '已启用', reason: '' }
    }
    return { level: 'ready', text: '已启用', reason: '' }
  }
  return { level: 'unknown', text: '状态未知', reason: '' }
}

const fleetMatrixRows = computed(() => {
  const rows = Array.isArray(fleetStatus.value) ? fleetStatus.value : []
  const filterCodes = Array.isArray(selectedFleetFarmCodes.value) ? selectedFleetFarmCodes.value : []
  const applyFilter = filterCodes.length > 0

  return rows
    .filter((farm) => !applyFilter || filterCodes.includes(farm.farm_code))
    .map((farm) => {
      const status = farm.status || {}
      const modelInfo = farm.model_info || {}

      const nwpState = normalizeBizState(
        status.supershort?.enabled ? status.supershort : null
      )

      const supershortState = nwpState.level === 'failed'
        ? { level: 'failed', text: 'NWP缺失', reason: 'NWP缺失' }
        : normalizeBizState(status.supershort)

      const shortState = normalizeBizState(status.short)
      const mediumState = normalizeBizState(status.medium)

      return {
        ...farm,
        nwpState,
        supershortState,
        shortState,
        mediumState,
        supershortModel: modelInfo.supershort || {},
        shortModel: modelInfo.short || {},
        mediumModel: modelInfo.medium || {},
      }
    })
})

const globalPredictStatus = computed(() => {
  const result = { supershort: false, short: false, medium: false }
  const rows = Array.isArray(fleetStatus.value) ? fleetStatus.value : []
  rows.forEach((farm) => {
    result.supershort = result.supershort || !!farm.status?.supershort
    result.short = result.short || !!farm.status?.short
    result.medium = result.medium || !!farm.status?.medium
  })
  return result
})

const aggregateByTypeMap = computed(() => {
  const base = {
    supershort: { success: 0, failed: 0, disabled: 0, degraded: 0 },
    short: { success: 0, failed: 0, disabled: 0, degraded: 0 },
    medium: { success: 0, failed: 0, disabled: 0, degraded: 0 }
  }
  fleetMatrixRows.value.forEach((row) => {
    const entries = [
      ['supershort', row.supershortState],
      ['short', row.shortState],
      ['medium', row.mediumState]
    ]
    entries.forEach(([type, state]) => {
      if (state.level === 'ready' || state.level === 'running') {
        base[type].success += 1
      } else if (state.level === 'failed') {
        base[type].failed += 1
      } else if (state.level === 'degraded' || state.level === 'delayed') {
        base[type].degraded += 1
      } else {
        base[type].disabled += 1
      }
    })
  })
  return base
})

// Aggregate last run info across all farms per prediction type
const lastRunsByType = computed(() => {
  const result = { supershort: null, short: null, medium: null }
  const rows = Array.isArray(fleetStatus.value) ? fleetStatus.value : []
  for (const farm of rows) {
    const lastRuns = farm.last_runs || {}
    for (const type of ['supershort', 'short', 'medium']) {
      const run = lastRuns[type]
      if (run && run.finished_at) {
        if (!result[type] || run.finished_at > (result[type].finished_at || '')) {
          result[type] = run
        }
      }
    }
  }
  return result
})

const failedStationsMap = computed(() => {
  const map = { supershort: [], short: [], medium: [] }
  fleetMatrixRows.value.forEach((row) => {
    if (row.supershortState.level === 'failed') {
      map.supershort.push({ farm_name: row.farm_name, farm_code: row.farm_code, reason: row.supershortState.reason || row.supershortState.text })
    }
    if (row.shortState.level === 'failed') {
      map.short.push({ farm_name: row.farm_name, farm_code: row.farm_code, reason: row.shortState.reason || row.shortState.text })
    }
    if (row.mediumState.level === 'failed') {
      map.medium.push({ farm_name: row.farm_name, farm_code: row.farm_code, reason: row.mediumState.reason || row.mediumState.text })
    }
  })
  return map
})

const failedStationsForDialog = computed(() => failedStationsMap.value[failedDialogPredictionType.value] || [])

const getPredictMetrics = (predictionName) => {
  const cycle = predictionCycleMap[predictionName] || predictionCycleMap.short
  const nextRunDate = computeNextRunByType(predictionName)
  const now = new Date(nowTick.value)
  const countdownSeconds = Math.max(0, Math.floor((nextRunDate.getTime() - now.getTime()) / 1000))
  const cycleSeconds = cycle.intervalMinutes * 60
  const progress = cycleSeconds > 0 ? Math.min(100, Math.max(0, Number((((cycleSeconds - countdownSeconds) / cycleSeconds) * 100).toFixed(2)))) : 0
  const aggregate = aggregateByTypeMap.value[predictionName] || { success: 0, failed: 0, disabled: 0, degraded: 0 }

  const lastRun = lastRunsByType.value[predictionName]
  const lastRunTime = lastRun?.finished_at
    ? new Date(lastRun.finished_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '未执行'
  const lastRunDuration = lastRun?.duration_sec != null ? `${lastRun.duration_sec}s` : '-'

  return {
    lastRun: lastRunTime,
    duration: lastRunDuration,
    nextRun: formatHms(nextRunDate),
    countdownText: formatCountdown(countdownSeconds),
    countdownProgress: progress,
    scheduleLabel: cycle.label,
    aggregate
  }
}

const triggerBusyMap = reactive({})

const triggerProgress = reactive({})

const getFarmDisplayName = () => {
  const code = currentFarm.value || farmService.getCurrentFarm()
  const farms = farmService.getAvailableFarms()
  const found = farms.find(f => f.code === code)
  return found ? `${found.name} (${code})` : code
}

const typeLabelMap = { supershort: '超短期', short: '短期', medium: '中期' }

const handleCardCommand = (command, item) => {
  if (command === 'predict' || command === 'train') {
    if (!canManagePredictions.value) {
      ElMessage.warning('当前账号没有执行预测控制的权限')
      return
    }
    const actionLabel = command === 'train' ? '训练' : '预测'
    const farmDisplay = getFarmDisplayName()
    showConfirmDialog(
      'manualTrigger',
      `确认手动补${actionLabel}`,
      `即将对 ${farmDisplay} 执行 ${typeLabelMap[item.name] || item.name}${actionLabel}，是否继续？`,
      { predictionType: item.name, action: command },
    )
    return
  }
  if (command === 'logs') {
    fetchLogs(item.name)
    return
  }
  if (command === 'delete') {
    if (!canManagePredictions.value) {
      ElMessage.warning('当前账号没有执行预测控制的权限')
      return
    }
    showConfirmDialog('deleteTask', '删除预测任务', `确定要删除 ${item.title} 吗？`, item.name)
  }
}

const pollTriggerProgress = (predictionType, celeryTaskId) => {
  const key = predictionType
  let elapsed = 0
  const maxWait = MANUAL_TRIGGER_MAX_WAIT_SECONDS
  const interval = 3000

  const timer = setInterval(async () => {
    elapsed += interval / 1000
    if (elapsed > maxWait) {
      clearInterval(timer)
      if (triggerProgress[key]?.status === 'running') {
        triggerProgress[key] = { ...triggerProgress[key], status: 'timeout' }
      }
      return
    }

    try {
      let run = null
      if (celeryTaskId) {
        const res = await getAutoPredictRunByTaskId(celeryTaskId)
        const items = res?.data?.data?.items || res?.data?.items || []
        run = items[0]
      } else {
        const farmCode = currentFarm.value || farmService.getCurrentFarm()
        const res = await getAutoPredictRuns(farmCode, predictionType, 1)
        const items = res?.data?.data?.items || res?.data?.items || []
        run = items[0]
      }
      if (run && !['queued', 'running'].includes(run.status)) {
        clearInterval(timer)
        triggerProgress[key] = {
          ...triggerProgress[key],
          status: run.status,
          duration: run.duration_sec ? `${run.duration_sec}s` : '-',
          error: run.error_message || '',
          finishedAt: run.finished_at,
          result: run.result || null,
        }
        fetchStatus()
        fetchFleetStatus()
      } else if (run && run.status === 'running') {
        const startedAtMs = run.started_at ? new Date(run.started_at).getTime() : NaN
        const runElapsed = Number.isFinite(startedAtMs)
          ? Math.max(0, (Date.now() - startedAtMs) / 1000)
          : elapsed
        triggerProgress[key] = {
          ...triggerProgress[key],
          phase: 'running',
          elapsed: runElapsed,
        }
      } else if (run && run.status === 'queued') {
        triggerProgress[key] = {
          ...triggerProgress[key],
          phase: 'queued',
          elapsed,
        }
      } else {
        triggerProgress[key] = {
          ...triggerProgress[key],
          phase: 'queued',
          elapsed,
        }
      }
    } catch {
      // ignore poll errors
    }
  }, interval)
}

const handleManualTrigger = async (predictionType, action) => {
  const key = predictionType
  if (triggerBusyMap[key]) return
  const actionLabel = action === 'train' ? '训练' : '预测'
  try {
    triggerBusyMap[key] = true
    const farmCode = currentFarm.value || farmService.getCurrentFarm()
    const res = await triggerAutoPredict(farmCode, predictionType, action)
    const data = res?.data?.data || res?.data || {}
    const taskId = data.celery_task_id || ''
    triggerProgress[key] = {
      status: 'running',
      action: actionLabel,
      typeLabel: typeLabelMap[predictionType] || predictionType,
      farmDisplay: getFarmDisplayName(),
      taskId: taskId ? taskId.slice(0, 8) + '...' : '',
      phase: 'queued',
      elapsed: 0,
    }
    pollTriggerProgress(predictionType, taskId)
  } catch (err) {
    const msg = err?.response?.data?.message || err?.response?.data?.error || err.message || '未知错误'
    ElMessage.error(`${typeLabelMap[predictionType] || predictionType}${actionLabel}触发失败: ${msg}`)
  } finally {
    triggerBusyMap[key] = false
  }
}

onMounted(async () => {
  farmService.addListener(handleFarmChanged)
  await farmService.loadAvailableFarms()
  currentFarm.value = farmService.getCurrentFarm()
  fetchStatus()
  fetchFleetStatus()
  countdownTimerId = setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
  intervalId = setInterval(() => {
    fetchStatus()
    fetchFleetStatus()
  }, POLLING_INTERVAL)
})

onUnmounted(() => {
  farmService.removeListener(handleFarmChanged)
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
  if (countdownTimerId) {
    clearInterval(countdownTimerId)
    countdownTimerId = null
  }
  if (farmChangeTimerId) {
    clearTimeout(farmChangeTimerId)
    farmChangeTimerId = null
  }
})

const showErrorDialog = (title, details) => {
  errorTitle.value = title || '操作失败'
  errorDetails.value = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details)
  errorDialogVisible.value = true
}

const isControlBusy = (predictionName) => {
  return !!controlBusyMap[predictionName]
}


const fetchStatus = async () => {
  const requestId = ++statusRequestSeq
  loading.value = true
  try {
    const res = await getAutoPredictStatus(currentFarm.value)
    if (requestId !== statusRequestSeq) {
      return
    }
    const payload = res.data?.data || res.data || {}
    predictions.forEach(p => {
      p.status = payload[p.name] || false
    })
    statusUpdatedAt.value = Date.now()
  } catch (error) {
    if (requestId !== statusRequestSeq) {
      return
    }
    console.error('获取状态失败:', error)
  } finally {
    if (requestId === statusRequestSeq) {
      loading.value = false
    }
  }
}

const fetchFleetStatus = async () => {
  fleetLoading.value = true
  try {
    let res
    try {
      res = await getAutoPredictOverview()
    } catch {
      res = await getAutoPredictStatusAll()
    }
    const payload = res.data?.data || res.data || {}
    const items = Array.isArray(payload.items) ? payload.items : []
    fleetStatus.value = items

    const availableCodes = items.map(item => item.farm_code).filter(Boolean)
    selectedFleetFarmCodes.value = selectedFleetFarmCodes.value.filter(code => availableCodes.includes(code))
    selectedMatrixFarmCodes.value = selectedMatrixFarmCodes.value.filter(code => availableCodes.includes(code))
  } catch (error) {
    console.error('获取多场站状态失败:', error)
  } finally {
    fleetLoading.value = false
  }
}

const handleMatrixSelectionChange = (selection) => {
  selectedMatrixFarmCodes.value = (Array.isArray(selection) ? selection : [])
    .map(item => item.farm_code)
    .filter(Boolean)
}

const selectAllVisibleMatrixRows = async () => {
  await nextTick()
  const table = matrixTableRef.value
  if (!table) return
  table.clearSelection()
  fleetMatrixRows.value.forEach((row) => {
    table.toggleRowSelection(row, true)
  })
}

const clearMatrixSelection = () => {
  selectedMatrixFarmCodes.value = []
  matrixTableRef.value?.clearSelection()
}

const openFarmCurve = (row) => {
  farmService.setCurrentFarm(row.farm_code)
  router.push({
    name: 'PowerCompare',
    query: { farm_code: row.farm_code, prediction_type: predictionTypeLabelMap.supershort }
  })
}

const openManualCorrection = (row) => {
  farmService.setCurrentFarm(row.farm_code)
  router.push({
    name: 'ReportManagement',
    query: { farm_code: row.farm_code, source: 'autopredict_matrix', mode: 'manual_correction' }
  })
}

const openFailedStationsDialog = (predictionType) => {
  const failed = aggregateByTypeMap.value[predictionType]?.failed || 0
  if (failed <= 0) return
  failedDialogPredictionType.value = predictionType
  failedStationsDialogVisible.value = true
}

const exportFailedBatchItems = () => {
  const items = Array.isArray(batchResult.items) ? batchResult.items : []
  const failedItems = items.filter(item => !item.success)
  if (failedItems.length === 0) {
    ElMessage.info('没有失败场站可导出')
    return
  }

  const header = ['farm_code', 'status_code', 'code', 'message']
  const rows = failedItems.map(item => [
    item.farm_code || '',
    String(item.status_code ?? ''),
    String(item.code ?? ''),
    String(item.message ?? '').replace(/"/g, '""')
  ])
  const csv = [header.join(','), ...rows.map(row => `${row[0]},${row[1]},${row[2]},"${row[3]}"`)].join('\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `batch_failed_${batchResult.type || 'unknown'}_${Date.now()}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出失败场站 ${failedItems.length} 条`)
}

const showConfirmDialog = (action, title, message, params = null) => {
  confirmDialog.action = action
  confirmDialog.title = title
  confirmDialog.message = message
  confirmDialog.params = params
  confirmDialog.visible = true
}

const executeConfirmedAction = () => {
  confirmDialog.visible = false
  switch (confirmDialog.action) {
    case 'startTask':
      handleControl(confirmDialog.params, 'start')
      break
    case 'stopTask':
      handleControl(confirmDialog.params, 'stop')
      break
    case 'deleteTask':
      handleControl(confirmDialog.params, 'delete')
      break
    case 'manualTrigger':
      handleManualTrigger(confirmDialog.params.predictionType, confirmDialog.params.action)
      break
    default:
      console.warn('未知操作:', confirmDialog.action)
  }
}

const handleControl = async (name, action) => {
  if (!canManagePredictions.value) {
    ElMessage.warning('当前账号没有执行预测控制的权限')
    return
  }
  if (isControlBusy(name)) {
    ElMessage.warning('操作正在处理中，请稍候')
    return
  }

  controlBusyMap[name] = true
  console.log('handleControl invoked', name, action)
  loading.value = true
  try {
    const res = await controlAutoPredict(action, name, currentFarm.value)
    const payload = res.data?.data || res.data || {}
    if (payload.warning || res.data?.warning) {
      ElMessage.warning(payload.warning || res.data.warning)
    } else {
      ElMessage.success(res.data.message || '操作成功')
    }
    setTimeout(async () => {
      await fetchStatus()
    }, 1000)
  } catch (error) {
    if (error?.response?.status === 409) {
      ElMessage.warning(error?.response?.data?.message || '任务操作冲突，请稍后再试')
      return
    }
    if (error.response && error.response.data) {
      const errorData = error.response.data
      showErrorDialog(
        `${action} ${name} 失败`, 
        errorData.details || errorData.error || error.message
      )
    }
  } finally {
    controlBusyMap[name] = false
    loading.value = false
  }
}

const isGlobalControlBusy = (predictionName) => {
  return !!globalControlBusyMap[predictionName]
}

const handleGlobalSwitchToggle = async (predictionType, enabled) => {
  if (!canManagePredictions.value) {
    ElMessage.warning('当前账号没有执行预测控制的权限')
    return
  }
  if (isGlobalControlBusy(predictionType)) {
    ElMessage.warning('全局操作正在处理中，请稍候')
    return
  }

  const allFarmCodes = fleetStatus.value.map(item => item.farm_code).filter(Boolean)
  if (allFarmCodes.length === 0) {
    ElMessage.warning('暂无可操作场站')
    return
  }

  const action = enabled ? 'start' : 'stop'
  if (!enabled) {
    try {
      await ElMessageBox.confirm(
        `您确定要停止所有场站的${predictionTypeLabelMap[predictionType]}预测吗？这将导致无法自动上报！`,
        '高危操作确认',
        {
          confirmButtonText: '确认停止',
          cancelButtonText: '取消',
          type: 'warning',
          confirmButtonClass: 'el-button--danger'
        }
      )
    } catch {
      return
    }
  }

  globalControlBusyMap[predictionType] = true
  loading.value = true
  try {
    const res = await controlAutoPredictMatrix(action, [predictionType], allFarmCodes)
    const payload = res.data?.data || res.data || {}
    const summary = payload.summary || {}
    const success = Number(summary.success || 0)
    const failed = Number(summary.failed || 0)
    if (failed > 0) {
      ElMessage.warning(`全局${action}完成：成功 ${success}，失败 ${failed}`)
    } else {
      ElMessage.success(`全局${action}完成：成功 ${success}`)
    }
    await fetchStatus()
    await fetchFleetStatus()
  } catch (error) {
    if (error?.response?.status === 409) {
      ElMessage.warning(error?.response?.data?.message || '全局操作冲突，请稍后再试')
      return
    }
    const message = error?.response?.data?.details || error?.response?.data?.error || error?.message || '未知错误'
    showErrorDialog(`全局${action}失败`, message)
  } finally {
    globalControlBusyMap[predictionType] = false
    loading.value = false
  }
}

const handleControlMatrix = async (action) => {
  if (!canManagePredictions.value) {
    ElMessage.warning('当前账号没有执行预测控制的权限')
    return
  }
  if (matrixControlLoading.value) {
    ElMessage.warning('矩阵批量操作正在处理中，请稍候')
    return
  }

  const targetFarmCodes = Array.isArray(selectedMatrixFarmCodes.value)
    ? selectedMatrixFarmCodes.value.filter(Boolean)
    : []
  const targetTypes = Array.isArray(selectedBatchTypes.value)
    ? selectedBatchTypes.value.filter(Boolean)
    : []

  if (targetFarmCodes.length === 0) {
    ElMessage.warning('请先勾选至少一个场站')
    return
  }
  if (targetTypes.length === 0) {
    ElMessage.warning('请至少选择一个预测类型')
    return
  }

  matrixControlLoading.value = true
  loading.value = true
  try {
    const res = await controlAutoPredictMatrix(action, targetTypes, targetFarmCodes)
    const payload = res.data?.data || res.data || {}
    const summary = payload.summary || {}
    const success = Number(summary.success || 0)
    const total = Number(summary.total || (targetFarmCodes.length * targetTypes.length))
    const failed = Number(summary.failed || 0)

    batchResult.action = action
    batchResult.type = targetTypes.join(',')
    batchResult.summary = { total, success, failed }
    batchResult.items = Array.isArray(payload.items) ? payload.items : []
    batchResultFarmFilter.value = ''
    batchResultDialogVisible.value = true

    if (failed > 0) {
      ElMessage.warning(`矩阵批量${action}完成：成功 ${success}/${total}，失败 ${failed}`)
    } else {
      ElMessage.success(`矩阵批量${action}完成：成功 ${success}/${total}`)
    }
    await fetchStatus()
    await fetchFleetStatus()
  } catch (error) {
    if (error?.response?.status === 409) {
      ElMessage.warning(error?.response?.data?.message || '矩阵批量操作冲突，请稍后再试')
      return
    }
    if (error.response && error.response.data) {
      const errorData = error.response.data
      showErrorDialog(
        `矩阵批量${action}失败`,
        errorData.details || errorData.error || error.message
      )
    }
  } finally {
    matrixControlLoading.value = false
    loading.value = false
  }
}

// 定时重启方法 (showScheduleDialog, setSchedule) 已移除
// 保存/加载/删除 PM2 配置方法 (saveSettings, resurrectConfig, clearSavedConfig) 已移除
// 查询脚本详情方法 (fetchScriptInfo) 已移除
// 获取任务状态方法 (fetchTaskStatus, refreshTaskStatus, fetchTaskStatusByDate, resetTaskDateInfo) 已移除
// 获取任务标题方法 (getTaskTitle) 已移除（如果日志部分不再需要可彻底删除）

// 获取脚本日志
const fetchLogs = async (name) => {
  currentPrediction = name // Set currentPrediction for logs
  logsDialogVisible.value = true
  logsFilters.logType = 'train'
  logsFilters.date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  fetchLogsByFilter()
}

const fetchLogsByFilter = async () => {
  loading.value = true
  try {
    const queryDate = logsFilters.date || new Date().toISOString().slice(0, 10).replace(/-/g, '')
    if (logsFilters.logType === 'param') {
      // params.param_opt_day = getParamOptDay(currentPrediction) // getParamOptDay is removed
      // If param logs are specific to a day derived from task type, adjust or remove this logic
      // For now, removing it if getParamOptDay is fully removed
    }
    const res = await getAutoPredictLogs(currentPrediction, currentFarm.value, {
      logType: logsFilters.logType || 'train',
      date: queryDate,
      lines: 500
    })
    const payload = res.data?.data || res.data || {}
    logsContent.value = payload.logs || res.data.logs || '暂无日志信息'
  } catch (error) {
    console.error('获取日志失败:', error)
    if (error.response && error.response.data) {
      showErrorDialog(
        '获取日志失败', 
        error.response.data.details || error.response.data.error || error.message
      )
    }
  } finally {
    loading.value = false
  }
}

const resetLogsFilters = () => {
  logsFilters.logType = 'train'
  logsFilters.date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  fetchLogsByFilter()
}

const getLogTypeOptions = () => {
  if (currentPrediction === 'supershort') {
    return [
      // { label: '涓昏皟搴︽棩蹇?, value: 'main' },
      { label: '每日训练日志', value: 'train' },
      { label: '实时预测日志', value: 'predict' }
    ]
  } 
  return [
    { label: '训练日志', value: 'train' },
    // { label: '参数优化日志', value: 'param' } // Consider if 'param' logs still relevant/obtainable without 'details'
  ]
}

const handleLogTypeChange = () => {
  fetchLogsByFilter()
}

// 任务历史记录相关方法 (openHistoryDialog, fetchTaskHistory, resetHistoryFilters, handleSizeChange, handleCurrentChange, showHistoryDetail) 已移除
// 历史记录辅助方法 (getTaskTypeTagType, getTaskTypeLabel, getActionTagType, getActionLabel, getStatusTagType, getStatusLabel) 已移除
// 参数优化星期相关方法 (getParamOptWeekday, getParamOptDay) 已移除
// 预测任务状态文本/类型方法 (getTaskPredictionType, getTaskPredictionStatus) 已移除

// getTaskTitle might still be used by logs, so keeping it conditionally or removing if not used.

</script>

<style scoped>
/* Styles remain largely the same, but some related to removed dialogs might be implicitly unused */
.autopredict-container {
  min-height: 100%;
  padding: 28px 32px 40px;
  position: relative;
  z-index: 1;
}

.power-predict-container {
  min-height: 100vh;
  background: transparent !important;
  position: relative;
}

.page-title {
  color: var(--text-primary);
  text-shadow: none;
  margin: 0;
}

.page-heading {
  margin-bottom: 16px;
}

.page-heading p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.fleet-overview {
  margin: 0 0 20px;
  padding: 18px 20px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.fleet-overview :deep(.el-table__cell.el-table-fixed-column--right) {
  background: var(--surface) !important;
}

.fleet-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.degrade-strategy-tip {
  font-size: 12px;
  color: var(--warning);
  margin-bottom: 10px;
}

.fleet-filter-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.minor-action-btn {
  background: var(--surface) !important;
  border-color: var(--border-color) !important;
  color: var(--text-secondary) !important;
}

.fleet-farm-select {
  min-width: 360px;
  max-width: 680px;
}

.fleet-code {
  margin-left: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.fleet-name {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 0;
}

.fleet-filter-row .el-button--primary.is-plain,
.fleet-filter-row .el-button--warning.is-plain,
.fleet-filter-row .el-button--danger.is-plain {
  background: transparent !important;
}

.fleet-filter-row .el-button--primary.is-plain {
  color: var(--primary) !important;
  border-color: rgba(36, 122, 82, 0.34) !important;
}

.fleet-filter-row .el-button--warning.is-plain {
  color: var(--warning) !important;
  border-color: rgba(183, 121, 31, 0.34) !important;
}

.fleet-filter-row .el-button--danger.is-plain {
  color: var(--danger) !important;
  border-color: rgba(196, 82, 82, 0.34) !important;
}

.biz-status {
  display: inline-block;
  border-radius: 14px;
  border: 1px solid transparent;
  padding: 2px 10px;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.biz-ready {
  color: var(--success);
  border-color: #cbe2d4;
  background: var(--accent-soft);
}

.biz-running {
  color: var(--warning);
  border-color: #ead6b4;
  background: var(--warning-soft);
}

.biz-delayed,
.biz-degraded {
  color: var(--warning);
  border-color: #ead6b4;
  background: var(--warning-soft);
}

.biz-failed {
  color: var(--danger);
  border-color: #edc9c9;
  background: var(--danger-soft);
}

.biz-disabled,
.biz-unknown {
  color: var(--text-muted);
  border-color: var(--border-color);
  background: var(--bg-muted);
}

.model-tags {
  display: inline-flex;
  gap: 4px;
  margin-left: 6px;
  vertical-align: middle;
}
.model-tag {
  display: inline-block;
  width: 20px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  cursor: default;
}
.model-tag.tag-ok {
  color: var(--success);
  background: var(--accent-soft);
  border: 1px solid #cbe2d4;
}
.model-tag.tag-missing {
  color: var(--danger);
  background: var(--danger-soft);
  border: 1px solid #edc9c9;
}

.hero-section {
  text-align: left;
  padding: 8px 2px 0;
  position: relative;
}

.autopredict-container h2 {
  font-size: 48px;
  font-weight: 600;
  margin-bottom: 40px;
  text-align: center;
  color: var(--text-primary);
  letter-spacing: -0.003em;
  line-height: 1.1;
}

.global-buttons {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 24px;
}


.button-group {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  justify-content: center;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 0;
}

.button-group .el-button {
  width: 100%;
  justify-content: center;
  min-width: 80px;
}

.batch-actions {
  grid-template-columns: repeat(3, 1fr);
  padding-top: 8px;
}

.batch-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.batch-result-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.batch-result-filter {
  min-width: 240px;
}

.el-row {
  margin: 0 -10px;
}

.el-col {
  padding: 0 10px;
  margin-bottom: 12px;
}

.el-card {
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: none;
  padding: 16px;
}

.el-card:hover {
  border-color: var(--border-strong);
}

.prediction-card {
  padding: 14px;
  border: none;
  min-height: 284px;
  position: relative;
  overflow: hidden;
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.card-title-group h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.title-icon {
  color: var(--primary);
}

.card-status {
  margin-top: 6px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.card-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.more-btn {
  color: var(--text-secondary) !important;
}

:deep(.predict-more-menu) {
  background: var(--surface) !important;
  border: 1px solid var(--border-color) !important;
  box-shadow: var(--shadow-float);
}

:deep(.predict-more-menu .el-dropdown-menu__item) {
  color: var(--text-primary) !important;
}

:deep(.predict-more-menu .el-dropdown-menu__item:hover) {
  background: var(--surface-soft) !important;
  color: var(--primary) !important;
}

.metric-list {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.metric-item {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 8px;
  background: var(--surface-soft);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-item span {
  color: var(--text-muted);
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.metric-item strong {
  color: var(--text-primary);
  font-size: 14px;
  font-family: Consolas, Menlo, Monaco, monospace;
}

.metric-divider {
  margin: 0 5px;
  color: var(--text-muted);
}

.metric-failed {
  color: var(--danger);
}

.metric-failed.clickable {
  cursor: pointer;
  text-decoration: underline;
}

.countdown-box {
  margin-top: 10px;
  padding: 10px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--surface-soft);
}

.countdown-label {
  color: var(--text-muted);
  font-size: 12px;
}

.countdown-value {
  color: var(--warning);
  font-size: 22px;
  font-family: Consolas, Menlo, Monaco, monospace;
  margin: 2px 0 8px;
}

.countdown-note {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.degraded-alert {
  margin-top: 8px;
  font-size: 12px;
  color: var(--warning);
}

.trigger-progress {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--surface-soft);
  border: 1px solid var(--border-light);
}
.trigger-progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
}
.trigger-progress-farm {
  color: var(--accent-blue);
  font-weight: 600;
}
.trigger-progress-action {
  color: var(--text-secondary);
}
.trigger-progress-status {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}
.trigger-progress-result {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.trigger-success {
  color: var(--success);
}
.trigger-failed {
  color: var(--danger);
}
.trigger-timeout {
  color: var(--warning);
}
.trigger-error-msg {
  color: var(--text-muted);
  font-size: 11px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trigger-detail {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
}
.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  line-height: 1.8;
}
.detail-row span {
  color: var(--text-muted);
}
.detail-row strong {
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.detail-row .detail-path {
  font-family: monospace;
  font-size: 11px;
  word-break: break-all;
  color: var(--accent-blue);
}

.card-footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.card-footer .el-button {
  min-width: 100px;
}

.prediction-card :deep(.el-card__header) {
  display: none;
  border-bottom: 1px solid var(--border-color);
}

.prediction-card :deep(.el-card__header span) {
  font-size: 24px;
  font-weight: 500;
  color: var(--text-primary);
}

.el-dialog {
  border-radius: 20px;
  overflow: hidden;
  transform: none !important;
  margin: 0 auto !important;
  position: relative;
  max-width: 90%;
  top: 50%;
  margin-top: 0 !important;
}

:deep(.el-overlay-dialog) {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
}

.el-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  margin: 0;
  background: transparent;
  border-bottom: 1px solid var(--border-color);
}

.el-dialog :deep(.el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.el-dialog :deep(.el-dialog__body) {
  padding: 24px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.el-dialog :deep(.el-dialog__body p) {
  margin: 0;
  text-align: center;
  width: 100%;
}

.el-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px 24px;
  text-align: center;
}

.dialog-footer-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  width: 100%;
}

.dialog-footer-buttons .el-button {
  margin-left: 0;
  flex: 0 0 auto;
  min-width: 100px;
}

.info-content, .logs-content, .error-content, .history-detail-content {
  max-height: 600px;
  overflow-y: auto;
  background: var(--surface-soft);
  padding: 24px;
  border-radius: 12px;
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.history-filters {
  margin-bottom: 24px;
}

.pagination-container {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

@media (max-width: 768px) {
  .autopredict-container {
    padding: 20px;
  }

  .autopredict-container h2 {
    font-size: 32px;
  }

  .el-button {
    height: 40px;
    padding: 0 20px;
    font-size: 14px;
  }

  .el-row {
    gap: 16px;  
    margin: 0 10px;  
  }
  
  .el-col {
    margin-bottom: 16px;  
  }
  
  .global-buttons {
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .fleet-filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .fleet-farm-select {
    min-width: 100%;
    max-width: 100%;
  }

  .batch-result-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-result-filter {
    min-width: 100%;
  }
}

.logs-filters {
  margin-bottom: 20px;
  background: var(--surface-soft);
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

/* Styles for removed dialogs and their contents can be cleaned up if desired */
/* .task-info-container, .task-status-cards, .script-info-section, .ultra-start-options, .task-date-selector might be unused now */

</style>
