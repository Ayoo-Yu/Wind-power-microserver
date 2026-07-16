<template>
  <div class="data-population page-shell">
    <div class="gradient-background"></div>

    <div class="page-header">
      <h1 class="page-title">数据补齐工具</h1>
      <p class="page-description">通过 CSV 文件批量导入历史数据，支持实测功率与气象预测两类数据</p>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="main-tabs" @tab-change="resetState">
      <!-- ========== Tab 1: 实测数据 ========== -->
      <el-tab-pane label="实测数据" name="actual">
        <el-card class="card-shell" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">配置</span>
            </div>
          </template>
          <el-form label-width="100px" label-position="left">
            <el-row :gutter="24">
              <el-col :span="8">
                <el-form-item label="目标场站">
                  <el-select v-model="actualForm.farmCode" placeholder="选择场站" style="width: 100%">
                    <el-option v-for="f in farmList" :key="f.code" :label="f.name" :value="f.code" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="导入策略">
                  <el-radio-group v-model="actualForm.strategy">
                    <el-radio value="fill_only">仅补齐（跳过已有）</el-radio>
                    <el-radio value="overwrite">覆盖（更新已有）</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
          <el-alert type="info" :closable="false" show-icon class="format-hint">
            <template #title>CSV 格式要求</template>
            <p>CSV 第一行为列标题，必须包含 <strong>timestamp</strong> 和 <strong>wp_true</strong> 列。</p>
            <p>时间格式：YYYY-MM-DD HH:MM:SS。示例：<code>2026-04-28 00:15:00,12.5</code></p>
          </el-alert>
        </el-card>

        <!-- 上传区域 -->
        <el-card class="card-shell" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">上传文件</span>
              <span class="card-sub">最大 2GB，仅 CSV</span>
            </div>
          </template>
          <div class="upload-zone" :class="{ 'is-dragover': dragover === 'actual', 'is-disabled': !canUploadActual }" @dragover.prevent="dragover = 'actual'" @dragleave.prevent="dragover = ''" @drop.prevent="handleDrop($event, 'actual')" @click="triggerInput('actual')">
            <input ref="actualInputRef" type="file" accept=".csv" multiple style="display: none" @change="handleFileSelect($event, 'actual')" />
            <template v-if="actualFiles.length">
              <div v-for="(file, index) in actualFiles" :key="file.name + file.size + index" class="file-info">
                <el-icon size="32"><Document /></el-icon>
                <div class="file-detail">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ fmtSize(file.size) }}</span>
                </div>
                <el-button type="danger" size="small" circle @click.stop="removeSelectedFile('actual', index)"><el-icon><Close /></el-icon></el-button>
              </div>
            </template>
            <template v-else>
              <el-icon size="48" color="#909399"><UploadFilled /></el-icon>
              <p>拖拽 CSV 文件到此处，或点击选择</p>
            </template>
          </div>
          <div class="upload-actions">
            <el-button type="primary" :disabled="!canUploadActual" :loading="uploading" @click="doUpload('actual')">开始导入</el-button>
            <el-button v-if="uploading" @click="cancelUpload">取消</el-button>
          </div>
          <div v-if="uploading" class="progress-section">
            <el-progress :percentage="progress" :stroke-width="12" />
            <p class="progress-status">{{ statusText }}</p>
            <div class="progress-metrics">
              <div class="metric-item">
                <span class="metric-label">Stage</span>
                <span class="metric-value">{{ progressDetail.phase || '-' }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Job</span>
                <span class="metric-value mono">{{ progressDetail.jobId || '-' }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Upload</span>
                <span class="metric-value">{{ fmtSize(progressDetail.uploadedBytes || 0) }} / {{ progressDetail.totalBytes ? fmtSize(progressDetail.totalBytes) : '-' }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Rows</span>
                <span class="metric-value">{{ fmtNum(progressDetail.processedRows) }} / {{ fmtNum(progressDetail.totalRows) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Inserted</span>
                <span class="metric-value">{{ fmtNum(progressDetail.inserted) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Updated</span>
                <span class="metric-value">{{ fmtNum(progressDetail.updated) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Skipped</span>
                <span class="metric-value">{{ fmtNum(progressDetail.skipped) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Ingested</span>
                <span class="metric-value">{{ fmtNum(progressDetail.ingested) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Errors</span>
                <span class="metric-value" :class="{ 'has-error': progressDetail.errors > 0 }">{{ fmtNum(progressDetail.errors) }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ========== Tab 2: 气象预测数据 ========== -->
      <el-tab-pane label="气象预测数据" name="ecmwf">
        <el-card class="card-shell" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">配置</span>
            </div>
          </template>
          <el-form label-width="100px" label-position="left">
            <el-row :gutter="24">
              <el-col :span="8">
                <el-form-item label="目标场站">
                  <el-select v-model="ecmwfForm.farmCode" placeholder="选择场站" style="width: 100%">
                    <el-option v-for="f in farmList" :key="f.code" :label="f.name" :value="f.code" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="数据类型">
                  <el-select v-model="ecmwfForm.dataType" style="width: 100%">
                    <el-option label="超短期预测" value="train_pre_supershort" />
                    <el-option label="短期预测" value="train_pre_short" />
                    <el-option label="中期预测" value="train_pre_middle" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
          <el-alert type="info" :closable="false" show-icon class="format-hint">
            <template #title>CSV 格式说明</template>
            <p>上传气象预测宽表数据，CSV 列名需与目标表列名一致。</p>
            <p>必须包含 <strong>Timestamp</strong> 列，其余为气象特征列，如：<code>100u_23.8_103.2, 10u_23.8_103.2, 2t_23.8_103.2, ...</code></p>
            <p>数据将导入 <strong>{{ ecmwfForm.dataType === 'train_pre_supershort' ? '超短期预测' : ecmwfForm.dataType === 'train_pre_short' ? '短期预测' : '中期预测' }} ({{ ecmwfForm.dataType }}_{{ ecmwfForm.farmCode ? ecmwfForm.farmCode.toLowerCase() : '?' }})</strong> 表。</p>
          </el-alert>
        </el-card>

        <el-card class="card-shell" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">上传文件</span>
              <span class="card-sub">最大 2GB，仅 CSV</span>
            </div>
          </template>
          <div class="upload-zone" :class="{ 'is-dragover': dragover === 'ecmwf', 'is-disabled': !canUploadEcmwf }" @dragover.prevent="dragover = 'ecmwf'" @dragleave.prevent="dragover = ''" @drop.prevent="handleDrop($event, 'ecmwf')" @click="triggerInput('ecmwf')">
            <input ref="ecmwfInputRef" type="file" accept=".csv" multiple style="display: none" @change="handleFileSelect($event, 'ecmwf')" />
            <template v-if="ecmwfFiles.length">
              <div v-for="(file, index) in ecmwfFiles" :key="file.name + file.size + index" class="file-info">
                <el-icon size="32"><Document /></el-icon>
                <div class="file-detail">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ fmtSize(file.size) }}</span>
                </div>
                <el-button type="danger" size="small" circle @click.stop="removeSelectedFile('ecmwf', index)"><el-icon><Close /></el-icon></el-button>
              </div>
            </template>
            <template v-else>
              <el-icon size="48" color="#909399"><UploadFilled /></el-icon>
              <p>拖拽 ECMWF CSV 文件到此处，或点击选择</p>
            </template>
          </div>
          <div class="upload-actions">
            <el-button type="primary" :disabled="!canUploadEcmwf" :loading="uploading" @click="doUpload('ecmwf')">开始导入</el-button>
            <el-button v-if="uploading" @click="cancelUpload">取消</el-button>
          </div>
          <div v-if="uploading" class="progress-section">
            <el-progress :percentage="progress" :stroke-width="12" />
            <p class="progress-status">{{ statusText }}</p>
            <div class="progress-metrics">
              <div class="metric-item">
                <span class="metric-label">Stage</span>
                <span class="metric-value">{{ progressDetail.phase || '-' }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Job</span>
                <span class="metric-value mono">{{ progressDetail.jobId || '-' }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Upload</span>
                <span class="metric-value">{{ fmtSize(progressDetail.uploadedBytes || 0) }} / {{ progressDetail.totalBytes ? fmtSize(progressDetail.totalBytes) : '-' }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Rows</span>
                <span class="metric-value">{{ fmtNum(progressDetail.processedRows) }} / {{ fmtNum(progressDetail.totalRows) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Inserted</span>
                <span class="metric-value">{{ fmtNum(progressDetail.inserted) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Updated</span>
                <span class="metric-value">{{ fmtNum(progressDetail.updated) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Skipped</span>
                <span class="metric-value">{{ fmtNum(progressDetail.skipped) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Ingested</span>
                <span class="metric-value">{{ fmtNum(progressDetail.ingested) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">Errors</span>
                <span class="metric-value" :class="{ 'has-error': progressDetail.errors > 0 }">{{ fmtNum(progressDetail.errors) }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="E文本管道" name="etext">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">E文本自动处理管道</span>
              <el-button type="primary" size="small" :loading="etextTriggering" @click="doTriggerEtext">立即执行</el-button>
            </div>
          </template>

          <el-form label-width="120px" size="small">
            <el-form-item label="启用">
              <el-switch v-model="etextConfig.enabled" />
            </el-form-item>
            <el-form-item label="目标目录">
              <el-input v-model="etextConfig.incoming_dir" placeholder="E文本文件存放目录（如 D:\data\etext\incoming）" />
            </el-form-item>
            <el-form-item label="扫描时间">
              <el-row :gutter="8" align="middle">
                <el-col :span="6">
                  <el-input-number v-model="etextConfig.schedule_hour" :min="0" :max="23" controls-position="right" />
                </el-col>
                <el-col :span="1" style="text-align:center;color:#aaa">:</el-col>
                <el-col :span="17">
                  <el-select v-model="etextConfig.schedule_minutes" multiple placeholder="选择分钟" style="width:100%">
                    <el-option v-for="m in 60" :key="m - 1" :label="String(m - 1).padStart(2, '0') + ' 分'" :value="m - 1" />
                  </el-select>
                </el-col>
              </el-row>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="etextLoading" @click="saveEtextConfig">保存配置</el-button>
            </el-form-item>
          </el-form>

          <el-descriptions v-if="etextJob" :column="1" border size="small" style="margin-top:12px">
            <el-descriptions-item label="下次执行">{{ etextJob.next_run_time || '未调度' }}</el-descriptions-item>
            <el-descriptions-item label="调度规则">{{ etextJob.trigger }}</el-descriptions-item>
          </el-descriptions>
          <el-alert v-else type="info" :closable="false" show-icon style="margin-top:12px">
            <template #title>调度器未运行或任务未注册</template>
          </el-alert>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-card v-if="uploading && batchJobs.length" class="card-shell" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">批量导入进度</span>
          <span class="card-sub">{{ batchJobs.filter(j => j.done).length }} / {{ batchJobs.length }}</span>
        </div>
      </template>
      <el-table :data="batchJobs" style="width: 100%" size="small">
        <el-table-column prop="fileName" label="文件" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="进度" width="180">
          <template #default="scope">
            <el-progress :percentage="scope.row.progress || 0" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column label="行数" width="180">
          <template #default="scope">{{ fmtNum(scope.row.processedRows) }} / {{ fmtNum(scope.row.totalRows) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="220">
          <template #default="scope">
            <span class="st-ok">+{{ fmtNum(scope.row.inserted || scope.row.ingested || 0) }}</span>
            <span v-if="scope.row.updated" class="st-up">~{{ fmtNum(scope.row.updated) }}</span>
            <span v-if="scope.row.skipped" class="st-skip">⊘{{ fmtNum(scope.row.skipped) }}</span>
            <span v-if="scope.row.errors" class="st-err">!{{ fmtNum(scope.row.errors) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 最近一次结果 -->
    <el-card v-if="lastResult" class="card-shell" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">导入结果</span>
          <el-tag :type="lastResult.success ? 'success' : 'warning'" size="small">{{ lastResult.success ? '成功' : '部分失败' }}</el-tag>
        </div>
      </template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="类型">{{ lastResult.type === 'actual' ? '实测数据' : formatDataType(lastResult.dataType) }}</el-descriptions-item>
        <el-descriptions-item label="场站">{{ lastResult.farmCode }}</el-descriptions-item>
        <el-descriptions-item v-if="lastResult.strategy" label="策略">{{ lastResult.strategy === 'fill_only' ? '仅补齐' : '覆盖' }}</el-descriptions-item>
        <el-descriptions-item v-if="lastResult.inserted !== undefined" label="新增">{{ lastResult.inserted }} 条</el-descriptions-item>
        <el-descriptions-item v-if="lastResult.updated !== undefined" label="更新">{{ lastResult.updated }} 条</el-descriptions-item>
        <el-descriptions-item v-if="lastResult.skipped !== undefined" label="跳过">{{ lastResult.skipped }} 条</el-descriptions-item>
        <el-descriptions-item v-if="lastResult.ingested !== undefined" label="摄取">{{ lastResult.ingested }} 条</el-descriptions-item>
        <el-descriptions-item v-if="lastResult.errors" label="错误">{{ lastResult.errors }} 条</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 上传历史 -->
    <el-card v-if="history.length" class="card-shell" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">上传记录</span>
          <el-button type="info" size="small" @click="history = []">清空</el-button>
        </div>
      </template>
      <el-table :data="history" style="width: 100%" size="small">
        <el-table-column prop="time" label="时间" width="180" />
        <el-table-column label="类型" width="100">
          <template #default="scope">{{ scope.row.type === 'actual' ? '实测' : formatDataType(scope.row.dataType, true) }}</template>
        </el-table-column>
        <el-table-column prop="farmCode" label="场站" width="120" />
        <el-table-column prop="fileName" label="文件" min-width="180" show-overflow-tooltip />
        <el-table-column label="结果" min-width="160">
          <template #default="scope">
            <span class="st-ok">+{{ fmtNum(scope.row.inserted || scope.row.ingested || 0) }}</span>
            <span v-if="scope.row.updated" class="st-up">~{{ fmtNum(scope.row.updated) }}</span>
            <span v-if="scope.row.skipped" class="st-skip">⊘{{ fmtNum(scope.row.skipped) }}</span>
            <span v-if="scope.row.errors" class="st-err">!{{ fmtNum(scope.row.errors) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="scope"><el-tag :type="scope.row.ok ? 'success' : 'warning'" size="small">{{ scope.row.ok ? '成功' : '异常' }}</el-tag></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Close } from '@element-plus/icons-vue'
import { uploadActualPowerAsync, getImportJob, uploadFeatureCsv, getEtextPipelineConfig, updateEtextPipelineConfig, triggerEtextPipeline, getEtextTriggerStatus } from '../api/dataImportApi'
import farmService from '../utils/farmService'

const activeTab = ref('actual')
const farms = ref([])
const uploading = ref(false)
const progress = ref(0)
const statusText = ref('')
const progressDetail = ref({})
const lastResult = ref(null)
const history = ref([])
const dragover = ref('')
const actualInputRef = ref(null)
const ecmwfInputRef = ref(null)
let abortCtrl = null

const actualForm = ref({ farmCode: '', strategy: 'fill_only' })
const ecmwfForm = ref({ farmCode: '', dataType: 'train_pre_short' })

// E text pipeline config
const etextConfig = ref({ incoming_dir: '', schedule_hour: 8, schedule_minutes: [40, 45, 50, 55], enabled: true })
const etextJob = ref(null)
const etextLoading = ref(false)
const etextTriggering = ref(false)

const DATA_TYPE_LABELS = {
  train_pre_supershort: { full: '气象预测-超短期', short: '气象-超短' },
  train_pre_short: { full: '气象预测-短期', short: '气象-短期' },
  train_pre_middle: { full: '气象预测-中期', short: '气象-中期' },
}
function formatDataType(dataType, brief = false) {
  const key = brief ? 'short' : 'full'
  return DATA_TYPE_LABELS[dataType]?.[key] ?? '气象预测'
}
const actualFiles = ref([])
const ecmwfFiles = ref([])
const batchJobs = ref([])

const farmList = computed(() => farms.value.filter(f => f.code))

const canUploadActual = computed(() => actualForm.value.farmCode && actualFiles.value.length > 0 && !uploading.value)
const canUploadEcmwf = computed(() => ecmwfForm.value.farmCode && ecmwfFiles.value.length > 0 && !uploading.value)

function fmtSize(b) {
  if (b < 1024) return b + ' B'
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB'
  if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB'
  return (b / 1073741824).toFixed(2) + ' GB'
}

function fmtNum(value) {
  if (value === undefined || value === null || value === '') return '-'
  const num = Number(value)
  if (!Number.isFinite(num)) return String(value)
  return num.toLocaleString()
}

function toCount(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function resetState() {
  uploading.value = false
  progress.value = 0
  statusText.value = ''
  progressDetail.value = {}
  batchJobs.value = []
}

function triggerInput(tab) {
  if (uploading.value) return
  if (tab === 'actual') actualInputRef.value?.click()
  else ecmwfInputRef.value?.click()
}

function handleFileSelect(e, tab) {
  setSelectedFiles(tab, Array.from(e.target.files || []))
  e.target.value = ''
}

function handleDrop(e, tab) {
  dragover.value = ''
  setSelectedFiles(tab, Array.from(e.dataTransfer?.files || []))
}

function setSelectedFiles(tab, files) {
  const validFiles = files.filter((file) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      ElMessage.warning(`${file.name} is not a CSV file`)
      return false
    }
    if (file.size > 2147483648) {
      ElMessage.error(`${file.name} exceeds 2GB`)
      return false
    }
    return true
  })
  if (tab === 'actual') actualFiles.value = validFiles
  else ecmwfFiles.value = validFiles
}

function removeSelectedFile(tab, index) {
  if (tab === 'actual') actualFiles.value.splice(index, 1)
  else ecmwfFiles.value.splice(index, 1)
}

function cancelUpload() {
  if (abortCtrl) abortCtrl.abort()
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function doUpload(tab) {
  await doBatchUpload(tab)
}

function refreshBatchSummary() {
  if (!batchJobs.value.length) return
  const totalProgress = batchJobs.value.reduce((sum, job) => sum + toCount(job.progress), 0)
  const doneCount = batchJobs.value.filter(job => job.done).length
  progress.value = Math.round(totalProgress / batchJobs.value.length)
  statusText.value = `Batch importing ${doneCount} / ${batchJobs.value.length} files`
  progressDetail.value = {
    phase: doneCount === batchJobs.value.length ? 'Done' : 'Batch',
    processedRows: batchJobs.value.reduce((sum, job) => sum + toCount(job.processedRows), 0),
    totalRows: batchJobs.value.reduce((sum, job) => sum + toCount(job.totalRows), 0),
    inserted: batchJobs.value.reduce((sum, job) => sum + toCount(job.inserted), 0),
    updated: batchJobs.value.reduce((sum, job) => sum + toCount(job.updated), 0),
    skipped: batchJobs.value.reduce((sum, job) => sum + toCount(job.skipped), 0),
    ingested: batchJobs.value.reduce((sum, job) => sum + toCount(job.ingested), 0),
    errors: batchJobs.value.reduce((sum, job) => sum + toCount(job.errors), 0)
  }
}

async function pollBatchJob(entry, signal) {
  let pollFailures = 0
  for (;;) {
    await wait(1500)
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')

    let res
    try {
      res = await getImportJob(entry.jobId, { signal })
      pollFailures = 0
    } catch (error) {
      if (signal?.aborted) throw error
      pollFailures += 1
      entry.status = `Retry ${pollFailures}`
      refreshBatchSummary()
      if (pollFailures >= 30) throw new Error('Status polling timed out repeatedly')
      continue
    }

    const job = res.data
    entry.status = job.status === 'queued' ? 'Queued' : job.status === 'done' ? 'Done' : 'Processing'
    entry.progress = job.status === 'done' ? 100 : Math.max(1, Math.min(job.progress || 0, 99))
    entry.processedRows = toCount(job.processed_rows)
    entry.totalRows = toCount(job.total_rows)
    entry.inserted = toCount(job.inserted_count)
    entry.updated = toCount(job.updated_count)
    entry.skipped = toCount(job.skipped_count)
    entry.ingested = toCount(job.ingested_count)
    entry.errors = toCount(job.error_count)
    refreshBatchSummary()

    if (job.status === 'done') return job
    if (job.status === 'failed') throw new Error(job.message || 'Import failed')
  }
}

function buildResultFromJob(tab, job) {
  if (tab === 'actual') {
    return {
      success: job.status === 'done' && toCount(job.error_count) === 0,
      type: 'actual',
      farmCode: actualForm.value.farmCode,
      strategy: actualForm.value.strategy,
      inserted: toCount(job.inserted_count),
      updated: toCount(job.updated_count),
      skipped: toCount(job.skipped_count),
      processed: toCount(job.processed_rows),
      errors: toCount(job.error_count)
    }
  }
  return {
    success: job.status === 'done' && toCount(job.error_count) === 0,
    type: 'ecmwf',
    farmCode: ecmwfForm.value.farmCode,
    ingested: toCount(job.ingested_count),
    processed: toCount(job.processed_rows),
    errors: toCount(job.error_count)
  }
}

function pushImportHistory(tab, file, result) {
  history.value.unshift({
    time: new Date().toLocaleString(),
    type: result.type,
    farmCode: result.farmCode,
    fileName: file?.name,
    inserted: result.inserted,
    updated: result.updated,
    skipped: result.skipped,
    ingested: result.ingested,
    processed: result.processed,
    errors: result.errors,
    ok: result.success
  })
}

async function uploadOneFile(tab, file, entry, signal) {
  entry.status = 'Uploading'
  const onUploadProgress = (e) => {
    if (!e.total) return
    entry.progress = Math.min(Math.round((e.loaded / e.total) * 50), 50)
    entry.uploadedBytes = e.loaded
    entry.totalBytes = e.total
    refreshBatchSummary()
  }

  if (tab === 'actual') {
    const res = await uploadActualPowerAsync({
      file,
      farmCode: actualForm.value.farmCode,
      strategy: actualForm.value.strategy,
      onUploadProgress,
      signal
    })
    entry.jobId = res.data.job_id
    entry.status = 'Queued'
    entry.progress = Math.max(entry.progress || 0, 50)
    refreshBatchSummary()
    const doneJob = await pollBatchJob(entry, signal)
    const result = buildResultFromJob(tab, doneJob)
    entry.done = true
    entry.ok = result.success
    entry.status = result.success ? 'Done' : 'Warning'
    refreshBatchSummary()
    pushImportHistory(tab, file, result)
    return result
  }

  // ECMWF 页签通过 /api/upload_feature_csv 同步上传。
  const tableName = `${ecmwfForm.value.dataType}_${ecmwfForm.value.farmCode.toLowerCase()}`
  const res = await uploadFeatureCsv({
    file,
    farmCode: ecmwfForm.value.farmCode,
    tableName,
    onUploadProgress,
    signal
  })
  const data = res.data
  const hasErrors = data.error_count > 0 || data.errors?.length > 0
  entry.progress = 100
  entry.done = true
  entry.ok = !hasErrors
  entry.status = hasErrors ? 'Warning' : 'Done'
  entry.inserted = data.inserted_count || 0
  entry.updated = data.updated_count || 0
  entry.errors = data.error_count || (data.errors?.length) || 0
  entry.processedRows = (data.inserted_count || 0) + (data.updated_count || 0) + (data.error_count || 0)
  refreshBatchSummary()

  const result = {
    success: !hasErrors,
    type: 'ecmwf',
    farmCode: ecmwfForm.value.farmCode,
    inserted: data.inserted_count || 0,
    updated: data.updated_count || 0,
    errors: entry.errors,
    processed: entry.processedRows
  }
  pushImportHistory(tab, file, result)
  return result
}

async function runLimited(tasks, limit) {
  const results = []
  let nextIndex = 0
  async function worker() {
    while (nextIndex < tasks.length) {
      const current = nextIndex
      nextIndex += 1
      results[current] = await tasks[current]()
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker))
  return results
}

async function doBatchUpload(tab) {
  const files = tab === 'actual' ? actualFiles.value : ecmwfFiles.value
  if (!files.length) return

  uploading.value = true
  progress.value = 0
  statusText.value = 'Uploading files...'
  progressDetail.value = { phase: 'Batch' }
  lastResult.value = null
  abortCtrl = new AbortController()
  batchJobs.value = files.map((file) => ({
    fileName: file.name,
    status: 'Waiting',
    progress: 0,
    processedRows: 0,
    totalRows: 0,
    inserted: 0,
    updated: 0,
    skipped: 0,
    ingested: 0,
    errors: 0,
    done: false,
    ok: false
  }))

  try {
    const tasks = files.map((file, index) => () => uploadOneFile(tab, file, batchJobs.value[index], abortCtrl.signal))
    const results = await runLimited(tasks, 2)
    const errors = results.reduce((sum, result) => sum + toCount(result.errors), 0)
    const successCount = results.filter(result => result.success).length
    const summary = {
      success: errors === 0,
      type: tab,
      farmCode: tab === 'actual' ? actualForm.value.farmCode : ecmwfForm.value.farmCode,
      dataType: tab === 'ecmwf' ? ecmwfForm.value.dataType : undefined,
      inserted: results.reduce((sum, result) => sum + toCount(result.inserted), 0),
      updated: results.reduce((sum, result) => sum + toCount(result.updated), 0),
      skipped: results.reduce((sum, result) => sum + toCount(result.skipped), 0),
      ingested: results.reduce((sum, result) => sum + toCount(result.ingested), 0),
      processed: results.reduce((sum, result) => sum + toCount(result.processed), 0),
      errors
    }
    progress.value = 100
    statusText.value = `Batch completed ${successCount} / ${results.length} files`
    lastResult.value = summary
    if (summary.success) ElMessage.success(`Batch import completed: ${results.length} files`)
    else ElMessage.warning(`Batch import completed with ${errors} errors`)
    if (tab === 'actual') actualFiles.value = []
    else ecmwfFiles.value = []
  } catch (err) {
    if (err.name === 'CanceledError' || err.name === 'AbortError') ElMessage.info('Canceled')
    else ElMessage.error(err.response?.data?.error || err.message || 'Upload failed')
  } finally {
    uploading.value = false
    abortCtrl = null
  }
}

async function loadEtextConfig() {
  etextLoading.value = true
  try {
    const res = await getEtextPipelineConfig()
    etextConfig.value = res.data.config
    etextJob.value = res.data.job
  } catch { /* pipeline not configured yet */ }
  etextLoading.value = false
}

async function saveEtextConfig() {
  etextLoading.value = true
  try {
    const res = await updateEtextPipelineConfig(etextConfig.value)
    etextConfig.value = res.data.config
    etextJob.value = null
    await loadEtextConfig()
    ElMessage.success('E文本管道配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  }
  etextLoading.value = false
}

async function doTriggerEtext() {
  etextTriggering.value = true
  try {
    const startRes = await triggerEtextPipeline()
    const jobId = startRes.data.job_id
    ElMessage.info('已提交，正在后台处理...')

    let pollErrors = 0
    for (let i = 0; i < 120; i++) {
      await new Promise(r => setTimeout(r, 3000))
      let pollRes
      try {
        pollRes = await getEtextTriggerStatus(jobId)
        pollErrors = 0
      } catch (pollErr) {
        pollErrors++
        if (pollErrors >= 5) throw pollErr
        continue
      }
      const d = pollRes.data
      if (d.status === 'done') {
        if (d.message) {
          ElMessage.warning(d.message)
        } else {
          ElMessage.success(`处理完成: ${d.tables} 表, 新增 ${d.inserted}, 更新 ${d.updated}`)
        }
        await loadEtextConfig()
        etextTriggering.value = false
        return
      }
      if (d.status === 'failed') {
        ElMessage.error('执行失败: ' + (d.error || '未知错误'))
        etextTriggering.value = false
        return
      }
    }
    ElMessage.warning('处理超时，请稍后查看结果')
  } catch (e) {
    ElMessage.error('执行失败: ' + (e.response?.data?.error || e.message))
  }
  etextTriggering.value = false
}

onMounted(async () => {
  await farmService.loadAvailableFarms(true)
  farms.value = farmService.getAvailableFarms()
  const first = farms.value.find(f => f.code)
  if (first && !actualForm.value.farmCode) {
    actualForm.value.farmCode = first.code
  }
  if (first && !ecmwfForm.value.farmCode) {
    ecmwfForm.value.farmCode = first.code
  }
  loadEtextConfig()
})
</script>

<style scoped>
.page-shell { position: relative; padding: 24px; min-height: 100vh; }
.gradient-background { position: fixed; inset: 0; background: linear-gradient(135deg, #0c1929 0%, #132a44 50%, #0e1f38 100%); z-index: -1; }
.page-header { margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 600; color: #e0e6ed; margin: 0 0 4px; }
.page-description { color: #8899aa; font-size: 13px; margin: 0; }

.card-shell { margin-bottom: 16px; border-radius: 10px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); color: #d0d7de; }
.card-shell :deep(.el-card__header) { border-bottom: 1px solid rgba(255,255,255,0.06); padding: 14px 20px; }
.card-shell :deep(.el-card__body) { padding: 20px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 15px; font-weight: 600; color: #e0e6ed; }
.card-sub { font-size: 12px; color: #8899aa; }

.main-tabs :deep(.el-tabs__item) { color: #8899aa; font-size: 15px; }
.main-tabs :deep(.el-tabs__item.is-active) { color: #409eff; }
.main-tabs :deep(.el-tabs__nav-wrap::after) { background: rgba(255,255,255,0.08); }

.format-hint { margin-top: 12px; }
.format-hint p { margin: 4px 0; font-size: 13px; line-height: 1.6; }
.format-hint code { background: rgba(255,255,255,0.1); padding: 1px 5px; border-radius: 3px; font-size: 12px; }

.upload-zone { border: 2px dashed rgba(255,255,255,0.15); border-radius: 8px; padding: 36px 20px; text-align: center; cursor: pointer; transition: all 0.2s; color: #8899aa; }
.upload-zone:hover, .upload-zone.is-dragover { border-color: #409eff; background: rgba(64,158,255,0.05); }
.upload-zone.is-disabled { opacity: 0.5; cursor: not-allowed; }

.file-info { display: flex; align-items: center; justify-content: center; gap: 12px; color: #d0d7de; }
.file-detail { text-align: left; }
.file-name { display: block; font-size: 14px; font-weight: 500; }
.file-size { display: block; font-size: 12px; color: #8899aa; }

.upload-actions { margin-top: 16px; display: flex; gap: 10px; }
.progress-section { margin-top: 16px; }
.progress-status { text-align: center; font-size: 13px; color: #8899aa; margin-top: 6px; }
.progress-metrics { margin-top: 12px; display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 8px; }
.metric-item { min-height: 48px; padding: 8px 10px; border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; background: rgba(255,255,255,0.04); overflow: hidden; }
.metric-label { display: block; font-size: 11px; line-height: 16px; color: #8899aa; }
.metric-value { display: block; margin-top: 2px; font-size: 14px; line-height: 20px; color: #e0e6ed; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.metric-value.mono { font-family: Consolas, Monaco, monospace; font-size: 12px; }
.metric-value.has-error { color: #f56c6c; }

.st-ok { color: #67c23a; margin-right: 8px; font-size: 12px; font-weight: 500; }
.st-up { color: #409eff; margin-right: 8px; font-size: 12px; }
.st-skip { color: #909399; margin-right: 8px; font-size: 12px; }
.st-err { color: #f56c6c; font-size: 12px; }

:deep(.el-form-item__label) { color: #c0c6cc; }
:deep(.el-radio__label) { color: #c0c6cc; }
:deep(.el-descriptions__label) { color: #8899aa !important; }
</style>
