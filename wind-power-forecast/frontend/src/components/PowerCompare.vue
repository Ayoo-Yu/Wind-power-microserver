<template>
  <DigitalPage>
    <DigitalHero
      eyebrow="DATA INSIGHT CENTER"
      title="数据可视化与下载"
      subtitle="多维对比预测与实测，洞察模型表现与上报状态"
      :metrics="heroMetrics"
    >
      <template #meta>
        <div class="digital-hero__meta">
          <span class="digital-status-chip">当前场站：{{ currentWindFarmDisplay || '未选择' }}</span>
          <el-button 
            icon="Refresh" 
            circle 
            class="refresh-button"
            @click="refreshPage"
            :loading="loading"
          />
        </div>
      </template>
    </DigitalHero>

    <el-card
      :class="['operational-upload-card', 'glass-panel', { 'panel--pulse': panelPulse.upload }]"
      shadow="never"
    >
      <template #header>
        <div class="card-header">
          <div class="card-header-title">
            <span class="icon-bubble">
              <el-icon><UploadFilled /></el-icon>
            </span>
            <div class="card-header-copy">
              <span class="card-title">运营数据上传</span>
              <span class="card-subtitle">将 CSV 文件直接导入当前场站的数据域</span>
            </div>
          </div>
          <el-tag type="info" effect="dark" size="small">当前场站：{{ currentWindFarmDisplay }}</el-tag>
        </div>
      </template>
      <div class="operational-upload-body">
        <el-row class="operational-upload-grid" :gutter="24">
          <el-col :xs="24" :lg="14">
            <div class="upload-panel">
              <div class="upload-steps">
                <span class="tip-badge">操作提示</span>
                <ul>
                  <li>选择上传的数据类型，并在右侧查看字段要求</li>
                  <li>拖拽或点击导入 CSV 文件，列名需与字段保持一致</li>
                  <li>提交后系统将自动附带当前风场标识</li>
                </ul>
              </div>

              <el-form label-position="top" class="operational-form">
                <el-form-item label="数据类型">
                  <el-select
                    v-model="selectedOperationalTable"
                    placeholder="选择要上传的数据表"
                    clearable
                    filterable
                    :loading="operationalSchemaLoading && !operationalSchema"
                    @change="handleOperationalTableChange"
                  >
                    <el-option
                      v-for="table in operationalTables"
                      :key="table"
                      :label="operationalTableDescriptions[table] || table"
                      :value="table"
                    />
                  </el-select>
                </el-form-item>
              </el-form>

              <p class="table-description">{{ operationalTableDescription }}</p>

              <div class="upload-drop-wrapper">
                <el-upload
                  class="operational-upload-dropzone"
                  drag
                  :limit="1"
                  :auto-upload="false"
                  :file-list="operationalUpload.fileList"
                  :on-change="handleOperationalFileChange"
                  :on-remove="handleOperationalFileRemove"
                  accept=".csv"
                >
                  <div class="dropzone-inner">
                    <el-icon class="dropzone-icon"><UploadFilled /></el-icon>
                    <div class="dropzone-title">拖拽或点击上传 CSV 文件</div>
                    <p class="dropzone-desc">系统将自动绑定「{{ currentWindFarmDisplay }}」</p>
                  </div>
                </el-upload>
              </div>

              <transition name="fade-slide">
                <div v-if="operationalUpload.file" class="selected-file-chip">
                  <span class="file-icon">
                    <el-icon><Document /></el-icon>
                  </span>
                  <div class="file-meta">
                    <span class="file-name">{{ operationalUpload.file.name }}</span>
                    <span class="file-size">{{ formatFileSize(operationalUpload.file.size) }}</span>
                  </div>
                  <el-button type="text" size="small" @click="resetOperationalUploadState({ clearMessages: true })">更换文件</el-button>
                </div>
              </transition>

              <div class="operational-upload-actions">
                <el-button type="primary" size="large" :loading="operationalUpload.uploading" @click="uploadOperationalDataset">上传数据</el-button>
                <el-button size="large" @click="resetOperationalUploadState({ clearMessages: true })">清空</el-button>
              </div>

              <transition name="fade-slide">
                <el-alert
                  v-if="operationalUploadResult"
                  type="success"
                  :title="operationalUploadResult.message || '上传成功'"
                  show-icon
                  closable
                  @close="operationalUploadResult = null"
                />
              </transition>
              <transition name="fade-slide">
                <el-alert
                  v-if="operationalUploadError"
                  type="error"
                  :title="operationalUploadError"
                  show-icon
                  closable
                  @close="operationalUploadError = null"
                />
              </transition>
            </div>
          </el-col>
          <el-col :xs="24" :lg="10">
            <div :class="['schema-panel', { 'panel--pulse': panelPulse.schema }]">
              <div class="schema-panel-header">
                <h3>字段要求</h3>
                <span>确保 CSV 列与字段类型匹配</span>
              </div>
              <div class="schema-panel-body">
                <div v-if="operationalSchemaLoading" class="schema-loading">
                  <el-skeleton :rows="6" animated />
                </div>
                <el-table
                  v-else-if="operationalSchemaRows.length"
                  :data="operationalSchemaRows"
                  class="schema-table"
                  border
                  size="small"
                >
                  <el-table-column prop="name" label="字段名" width="140" />
                  <el-table-column label="字段说明">
                    <template #default="{ row }">
                      <div class="schema-info">
                        <span class="schema-type">{{ row.meta?.type || '未知类型' }}</span>
                        <span v-if="row.meta?.comment" class="schema-comment">{{ row.meta.comment }}</span>
                        <span class="schema-required">
                          {{ row.meta?.nullable ? '可为空' : '必填' }}
                          <span v-if="row.meta?.primary_key" class="schema-primary">主键</span>
                        </span>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-else description="请选择数据类型以查看字段信息" />
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <div class="config-panel">
      <el-card
        :class="['merged-config-card', 'glass-panel', { 'panel--pulse': panelPulse.config }]"
      > 
        <!-- Row 1: Time Picker, Query Button, Download Buttons -->
        <div class="config-row config-row-1">
          <div class="time-picker-wrapper-outer">
            <span class="label">选择时间范围：</span>
            <el-date-picker
              v-model="timeRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              value-format="YYYY-MM-DD HH:mm:ss"
              class="time-range-picker-element" 
            />
          </div>
          <el-button-group class="quick-time-select-buttons" style="margin-left: 10px; margin-right: 10px;">
            <el-button type="info" plain size="small" @click="setQuickTimeRange('today')" :disabled="isQuickTimeSwitching">今日</el-button>
            <el-button type="info" plain size="small" @click="setQuickTimeRange('3d')" :disabled="isQuickTimeSwitching">近三天</el-button>
            <el-button type="info" plain size="small" @click="setQuickTimeRange('1w')" :disabled="isQuickTimeSwitching">近一周</el-button>
            <el-button type="info" plain size="small" @click="setQuickTimeRange('1m')" :disabled="isQuickTimeSwitching">近一个月</el-button>
          </el-button-group>
          <el-button 
            type="primary" 
            @click="fetchComparisonData"
            :loading="loading"
            class="query-button"
          >
            查询数据
          </el-button>
          <el-button-group class="download-buttons download-buttons-row1">
            <el-button 
              type="success" 
              @click="downloadCSV"
              :disabled="!exportData.comparison"
            >
              数据下载
            </el-button>
            <el-button 
              type="success" 
              @click="downloadMetricsCSV"
              :disabled="!exportData.metrics"
            >
              指标下载
            </el-button>
            <el-button 
              type="success" 
              @click="downloadSVG"
              :disabled="!chartData"
            >
              功率图下载
            </el-button>
            <el-button 
              type="success" 
              @click="downloadMetricSVG"
              :disabled="!dailyMetrics"
            >
              指标图下载
            </el-button>
            <el-button
              type="success"
              @click="showDailyMetricsAnalysis = !showDailyMetricsAnalysis"
            >
              {{ showDailyMetricsAnalysis ? '隐藏' : '显示' }}每日指标
            </el-button>
            <el-button
              type="success"
              @click="showQualificationRateAnalysis = !showQualificationRateAnalysis"
              :disabled="!qualificationRates || Object.keys(qualificationRates).length === 0"
            >
              {{ showQualificationRateAnalysis ? '隐藏' : '显示' }}合格率分析
            </el-button>
          </el-button-group>
        </div>

        <!-- Row 2: Type Select -->
        <div class="config-row config-row-2">
          <div class="type-checkbox-group type-checkbox-group-row2">
            <span class="label">选择展示类型：</span>
            <el-checkbox-group v-model="selectedTypes" class="type-selector-group">
              <el-checkbox label="实测值" />
              <el-checkbox label="超短期预测" />
              <el-checkbox label="短期预测" />
              <el-checkbox label="中期预测" />
              <el-checkbox label="短期风速预测" />
              <el-checkbox label="中期风速预测" />
            </el-checkbox-group>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 图表展示区域 -->
    <div
      v-if="chartData"
      :class="['chart-container', { 'panel--pulse': panelPulse.chart }]"
    >
      <div class="chart-wrapper" :key="chartKey">
        <canvas ref="chartCanvas" style="height: 70vh !important;"></canvas>
      </div>
    </div>

    <!-- 每日指标区域 -->
    <div class="daily-metrics-container" v-if="showDailyMetricsAnalysis && dailyMetrics">
      <el-card
        :class="['metrics-card', 'glass-panel', { 'panel--pulse': panelPulse.metrics }]"
      >
        <div class="metrics-header">
          <h3>每日评估指标</h3>
          <div class="metric-buttons">
            <el-radio-group v-model="currentMetric" @change="handleMetricChange">
              <el-radio-button label="acc" :disabled="isMetricButtonCooling">ACC (%)</el-radio-button>
              <el-radio-button label="mae" :disabled="isMetricButtonCooling">MAE (MW)</el-radio-button>
              <el-radio-button label="mse" :disabled="isMetricButtonCooling">MSE (MW²)</el-radio-button>
              <el-radio-button label="rmse" :disabled="isMetricButtonCooling">RMSE (MW)</el-radio-button>
              <el-radio-button label="k" :disabled="isMetricButtonCooling">K值</el-radio-button>
              <el-radio-button label="pe" :disabled="isMetricButtonCooling">Pe (MW)</el-radio-button>
            </el-radio-group>
          </div>
        </div>
        <div class="metrics-chart-wrapper">
          <canvas 
            ref="metricChart" 
            style="width: 100%; height: 100%; display: block;"
          ></canvas>
        </div>
      </el-card>
    </div>

    <!-- 数据提示区域 -->
    <div class="empty-data-container" v-if="!chartData">
      <el-card class="empty-data-card glass-panel">
        <div class="empty-data-content">
          <el-icon class="empty-icon"><PieChart /></el-icon>
          <h3>暂无数据</h3>
          <p class="empty-text">请选择时间范围并点击查询数据按钮</p>
        </div>
      </el-card>
    </div>

    <!-- 合格率分析区域 -->
    <div class="qualification-container" v-if="showQualificationRateAnalysis && qualificationRates && Object.keys(qualificationRates).length > 0">
      <el-card
        :class="['qualification-card', 'glass-panel', { 'panel--pulse': panelPulse.qualification }]"
      >
        <div class="qualification-header">
          <h3>预测合格率分析</h3>
        </div>
        <div class="qualification-content">
          <div v-for="(data, type) in qualificationRates" :key="type" class="qualification-item">
            <div class="qualification-type">
              <span class="type-label">{{ type }}</span>
              <span class="threshold-label">合格标准: K值 > {{ data.threshold }}</span>
            </div>
            <el-progress 
              :percentage="data.rate" 
              :color="getQualificationColor(data.rate)"
              :format="percent => `${percent.toFixed(1)}%`"
              :stroke-width="18"
            />
            <div class="qualification-details">
              <span>合格天数: {{ data.qualifiedDays }}/{{ data.totalDays }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 加载状态 -->
    <LoadingIndicator 
      :visible="loading" 
      message="数据加载中..."
    />
  </DigitalPage>
</template>

<script>
import { Chart, CategoryScale, LinearScale, LineElement, PointElement, Title, Tooltip, Legend, LineController } from 'chart.js'
import zoomPlugin from 'chartjs-plugin-zoom';
import axiosInstance from '../api/axios'
import { ElMessage } from 'element-plus'
import { useWindFarmStore } from '@/store/windFarm'
import { UploadFilled, Document } from '@element-plus/icons-vue'
import DigitalPage from './common/DigitalPage.vue'
import DigitalHero from './common/DigitalHero.vue'

Chart.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  LineController,
  zoomPlugin // Register the zoom plugin
)

// Define Y-axis constants at a higher scope
const YAXIS_POWER = 'yPower';
const YAXIS_WINDSPEED = 'yWindSpeed';

const windFarmStore = useWindFarmStore();

export default {
  name: 'PowerCompare',
  components: {
    UploadFilled,
    Document,
    DigitalPage,
    DigitalHero,
  },
  data() {
    return {
      timeRange: [],
      selectedTypes: ['实测值', '超短期预测', '短期预测', '中期预测','短期风速预测','中期风速预测'],
      chartData: null,
      chartInstance: null,
      loading: false,
      wfcapacity: 453.5,
      currentMetric: 'acc',
      dailyMetrics: null,
      metricChart: null,
      colors: {
        '实测值': '#FF6B6B',
        '超短期预测': '#4ECDC4',
        '短期预测': '#45B7D1',
        '中期预测': '#96CEB4'
      },
      windSpeedColors: {
        '短期风速': '#FFD700',
        '中期风速': '#DA70D6',
      },
      exportData: {
        comparison: null,
        metrics: null
      },
      operationalTables: [],
      operationalTableDescriptions: {},
      operationalSchema: null,
      selectedOperationalTable: '',
      operationalUpload: {
        file: null,
        fileList: [],
        uploading: false,
      },
      operationalSchemaLoading: false,
      operationalUploadResult: null,
      operationalUploadError: null,
      qualifiedThresholds: {
        '超短期预测': 0.65,
        '短期预测': 0.6,
        '中期预测': 0.4
      },
      qualificationRates: null,
      showDailyMetricsAnalysis: false,
      showQualificationRateAnalysis: false,
      selectedSupershortHorizon: ['average'],
      supershortHorizons: [
        { value: 'average', label: '平均值' },
        ...Array.from({ length: 16 }, (_, i) => ({
          value: `wp_pred${i + 2}`,
          label: `P${i + 1}`,
        })),
      ],
      chartKey: 0,
      isProcessingChart: false,
      isQuickTimeSwitching: false, // Flag for quick time range button cooldown
      isUpdatingMetricChart: false, // Added for updateMetricChart lock
      isMetricButtonCooling: false, // 指标按钮的冷却状态标志
      panelPulse: {
        upload: false,
        schema: false,
        config: false,
        chart: false,
        metrics: false,
        qualification: false,
      },
      panelPulseTimers: {},
    }
  },
  computed: {
    selectedWindFarm() {
      return windFarmStore.selectedWindFarm.value;
    },
    currentWindFarmRecord() {
      return windFarmStore.findWindFarmByCode(this.selectedWindFarm);
    },
    currentWindFarmDisplay() {
      const record = this.currentWindFarmRecord;
      if (record) {
        return record.farm_name || record.farm_code || this.selectedWindFarm;
      }
      return this.selectedWindFarm;
    },
    heroMetrics() {
      const compareReady = !!this.chartData
      const uploadReady = !!(this.operationalUploadResult || this.operationalUpload.file)

      return [
        {
          id: 'timeRange',
          label: '时间范围',
          value: this.timeRangeFormatted,
          meta: '当前查询范围',
        },
        {
          id: 'types',
          label: '展示类型',
          value: this.selectedTypes.length,
          meta: '预测/实测曲线',
        },
        {
          id: 'compare',
          label: '对比数据',
          value: compareReady ? 'READY' : 'PENDING',
          meta: compareReady ? '图表已生成' : '等待查询',
        },
        {
          id: 'uploads',
          label: '运营数据上传',
          value: uploadReady ? '配置中' : '未上传',
          meta: this.selectedOperationalTable || '未选择表',
        },
      ]
    },
    timeRangeFormatted() {
      if (!Array.isArray(this.timeRange) || this.timeRange.length !== 2 || !this.timeRange[0] || !this.timeRange[1]) {
        return '未选择'
      }
      return `${this.timeRange[0].slice(5, 16)} ~ ${this.timeRange[1].slice(5, 16)}`
    },
    operationalTableDescription() {
      if (!this.selectedOperationalTable) {
        return '请选择要上传的运营数据类型';
      }
      return this.operationalTableDescriptions[this.selectedOperationalTable] || this.selectedOperationalTable;
    },
    operationalSchemaRows() {
      if (!this.operationalSchema) {
        return [];
      }
      return Object.entries(this.operationalSchema).map(([name, meta]) => ({
        name,
        meta,
      }));
    }
  },
  mounted() {
    const today = new Date();
    const year = today.getFullYear();
    const month = (today.getMonth() + 1).toString().padStart(2, '0');
    const day = today.getDate().toString().padStart(2, '0');
    
    this.timeRange = [
      `${year}-${month}-${day} 00:00:00`,
      `${year}-${month}-${day} 23:59:59`,
    ];
    this.fetchOperationalTables();
    this.fetchComparisonData();
  },
  methods: {
    triggerPanelPulse(key, duration = 900) {
      if (!this.panelPulse || !Object.prototype.hasOwnProperty.call(this.panelPulse, key)) {
        return;
      }
      if (!this.panelPulseTimers) {
        this.panelPulseTimers = {};
      }
      if (this.panelPulseTimers[key]) {
        clearTimeout(this.panelPulseTimers[key]);
      }
      this.panelPulse[key] = true;
      this.panelPulseTimers[key] = setTimeout(() => {
        this.panelPulse[key] = false;
        this.panelPulseTimers[key] = null;
      }, duration);
    },
    clearPanelPulse(key) {
      if (!this.panelPulse || !Object.prototype.hasOwnProperty.call(this.panelPulse, key)) {
        return;
      }
      if (this.panelPulseTimers && this.panelPulseTimers[key]) {
        clearTimeout(this.panelPulseTimers[key]);
        this.panelPulseTimers[key] = null;
      }
      this.panelPulse[key] = false;
    },
    clearAllPanelPulses() {
      if (this.panelPulseTimers) {
        Object.keys(this.panelPulseTimers).forEach(key => {
          if (this.panelPulseTimers[key]) {
            clearTimeout(this.panelPulseTimers[key]);
            this.panelPulseTimers[key] = null;
          }
        });
      }
      if (this.panelPulse) {
        Object.keys(this.panelPulse).forEach(key => {
          this.panelPulse[key] = false;
        });
      }
    },
    async handleWindFarmSelectionChange() {
      this.clearAllPanelPulses();
      ElMessage.info(`已切换到场站：${this.currentWindFarmDisplay}`);
      this.chartData = null;
      this.dailyMetrics = null;
      this.exportData = { comparison: null, metrics: null };
      this.qualificationRates = null;
      this.showDailyMetricsAnalysis = false;
      this.showQualificationRateAnalysis = false;
      this.chartKey += 1;
      this.resetOperationalUploadState({ clearMessages: true });
      this.operationalSchema = null;
      await this.fetchOperationalTables();
      if (this.timeRange && this.timeRange.length === 2) {
        await this.fetchComparisonData();
      }
    },
    refreshPage() {
      window.location.reload();
    },
    
    // 格式化K值为三位有效数字
    formatKValue(kValue) {
      if (kValue === null || kValue === undefined || isNaN(kValue)) {
        return '0.000';
      }
      
      // 使用 toPrecision(3) 保留三位有效数字
      let formatted = Number(kValue).toPrecision(3);
      
      // 如果结果是科学记数法，转换为普通数字格式
      if (formatted.includes('e')) {
        formatted = Number(formatted).toFixed(6);
        // 移除末尾的零
        formatted = parseFloat(formatted).toString();
      }
      
      return formatted;
    },
    async fetchOperationalTables() {
      try {
        const response = await axiosInstance.get('operational/api/operational_tables', {
          params: { wind_farm_code: this.selectedWindFarm }
        });
        const data = response.data || {};
        this.operationalTables = data.supported_tables || [];
        this.operationalTableDescriptions = data.table_descriptions || {};

        if (this.operationalTables.length === 0) {
          this.selectedOperationalTable = '';
          this.operationalSchema = null;
          this.resetOperationalUploadState({ clearMessages: true });
          return;
        }

        const maintainSelection = this.selectedOperationalTable && this.operationalTables.includes(this.selectedOperationalTable);
        const nextSelection = maintainSelection ? this.selectedOperationalTable : this.operationalTables[0];
        this.selectedOperationalTable = nextSelection;
        await this.fetchOperationalTableSchema(nextSelection);
      } catch (error) {
        ElMessage.error('获取运营数据类型失败');
        console.error('fetchOperationalTables error:', error);
      }
    },
    async fetchOperationalTableSchema(tableName) {
      if (!tableName) {
        this.operationalSchema = null;
        return;
      }
      this.operationalSchemaLoading = true;
      try {
        const response = await axiosInstance.get(`operational/api/operational_table_schema/${tableName}`, {
          params: { wind_farm_code: this.selectedWindFarm }
        });
        this.operationalSchema = response.data?.columns || {};
        if (this.operationalSchema && Object.keys(this.operationalSchema).length) {
          this.triggerPanelPulse('schema');
        }
      } catch (error) {
        ElMessage.error('获取表字段信息失败');
        console.error('fetchOperationalTableSchema error:', error);
        this.operationalSchema = null;
      } finally {
        this.operationalSchemaLoading = false;
      }
    },
    async handleOperationalTableChange(value) {
      this.selectedOperationalTable = value;
      await this.fetchOperationalTableSchema(value);
      this.resetOperationalUploadState({ clearMessages: true });
    },
    handleOperationalFileChange(file, fileList) {
      this.operationalUpload.fileList = fileList.slice(-1);
      this.operationalUpload.file = file?.raw || null;
      this.operationalUploadResult = null;
      this.operationalUploadError = null;
    },
    handleOperationalFileRemove() {
      this.resetOperationalUploadState({ clearMessages: true });
    },
    resetOperationalUploadState(options = {}) {
      const { clearMessages = false } = options;
      this.operationalUpload.file = null;
      this.operationalUpload.fileList = [];
      if (clearMessages) {
        this.operationalUploadResult = null;
        this.operationalUploadError = null;
        this.clearPanelPulse('upload');
        this.clearPanelPulse('schema');
      }
    },
    formatFileSize(size) {
      if (size === undefined || size === null) {
        return '--';
      }
      const units = ['B', 'KB', 'MB', 'GB'];
      let value = size;
      let unitIndex = 0;
      while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
      }
      const precision = value < 10 && unitIndex > 0 ? 1 : 0;
      return `${value.toFixed(precision)} ${units[unitIndex]}`;
    },
    async uploadOperationalDataset() {
      if (!this.selectedOperationalTable) {
        ElMessage.warning('请先选择数据类型');
        return;
      }
      if (!this.operationalUpload.file) {
        ElMessage.warning('请先选择要上传的CSV文件');
        return;
      }

      const formData = new FormData();
      formData.append('file', this.operationalUpload.file);
      formData.append('table_name', this.selectedOperationalTable);
      if (this.selectedWindFarm) {
        formData.append('wind_farm_code', this.selectedWindFarm);
      }

      this.operationalUpload.uploading = true;
      try {
        const response = await axiosInstance.post('operational/api/upload_operational_csv', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        this.operationalUploadResult = response.data;
        this.operationalUploadError = null;
        ElMessage.success(response.data?.message || '上传成功');
        this.triggerPanelPulse('upload');
        this.resetOperationalUploadState();
        await Promise.all([
          this.fetchComparisonData(),
          this.fetchOperationalTableSchema(this.selectedOperationalTable)
        ]);
        this.triggerPanelPulse('schema');
      } catch (error) {
        console.error('uploadOperationalDataset error:', error);
        this.operationalUploadError = error.response?.data?.error || error.message;
        ElMessage.error(this.operationalUploadError || '上传失败');
      } finally {
        this.operationalUpload.uploading = false;
      }
    },
    async fetchComparisonData() {
      if (this.isProcessingChart) {
        this.$message.warning('正在处理上一个请求，请稍候...');
        return;
      }
      this.isProcessingChart = true;
      this.loading = true;

      if (!this.timeRange || this.timeRange.length !== 2) {
        this.$message.error('请选择完整的时间范围');
        this.loading = false; // Release loading state
        this.isProcessingChart = false; // Release lock
        return;
      }

      try {
        const payload = {
          start: this.timeRange[0],
          end: this.timeRange[1],
          types: this.selectedTypes,
          wind_farm_code: this.selectedWindFarm,
          ...(this.selectedTypes.includes('超短期预测') && { supershort_horizon: 'average' })
        };

        const response = await axiosInstance.post('power-compare/data', payload);
        await this.processChartData(response.data); 
        this.triggerPanelPulse('config');
      } catch (error) {
        this.$message.error('数据获取失败');
        console.error(error);
        this.chartData = null; 
      } finally {
        this.loading = false;
        this.isProcessingChart = false; // Ensure lock is released in finally
      }
    },

    async processChartData(apiData) {
      try {
          console.log('ProcessChartData - 原始API数据:', apiData);

          // 提前处理 apiData 为空或无效的情况
          if (!apiData || (typeof apiData === 'object' && Object.keys(apiData).length === 0)) {
              console.warn("ProcessChartData - apiData 无效或为空, 将清空图表并显示无数据提示。");
              this.chartData = null; // 这将触发 v-if="!chartData" 显示"暂无数据"
              if (this.chartInstance) {
                  console.log('ProcessChartData - 销毁因空数据产生的旧主图表实例');
                  this.chartInstance.destroy();
                  this.chartInstance = null;
              }
              // 如果指标图表也依赖于此，也需要清空
              if (this.showDailyMetricsAnalysis) {
                  this.dailyMetrics = null; // 清空指标数据
                  await this.$nextTick(); // 等待 DOM 更新（如果 metricChart 的 canvas 依赖 v-if）
                  this.updateMetricChart(); // updateMetricChart 内部会处理 dailyMetrics 为 null 的情况
              }
              this.exportData.comparison = null;
              this.exportData.metrics = null;
              return; // 处理完毕，提前返回
          }

          this.chartData = apiData; 

          await this.$nextTick(); 

          if (this.chartInstance) {
            console.log('ProcessChartData - 销毁旧的主图表实例:', this.chartInstance.id);
            this.chartInstance.destroy();
            this.chartInstance = null;
          }

          this.chartKey++;
          console.log('ProcessChartData - chartKey incremented to:', this.chartKey);

          await this.$nextTick(); 
          console.log('ProcessChartData - $nextTick after incrementing chartKey');

          const canvasEl = this.$refs.chartCanvas;
          if (!canvasEl) {
            console.error('ProcessChartData - 主图表 Canvas 元素 (this.$refs.chartCanvas) 未找到!');
            return;
          }
          
          const ctx = canvasEl.getContext('2d');
          if (!ctx) {
            console.error('ProcessChartData - 获取主图表 Canvas 的 2D 上下文失败!');
            return;
          }
          
          // ... (rest of the processChartData method, including calculateDailyMetrics, prepareChartJsDataForMainChart, new Chart, updateMetricChart call)
          // The following is a placeholder for the rest of your processChartData, ensure the actual content is there.
          console.log('ProcessChartData - 开始计算每日指标');
          this.dailyMetrics = this.calculateDailyMetrics(apiData); 
          if (this.dailyMetrics && Object.keys(this.dailyMetrics).length > 0) {
            this.triggerPanelPulse('metrics');
          }
          console.log('ProcessChartData - 每日指标计算结果:', this.dailyMetrics);

          const { labels, datasets: chartJSDatasets, sortedTimestamps } = this.prepareChartJsDataForMainChart(apiData);
          console.log('ProcessChartData - 为主图表准备的 Labels:', labels);
          console.log('ProcessChartData - 为主图表准备的 Datasets:', chartJSDatasets);

          if (labels.length === 0 && chartJSDatasets.length === 0 && Object.keys(apiData).length > 0) {
              console.warn("ProcessChartData - API有数据但处理后图表数据为空,检查prepareChartJsDataForMainChart逻辑");
          }

          try {
        this.chartInstance = new Chart(ctx, {
          type: 'line',
          data: {
                labels: labels,
                datasets: chartJSDatasets
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
              legend: {
                position: 'top',
                labels: {
                  padding: 20,
                  font: { size: 13 },
                  usePointStyle: true,
                  pointStyle: 'line'
                }
              },
              tooltip: { 
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += context.parsed.y.toFixed(2);
                            if (context.dataset.yAxisID === YAXIS_POWER) {
                                label += ' MW';
                            } else if (context.dataset.yAxisID === YAXIS_WINDSPEED) {
                                label += ' m/s'; 
                            }
                        }
                        return label;
                    }
                }
                  },
                  zoom: { 
                    pan: {
                      enabled: true,
                      mode: 'x',
                      threshold: 5,
                    },
                    zoom: {
                      wheel: {
                        enabled: true,
                      },
                      pinch: {
                        enabled: true
                      },
                      mode: 'x',
                      drag: {
                        enabled: true,
                        backgroundColor: 'rgba(0,123,255,0.25)'
                      }
                    },
                    limits: {
                    },
              }
            },
            scales: {
              x: {
                grid: { color: 'rgba(255,255,255,0.1)' },
                ticks: { 
                  color: '#666',
                  maxRotation: 45,
                  minRotation: 45
                }
              },
              [YAXIS_POWER]: { 
                type: 'linear',
                display: true,
                position: 'left',
                beginAtZero: true,
                suggestedMax: this.wfcapacity * 1.1, 
                title: {
                  display: true,
                  text: '功率 (MW)',
                  color: '#666'
                },
                grid: { color: 'rgba(255,255,255,0.1)' },
                ticks: { color: '#666' }
              },
              [YAXIS_WINDSPEED]: { 
                type: 'linear',
                    display: chartJSDatasets.some(ds => ds.yAxisID === YAXIS_WINDSPEED), 
                position: 'right',
                beginAtZero: true,
                suggestedMax: 30, 
                title: {
                  display: true,
                  text: '风速 (m/s)', 
                  color: '#666'
                },
                grid: { 
                  drawOnChartArea: false, 
                },
                ticks: { color: '#666' }
              }
            }
          }
            });
            console.log('ProcessChartData - 新的主图表实例创建成功:', this.chartInstance.id);
          } catch (e) {
            console.error("ProcessChartData - 创建主图表实例时出错:", e);
            return;
          }

      this.triggerPanelPulse('chart');

      this.$nextTick(() => {
            if (this.showDailyMetricsAnalysis && this.dailyMetrics) {
              console.log('ProcessChartData - 调用 updateMetricChart');
              this.updateMetricChart();
            }
          });

          const exportComparisonDatasets = {};
          chartJSDatasets.forEach(dataset => {
              let cleanKey = dataset.label;
              // 修改正则表达式来正确处理超短期预测的label格式
              // 对于超短期预测，匹配到指标括号之前的内容（包含horizon信息）
              const matchMetrics = dataset.label.match(/^(.*?)\s*\(\s*MAE\s*:/); 
              if (matchMetrics && matchMetrics[1]) {
                  cleanKey = matchMetrics[1].trim();
              }
              // 处理风速数据的右轴标记
              if (dataset.yAxisID === YAXIS_WINDSPEED) {
                  cleanKey = cleanKey.replace(' (右轴)', '').trim();
              }
              exportComparisonDatasets[cleanKey] = dataset.data;
          });

      this.exportData.comparison = {
        labels: labels,
        rawTimestamps: sortedTimestamps,
            datasets: exportComparisonDatasets
          };
          this.exportData.metrics = this.dailyMetrics;
          console.log('ProcessChartData - 导出数据已准备:', this.exportData);

      } catch(e) {
          console.error("Error in processChartData:", e);
      } 
    },

    // 辅助方法：为主要对比图表准备 Chart.js 数据格式
    prepareChartJsDataForMainChart(apiData) {
      const datasets = [];
      const powerColors = {
        '实测值': '#FF6B6B',
        '超短期预测': this.colors['超短期预测'], // 确保 this.colors 定义了这些
        '短期预测': this.colors['短期预测'],
        '中期预测': this.colors['中期预测']
      };
      const windSpeedColors = this.windSpeedColors; // 确保 this.windSpeedColors 定义了这些

      let timestamps = new Set();
      if (apiData && typeof apiData === 'object' && Object.keys(apiData).length > 0) {
        Object.values(apiData).forEach(seriesArray => {
          if (Array.isArray(seriesArray)) {
            seriesArray.forEach(v => {
              if (v && v.timestamp) timestamps.add(v.timestamp);
            });
          }
        });
      } else {
          console.warn("prepareChartJsDataForMainChart: apiData 无效或为空, 返回空图表数据");
          return { labels: [], datasets: [], sortedTimestamps: [] };
      }


      const sortedTimestamps = Array.from(timestamps)
        .map(ts => new Date(ts).getTime())
        .sort((a, b) => a - b)
        .map(ts => new Date(ts).toISOString());

      const labels = sortedTimestamps.map(ts => {
        const date = new Date(ts);
        return `${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:${date.getMinutes().toString().padStart(2,'0')}`;
      });

      // --- 处理功率数据 ---
      if (apiData['实测值'] && Array.isArray(apiData['实测值'])) {
        const actualMap = new Map(apiData['实测值'].map(v => [
          new Date(v.timestamp).toISOString(),
          v.power
        ]));
        datasets.push({
          label: '实测值',
          data: sortedTimestamps.map(ts => actualMap.get(ts) === undefined ? null : actualMap.get(ts)),
          borderColor: powerColors['实测值'],
          backgroundColor: `${powerColors['实测值']}33`,
          tension: 0.3,
          pointRadius: 3,
          spanGaps: true,
          yAxisID: YAXIS_POWER
        });
      }

      const predictionKeys = ['超短期预测', '短期预测', '中期预测'];
      const selectedPredictionTypes = predictionKeys.filter(type => this.selectedTypes.includes(type) && apiData[type] && Array.isArray(apiData[type]));

      selectedPredictionTypes.forEach(type => {
        const predictedMap = new Map(apiData[type].map(v => [
          new Date(v.timestamp).toISOString(),
          v.power
        ]));

        let metricsTextLabel = type;
        // 'average' 是默认的，但如果 selectedSupershortHorizon 可以是其他值，需要处理
        const horizon = (type === '超短期预测' && this.selectedSupershortHorizon && this.selectedSupershortHorizon.length > 0)
                            ? this.selectedSupershortHorizon.join(', ') : 'average';
        if (type === '超短期预测') {
            metricsTextLabel = `${type} (${horizon})`;
        }

        // 计算图例显示的整体指标，使用正确的按天K值计算方式
        if (apiData['实测值'] && Array.isArray(apiData['实测值']) && apiData[type] && Array.isArray(apiData[type])) {
          // 先计算该预测类型的每日指标（确保K值按天计算）
          const tempDailyMetrics = this.calculateDailyMetricsForType(apiData, type);
          
          if (tempDailyMetrics && tempDailyMetrics.length > 0) {
            // 计算所有天的指标平均值
            const avgMAE = tempDailyMetrics.reduce((sum, day) => sum + day.mae, 0) / tempDailyMetrics.length;
            const avgRMSE = tempDailyMetrics.reduce((sum, day) => sum + day.rmse, 0) / tempDailyMetrics.length;
            const avgACC = tempDailyMetrics.reduce((sum, day) => sum + day.acc, 0) / tempDailyMetrics.length;
            const avgK = tempDailyMetrics.reduce((sum, day) => sum + day.k, 0) / tempDailyMetrics.length;
            const avgPe = tempDailyMetrics.reduce((sum, day) => sum + day.pe, 0) / tempDailyMetrics.length;
            
            metricsTextLabel = `${metricsTextLabel} (MAE: ${avgMAE.toFixed(1)} | RMSE: ${avgRMSE.toFixed(1)} | ACC: ${(avgACC * 100).toFixed(1)}% | K: ${this.formatKValue(avgK)} | Pe: ${avgPe.toFixed(1)})`;
          } else {
            console.warn(`prepareChartJsDataForMainChart: 类型 ${type} 无法计算每日指标`);
          }
        }
        
        datasets.push({
          label: metricsTextLabel,
          data: sortedTimestamps.map(ts => predictedMap.get(ts) === undefined ? null : predictedMap.get(ts)),
          borderColor: powerColors[type],
          backgroundColor: `${powerColors[type]}33`,
          tension: 0.3,
          pointRadius: 3,
          spanGaps: true,
          yAxisID: YAXIS_POWER
        });
      });

      // --- 处理风速数据 ---
      // 你的 selectedTypes 包含 "短期风速预测", "中期风速预测"
      // 但 apiData 的 key 可能是 "短期风速", "中期风速"
      const windSpeedApiKeys = {
          '短期风速预测': '短期风速',
          '中期风速预测': '中期风速'
      };
      const selectedWindSpeedTypes = Object.keys(windSpeedApiKeys)
                                      .filter(type => this.selectedTypes.includes(type) && apiData[windSpeedApiKeys[type]] && Array.isArray(apiData[windSpeedApiKeys[type]]));

      selectedWindSpeedTypes.forEach(selectedTypeKey => { // e.g., "短期风速预测"
        const apiKey = windSpeedApiKeys[selectedTypeKey]; // e.g., "短期风速"
        const wsMap = new Map(apiData[apiKey].map(v => [
            new Date(v.timestamp).toISOString(),
            v.wind_speed
        ]));
        datasets.push({
            label: `${apiKey} (右轴)`, // 使用 apiKey "短期风速" 作为图例标签基础
            data: sortedTimestamps.map(ts => wsMap.get(ts) === undefined ? null : wsMap.get(ts)),
            borderColor: windSpeedColors[apiKey], // 使用 apiKey "短期风速"
            backgroundColor: `${windSpeedColors[apiKey]}33`,
            tension: 0.4,
            pointRadius: 2,
            borderDash: [5, 5],
            spanGaps: true,
            yAxisID: YAXIS_WINDSPEED
        });
      });
      
      return { labels, datasets, sortedTimestamps };
    },

    calculateMetrics(actual, predicted) {
      const threshold = 0.2 * this.wfcapacity
      
      // 过滤掉实测值为null的数据点
      const validIndices = actual.map((val, idx) => val !== null ? idx : null).filter(idx => idx !== null)
      const filteredActual = validIndices.map(idx => actual[idx])
      const filteredPredicted = validIndices.map(idx => predicted[idx])
      
      // 如果没有有效数据点，返回默认值
      if (filteredActual.length === 0) {
        return { mae: 0, mse: 0, rmse: 0, acc: 0, k: 0, pe: 0 }
      }
      
      const mae = filteredPredicted.reduce((sum, p, i) => sum + Math.abs(p - filteredActual[i]), 0) / filteredPredicted.length
      
      const mse = filteredPredicted.reduce((sum, p, i) => sum + Math.pow(p - filteredActual[i], 2), 0) / filteredPredicted.length
      const rmse = Math.sqrt(mse)
      
      const acc = 1 - rmse / this.wfcapacity
      
      const pe = acc < 0.83 ? (0.83 - acc) * this.wfcapacity : 0
      
      // 修正K值计算：使用实际值的绝对值作为分母的基础
      const m_values = filteredPredicted.map((p, i) => {
        const actualVal = Math.max(Math.abs(filteredActual[i]), threshold)
        return Math.pow((p - filteredActual[i]) / actualVal, 2)
      })
      const k = m_values.length > 0 ? 1 - Math.sqrt(m_values.reduce((sum, v) => sum + v, 0) / m_values.length) : 0
      
      return { mae, mse, rmse, acc, k, pe }
    },

    calculateDailyMetrics(data) {
      console.log('计算每日指标的输入数据:', data)
      if (!data['实测值']) {
        console.warn('没有实测值数据，无法计算评估指标')
        return null
      }

      const dailyMetrics = {}
      const predictionTypes = this.selectedTypes.filter(type => 
        type !== '实测值' && data[type]
      )
      console.log('预测类型:', predictionTypes)

      predictionTypes.forEach(type => {
        dailyMetrics[type] = this.calculateDailyMetricsForType(data, type)
      })

      this.calculateQualificationRates(dailyMetrics)

      return dailyMetrics
    },

    calculateDailyMetricsForType(data, type) {
      console.log(`处理预测类型: ${type}`)
      const metricsByDay = {}
      
      data[type].forEach(pred => {
        const dateObj = new Date(pred.timestamp)
        const date = `${dateObj.getFullYear()}-${(dateObj.getMonth()+1).toString().padStart(2,'0')}-${dateObj.getDate().toString().padStart(2,'0')}`
        
        if (!metricsByDay[date]) {
          metricsByDay[date] = {
            predicted: [],
            actual: []
          }
        }

        const actualPoint = data['实测值'].find(
          act => new Date(act.timestamp).getTime() === new Date(pred.timestamp).getTime()
        )
        // 即使实测值可能为null，也收集这个数据点
        if (actualPoint) {
          metricsByDay[date].predicted.push(pred.power)
          metricsByDay[date].actual.push(actualPoint.power)
        }
      })

      console.log(`${type} 的每日数据:`, metricsByDay)

      // 收集所有日期，以确保日期连续性
      const allDates = Object.keys(metricsByDay).sort()
      
      return allDates
        .filter(dateStr => {
          const date = new Date(dateStr)
          const startDate = new Date(this.timeRange[0])
          const endDate = new Date(this.timeRange[1])
          return date >= startDate && date <= endDate
        })
        .filter(dateStr => {
          // 确保至少有一些预测数据点
          return metricsByDay[dateStr].predicted.length > 0
        })
        .map(date => {
          const dayData = metricsByDay[date]
          // 计算指标 - calculateMetrics会自动过滤掉actual为null的点
          const metrics = this.calculateMetrics(dayData.actual, dayData.predicted)
          const threshold = this.qualifiedThresholds[type] || 0
          const isQualified = metrics.k > threshold
          
          // 记录有效数据点的百分比
          const totalPoints = dayData.actual.length
          const validPoints = dayData.actual.filter(val => val !== null).length
          const validDataPercentage = totalPoints > 0 ? (validPoints / totalPoints) * 100 : 0
          
          return { 
            date, 
            ...metrics, 
            isQualified,
            totalPoints,
            validPoints,
            validDataPercentage
          }
        })
        .sort((a, b) => new Date(a.date) - new Date(b.date))
    },

    calculateQualificationRates(dailyMetrics) {
      const qualificationRates = {}
      
      Object.entries(dailyMetrics).forEach(([type, metrics]) => {
        const qualifiedDays = metrics.filter(day => day.isQualified)
        const rate = metrics.length > 0 ? (qualifiedDays.length / metrics.length) * 100 : 0
        qualificationRates[type] = {
          totalDays: metrics.length,
          qualifiedDays: qualifiedDays.length,
          rate: rate,
          threshold: this.qualifiedThresholds[type]
        }
      })
      
      this.qualificationRates = qualificationRates
      if (this.showQualificationRateAnalysis && this.qualificationRates && Object.keys(this.qualificationRates).length > 0) {
        this.triggerPanelPulse('qualification');
      }
    },

    updateMetricChart() {
        console.log('开始更新指标图表');
        
        // 防止同时多次更新
        if (this.isUpdatingMetricChart) {
            console.log('已有更新操作正在进行，忽略此次调用');
            return;
        }
        
        this.isUpdatingMetricChart = true;
        
        // 销毁旧图表
        if (this.metricChart) {
            try {
                this.metricChart.destroy();
            } catch (error) {
                console.warn('销毁旧图表实例时出错:', error);
            }
            this.metricChart = null;
        }

        // 获取Canvas元素
        this.$nextTick(() => {
            try {
                const canvas = this.$refs.metricChart;
                if (!canvas) {
                    console.error('指标图表Canvas元素未找到');
                    this.isUpdatingMetricChart = false;
                    return;
                }

                // 检查数据有效性
                if (!this.dailyMetrics || Object.keys(this.dailyMetrics).length === 0) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.font = "16px Arial";
                    ctx.fillStyle = "#888";
                    ctx.textAlign = "center";
                    ctx.fillText("暂无指标数据", canvas.width / 2, canvas.height / 2);
                    this.isUpdatingMetricChart = false;
                    return;
                }

                // 准备图表数据
                const { labels, datasets } = this.prepareMetricChartData();
                
                // 如果没有有效数据，显示提示
                if (!labels.length || !datasets.length) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.font = "16px Arial";
                    ctx.fillStyle = "#888";
                    ctx.textAlign = "center";
                    ctx.fillText("所选指标无数据", canvas.width / 2, canvas.height / 2);
                    this.isUpdatingMetricChart = false;
                    return;
                }

                // 指标配置
                const metricConfig = {
                    acc: { label: 'ACC (%)', min: 0, max: 100 },
                    mae: { label: 'MAE (MW)', min: 0 },
                    mse: { label: 'MSE (MW²)', min: 0 },
                    rmse: { label: 'RMSE (MW)', min: 0 },
                    k: { label: 'K值', min: -1, max: 1 },
                    pe: { label: 'Pe (MW)', min: 0 }
                }[this.currentMetric];

                // 合格线插件
                const qualificationLinePlugin = {
                    id: 'qualificationLine',
                    beforeDraw: (chart) => {
                        if (this.currentMetric === 'k') {
                            const ctx = chart.ctx;
                            const yAxis = chart.scales.y;
                            const chartArea = chart.chartArea;

                            Object.entries(this.qualifiedThresholds).forEach(([type, threshold]) => {
                                if (this.selectedTypes.includes(type)) {
                                    const y = yAxis.getPixelForValue(threshold);
                                    ctx.save();
                                    ctx.beginPath();
                                    ctx.moveTo(chartArea.left, y);
                                    ctx.lineTo(chartArea.right, y);
                                    ctx.lineWidth = 1;
                                    ctx.strokeStyle = `${this.colors[type]}99`;
                                    ctx.setLineDash([5, 5]);
                                    ctx.stroke();
                                    
                                    ctx.textAlign = 'left';
                                    ctx.textBaseline = 'bottom';
                                    ctx.fillStyle = this.colors[type];
                                    ctx.font = '12px Arial';
                                    ctx.fillText(`${type}合格线: K > ${threshold}`, chartArea.left + 10, y - 2);
                                    ctx.restore();
                                }
                            });
                        }
                    }
                };

                // 创建图表
                try {
                    this.metricChart = new Chart(canvas.getContext('2d'), {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: datasets
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    position: 'top',
                                    labels: { font: { size: 13 } }
                                },
                                title: {
                                    display: true,
                                    text: metricConfig.label,
                                    font: { size: 16 },
                                    padding: 20
                                },
                                tooltip: {
                                    callbacks: {
                                        label: (context) => {
                                            let label = context.dataset.label.split(' (')[0] + ': ';
                                            if (context.parsed.y !== null) {
                                                // 判断当前指标类型并使用相应的格式化方法
                                                if (this.currentMetric === 'k') {
                                                    label += this.formatKValue(context.parsed.y);
                                                } else {
                                                    label += context.parsed.y.toFixed(2);
                                                    if (context.chart.options.plugins.title.text.includes('%')) {
                                                        label += '%';
                                                    } else if (context.chart.options.plugins.title.text.includes('MW')) {
                                                        label += ' MW';
                                                    }
                                                }
                                            }
                                            return label;
                                        }
                                    }
                                }
                            },
                            scales: {
                                x: {
                                    display: true,
                                    grid: { color: 'rgba(200,200,200,0.1)' },
                                    ticks: { 
                                        color: '#666',
                                        maxRotation: 45,
                                        minRotation: 45
                                    }
                                },
                                y: {
                                    display: true,
                                    beginAtZero: true,
                                    min: metricConfig.min,
                                    max: metricConfig.max,
                                    grid: { color: 'rgba(200,200,200,0.1)' },
                                    ticks: {
                                        color: '#666',
                                        callback: (value) => {
                                            switch (this.currentMetric) {
                                                case 'acc': return value.toFixed(1) + '%';
                                                case 'mse': return value.toFixed(1) + ' MW²';
                                                case 'k': return this.formatKValue(value);
                                                default: return value.toFixed(1) + ' MW';
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        plugins: [qualificationLinePlugin]
                    });
                    
                    console.log('指标图表创建成功');
                } catch (error) {
                    console.error('创建指标图表时出错:', error);
                } finally {
                    this.isUpdatingMetricChart = false;
                }
            } catch (error) {
                console.error('绘制图表过程中发生错误:', error);
                this.isUpdatingMetricChart = false;
            }
        });
    },

    prepareMetricChartData() {
        // 直接使用与指标下载相同的数据源
        if (!this.exportData.metrics) {
            console.warn('没有可用于图表的指标数据');
            return { labels: [], datasets: [] };
        }

        const metrics = this.exportData.metrics;
        const predictionTypes = Object.keys(metrics).filter(type => 
            this.selectedTypes.includes(type) && type !== '实测值'
        );

        if (predictionTypes.length === 0) {
            console.warn('没有选中的预测类型');
            return { labels: [], datasets: [] };
        }

        // 收集所有唯一日期并排序
        const allDates = new Set();
        predictionTypes.forEach(type => {
            metrics[type].forEach(day => {
                allDates.add(day.date);
            });
        });
        const sortedDates = Array.from(allDates).sort();

        // 创建日期标签
        const dateLabels = sortedDates.map(date => {
            const dateObj = new Date(date);
            return `${dateObj.getMonth() + 1}/${dateObj.getDate()}`;
        });

        console.log('图表日期标签:', dateLabels, '原始日期:', sortedDates);

        // 创建数据集
        const datasets = [];

        // 为每个预测类型创建一个数据集
        predictionTypes.forEach(type => {
            // 创建一个日期到指标值的映射
            const dateToMetric = {};
            metrics[type].forEach(day => {
                dateToMetric[day.date] = day;
            });

            // 为所有日期创建数据点
            const dataPoints = sortedDates.map(date => {
                const day = dateToMetric[date];
                if (!day) return null;

                // 获取当前选择的指标值
                let value = day[this.currentMetric];
                if (this.currentMetric === 'acc') {
                    value = value * 100; // 转换为百分比
                }
                return value;
            });

            // 计算平均值 (排除null值)
            const validValues = dataPoints.filter(v => v !== null && !isNaN(v));
            const avg = validValues.length > 0 ? 
                validValues.reduce((sum, val) => sum + val, 0) / validValues.length : 0;
            
            // 创建数据集
            const avgFormatted = this.currentMetric === 'k' ? this.formatKValue(avg) : avg.toFixed(2);
            datasets.push({
                label: `${type} (平均: ${avgFormatted}${this.currentMetric === 'acc' ? '%' : ''})`,
                data: dataPoints,
                borderColor: this.colors[type],
                backgroundColor: `${this.colors[type]}33`,
                tension: 0.3,
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                spanGaps: true
            });

            console.log(`预测类型: ${type}, 指标: ${this.currentMetric}`, {
                日期: dateLabels,
                数据: dataPoints,
                平均值: avg
            });
        });

        return { labels: dateLabels, datasets };
    },
    
    // 辅助函数：将十六进制颜色转为RGB格式
    hexToRgb(hex) {
        // 去掉可能的#前缀
        hex = hex.replace(/^#/, '');
        
        // 解析颜色
        let bigint = parseInt(hex, 16);
        let r = (bigint >> 16) & 255;
        let g = (bigint >> 8) & 255;
        let b = bigint & 255;
        
        return `${r}, ${g}, ${b}`;
    },
    
    // ... other methods like generateComparisonCSV, downloadMetricsCSV, downloadSVG, downloadMetricSVG, getQualificationColor, setQuickTimeRange etc.
    // Ensure they are still present
    generateComparisonCSV() {
        if (!this.exportData.comparison || 
            !this.exportData.comparison.rawTimestamps || 
            !this.exportData.comparison.datasets) {
            this.$message.warning('导出数据尚未准备好')
            return ''
        }

        const headers = ['时间戳'];
        const dataKeys = []; 

        if (this.selectedTypes.includes('实测值') && this.exportData.comparison.datasets['实测值']) {
            headers.push('实测值(MW)');
            dataKeys.push('实测值');
        }
        
        const selectedPowerPredictionTypes = (this.selectedTypes || [])
            .filter(type => { 
                if (type === '实测值' || type.includes('风速')) return false;
                
                let keyToFindPrefix = type; 
                if (type === '超短期预测' && this.selectedSupershortHorizon.length > 0) {
                    keyToFindPrefix = `${type} (${this.selectedSupershortHorizon.join(', ')})`; 
                }
                return Object.keys(this.exportData.comparison.datasets).some(exportKey => exportKey.startsWith(keyToFindPrefix));
            });

        selectedPowerPredictionTypes.forEach(type => { 
            let csvHeaderName = type; 
            if (type === '超短期预测' && this.selectedSupershortHorizon.length > 0) {
                csvHeaderName = `${type} (${this.selectedSupershortHorizon.join(', ')})`; 
            }
            headers.push(`${csvHeaderName}(MW)`); 

            const actualDatasetKey = Object.keys(this.exportData.comparison.datasets)
                                       .find(k => k.startsWith(csvHeaderName)); 
            if (actualDatasetKey) {
                dataKeys.push(actualDatasetKey);
            } else {
                console.warn(`CSV Export: Could not find dataset key for power type: ${csvHeaderName}`);
                dataKeys.push(csvHeaderName); 
            }
        });

        const selectedWindSpeedTypes = (this.selectedTypes || [])
            .filter(type => { 
                if (!type.includes('风速预测')) return false;
                const keyToFind = type.replace('预测', ''); 
                return !!this.exportData.comparison.datasets[keyToFind];
            });

        selectedWindSpeedTypes.forEach(type => { 
            const csvHeaderName = type.replace('预测', ''); 
            headers.push(`${csvHeaderName}(m/s)`); 
            dataKeys.push(csvHeaderName); 
        });

        const dataRows = this.exportData.comparison.rawTimestamps.map((ts, index) => {
            const date = new Date(ts);
            const beijingDate = new Date(date.getTime() + 8 * 60 * 60 * 1000);
            const formattedDate = 
                `${beijingDate.getUTCFullYear()}-` +
                `${(beijingDate.getUTCMonth() + 1).toString().padStart(2, '0')}-` +
                `${beijingDate.getUTCDate().toString().padStart(2, '0')} ` +
                `${beijingDate.getUTCHours().toString().padStart(2, '0')}:` +
                `${beijingDate.getUTCMinutes().toString().padStart(2, '0')}:` +
                `${beijingDate.getUTCSeconds().toString().padStart(2, '0')}`;

            const row = [formattedDate];
            dataKeys.forEach(key => { 
                const dataSet = this.exportData.comparison.datasets[key] || [];
                const value = dataSet[index];
                row.push(value !== undefined && value !== null ? Number(value).toFixed(2) : '');
            });
            return row;
        });

        const csvData = [
            headers,
            ...dataRows,
        ];

        return csvData
            .filter(row => Array.isArray(row))
            .map(row => {
                const processedRow = row.map(cell => {
                    if (Array.isArray(cell)) return cell.join(',');
                    return typeof cell === 'string' ? cell : String(cell);
                });
                return processedRow.join(',');
            })
            .join('\n');
    },
    // 将这个方法添加到你的 export default { ... methods: { ... } } 中
    downloadCSV() {
      const csvString = this.generateComparisonCSV(); // 这个方法你需要确保也存在且工作正常
      // 清晰地打印返回的字符串，便于调试
      console.log('--- BEGIN GENERATED CSV STRING ---');
      console.log(csvString);
      console.log('--- END GENERATED CSV STRING ---');

      if (!csvString) { 
        // generateComparisonCSV 内部通常已经有 $message.warning 了，
        // 这里可以不再重复提示或保留一个通用提示。
        // 例如: this.$message.info('未能生成CSV文件内容或内容为空。');
        return;
      }

      // BOM 头，确保 Excel 能正确识别 UTF-8 编码的 CSV
      const blob = new Blob(["\ufeff" + csvString], { type: 'text/csv;charset=utf-8' });
      const link = document.createElement('a');

      if (link.download !== undefined) { // 检查浏览器是否支持 download 属性
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        // 文件名可以根据需要调整
        link.setAttribute('download', `功率对比数据_${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }).replace(/[/\s:]/g, '-')}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url); // 及时释放
      } else {
        // 对于不支持 download 属性的旧浏览器 (例如 IE)
        // 你可能需要一个不同的策略，或者提示用户手动复制数据
        this.$message.error('您的浏览器不支持自动下载，请尝试更新浏览器或手动复制数据。');
        // navigator.msSaveBlob(blob, filename); // IE10+ 的特定方法
      }
    },
    downloadMetricsCSV() {
      if (!this.exportData.metrics) {
        this.$message.warning('暂无可导出的指标数据')
        return
      }

      const headers = ['日期', '预测类型', 'ACC(%)', 'MAE(MW)', 'MSE(MW²)', 'RMSE(MW)', 'K值', 'Pe(MW)', 
                      '合格标准', '是否合格', '总数据点', '有效数据点', '有效数据百分比(%)']
      const rows = []
      
      Object.entries(this.exportData.metrics).forEach(([type, days]) => {
        const threshold = this.qualifiedThresholds[type] || 0
        days.forEach(day => {
          rows.push([
            day.date,
            type,
            (day.acc * 100).toFixed(2),
            day.mae.toFixed(2),
            day.mse.toFixed(2),
            day.rmse.toFixed(2),
            this.formatKValue(day.k),
            day.pe.toFixed(2),
            `K值 > ${threshold}`,
            day.isQualified ? '是' : '否',
            day.totalPoints || '未知',
            day.validPoints || '未知',
            day.validDataPercentage ? day.validDataPercentage.toFixed(1) : '100.0'
          ])
        })
      })

      if (this.qualificationRates) {
        rows.push([])
        rows.push(['合格率汇总'])
        rows.push(['预测类型', '合格标准', '合格天数', '总天数', '合格率(%)'])
        
        Object.entries(this.qualificationRates).forEach(([type, data]) => {
          rows.push([
            type,
            `K值 > ${data.threshold}`,
            data.qualifiedDays,
            data.totalDays,
            data.rate.toFixed(1)
          ])
        })
      }

      const csvContent = [headers, ...rows]
        .map(row => row.join(','))
        .join('\n')

      const blob = new Blob(["\ufeff" + csvContent], { type: 'text/csv;charset=utf-8' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `每日评估指标_${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }).replace(/[/\s:]/g, '-')}.csv`
      link.click()
    },

    downloadSVG() {
      const canvas = this.$refs.chartCanvas
      if (!canvas) {
        this.$message.warning('暂无可导出的图表')
        return
      }
      const svgContent = `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}">
        <foreignObject width="100%" height="100%">
          <div xmlns="http://www.w3.org/1999/xhtml">
            <img src="${canvas.toDataURL('image/png')}" width="100%" height="100%"/>
          </div>
        </foreignObject>
      </svg>`
      const blob = new Blob([svgContent], { type: 'image/svg+xml' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `功率对比图表_${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }).replace(/[/\s:]/g, '-')}.svg`
      link.click()
    },

    downloadMetricSVG() {
      const canvas = this.$refs.metricChart
      if (!canvas) {
        this.$message.warning('暂无可导出的指标图表')
        return
      }
      const svgContent = `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}">
          <foreignObject width="100%" height="100%">
              <div xmlns="http://www.w3.org/1999/xhtml">
                  <img src="${canvas.toDataURL('image/png')}" width="100%" height="100%"/>
              </div>
          </foreignObject>
      </svg>`
      const blob = new Blob([svgContent], { type: 'image/svg+xml' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `指标图表_${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }).replace(/[/\s:]/g, '-')}.svg`
      link.click()
    },

    getQualificationColor(rate) {
      if (rate >= 80) return '#4CAF50';
      if (rate >= 60) return '#FFC107';
      return '#F44336';
    },

    setQuickTimeRange(period) {
      if (this.isQuickTimeSwitching) {
        this.$message.warning('请勿频繁操作快速选择按钮，请等待5秒...');
        return;
      }
      this.isQuickTimeSwitching = true;

      const endDate = new Date();
      let startDate = new Date();
      
      endDate.setHours(23, 59, 59, 999);
      startDate.setHours(0, 0, 0, 0);

      switch (period) {
        case 'today': {
          break;
        }
        case '3d':{
          startDate.setDate(endDate.getDate() - 2); 
          break;
        }
        case '1w':{
          startDate.setDate(endDate.getDate() - 6); 
          break;
        }
        case '1m': {
            startDate = new Date(endDate);
          startDate.setMonth(endDate.getMonth() - 1);
             startDate.setHours(0,0,0,0); // ensure time is reset
             // If original day was 31st and prev month has 30, it rolls.
             // Check if we rolled into the *same* month as endDate by going back then forward for month day
             const checkStartDate = new Date(endDate);
             checkStartDate.setMonth(endDate.getMonth() -1);
             if (checkStartDate.getMonth() === endDate.getMonth()) { // e.g. Mar 31 to Feb rolled to Mar 3
                 startDate = new Date(endDate.getFullYear(), endDate.getMonth(), 1); // Beginning of current month
                 startDate.setDate(0); // End of previous month
                 startDate.setHours(0,0,0,0);
           } else {
                // If day doesn't exist in prev month (e.g. Mar 31st -> Feb 31st doesn't exist)
                // it auto-adjusts. e.g. Mar 31st -> March 3rd (if Feb has 28 days).
                // We want it to be Feb 28th.
                // So, if startDate's month after setMonth is not (endDate.getMonth() - 1 + 12) % 12
                // it means it rolled over.
                const targetMonth = (endDate.getMonth() - 1 + 12) % 12;
                if (startDate.getMonth() !== targetMonth) {
                    // It rolled. Set to last day of target month.
                    startDate = new Date(endDate.getFullYear(), targetMonth + 1, 0); // day 0 of next month is last day of targetMonth
                    startDate.setHours(0,0,0,0);
                }
             }
          break;
        }
        case '3m':{
          startDate = new Date(endDate);
          startDate.setMonth(endDate.getMonth() - 3);
          startDate.setHours(0,0,0,0);
          // Similar month-end/roll-over logic as '1m' might be needed if very precise "calendar 3 months"
          // For simplicity, this will be "date X, 3 months ago"
          break;
        }
        case '6m':{ 
          startDate = new Date(endDate);
          startDate.setMonth(endDate.getMonth() - 6);
          startDate.setHours(0,0,0,0);
          break;
        }
        case '1y':{
          startDate = new Date(endDate);
          startDate.setFullYear(endDate.getFullYear() - 1);
          startDate.setHours(0,0,0,0);
          break;
        }
        default:
          this.$message.error('无效的快速选择周期');
          return;
      }
      startDate.setHours(0,0,0,0);


      const formatDateVal = (date) => {
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      this.timeRange = [
        `${formatDateVal(startDate)} 00:00:00`,
        `${formatDateVal(endDate)} 23:59:59`,
      ];
      this.fetchComparisonData();

      setTimeout(() => {
        this.isQuickTimeSwitching = false;
      }, 5000); // 5-second cooldown
    },

    // 指标按钮点击处理 - 增加冷却功能
    handleMetricChange() {
      // 如果已经在冷却中，不进行操作
      if (this.isMetricButtonCooling) {
        this.$message.warning('操作过于频繁，请稍候再试');
        return;
      }
      
      // 设置冷却状态
      this.isMetricButtonCooling = true;
      
      // 更新图表
      this.updateMetricChart();
      this.triggerPanelPulse('metrics');
      
      // 3秒后解除冷却
      setTimeout(() => {
        this.isMetricButtonCooling = false;
      }, 2000);
    },
  },
  watch: {
    selectedWindFarm() {
      this.handleWindFarmSelectionChange();
    },
    showDailyMetricsAnalysis(newValue) {
      if (newValue) { 
        this.$nextTick(() => { 
          if (this.dailyMetrics) { 
            this.updateMetricChart();
          } else {
            console.log("showDailyMetricsAnalysis changed to true, but dailyMetrics is still null/empty. Metric chart not updated yet.");
          }
        });
      } else if (this.metricChart) { 
          this.metricChart.destroy();
          this.metricChart = null;
      }
    },
    showQualificationRateAnalysis(newValue) {
      if (newValue && this.qualificationRates && Object.keys(this.qualificationRates).length > 0) {
        this.triggerPanelPulse('qualification');
      }
    },
    dailyMetrics(newMetrics) {
        if (this.showDailyMetricsAnalysis && newMetrics && Object.keys(newMetrics).length > 0) {
            this.triggerPanelPulse('metrics');
            this.$nextTick(() => {
                this.updateMetricChart();
            });
        }
    },
    qualificationRates(newRates) {
      if (newRates && Object.keys(newRates).length > 0 && this.showQualificationRateAnalysis) {
        this.triggerPanelPulse('qualification');
      }
    },
    // 监听currentMetric变化时的处理已移至handleMetricChange方法
  },

  beforeUnmount() {
    if (this.chartInstance) {
      this.chartInstance.destroy();
      this.chartInstance = null;
    }
    if (this.metricChart) {
      this.metricChart.destroy();
      this.metricChart = null;
    }
    this.clearAllPanelPulses();
  }
}
</script>

<style scoped>
.operational-upload-body {
  padding: 8px 6px 20px;
}

.operational-upload-grid {
  align-items: stretch;
}

.panel--pulse {
  position: relative;
  border-color: rgba(66, 195, 255, 0.32) !important;
  box-shadow: 0 24px 60px rgba(34, 246, 170, 0.28);
  animation: panelPulse 0.9s ease;
}

.panel--pulse::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background: radial-gradient(circle at 20% 20%, rgba(66, 195, 255, 0.28), transparent 60%);
  opacity: 0.45;
}

@keyframes panelPulse {
  0% {
    box-shadow: 0 0 0 rgba(34, 246, 170, 0.35);
    border-color: rgba(66, 195, 255, 0.22);
  }
  50% {
    box-shadow: 0 24px 66px rgba(34, 246, 170, 0.45);
    border-color: rgba(66, 195, 255, 0.45);
  }
  100% {
    box-shadow: 0 0 0 rgba(34, 246, 170, 0.12);
    border-color: rgba(66, 195, 255, 0.18);
  }
}

.upload-panel,
.schema-panel,
.action-card,
.merged-config-card,
.metrics-card,
.qualifications-card,
.visualization-section,
.qualification-card {
  border-radius: 18px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 14px;
}

.icon-bubble {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(33, 150, 243, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2f80ed;
  border: 1px solid rgba(47, 128, 237, 0.25);
}

.card-header-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
}

.upload-steps {
  background: rgba(79, 152, 255, 0.08);
  border: 1px dashed rgba(79, 152, 255, 0.3);
  border-radius: 12px;
  padding: 14px 16px;
}

.tip-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  font-size: 12px;
  border-radius: 999px;
  background: rgba(47, 128, 237, 0.12);
  color: #2f80ed;
  font-weight: 600;
  letter-spacing: 0.4px;
}

.upload-drop-wrapper {
  border-radius: 14px;
  overflow: hidden;
}

.operational-upload-dropzone :deep(.el-upload) {
  width: 100%;
}

.operational-upload-dropzone :deep(.el-upload-dragger) {
  background: rgba(255, 255, 255, 0.08);
  border: 1px dashed rgba(47, 128, 237, 0.35);
  border-radius: 14px;
  padding: 26px;
}

.dropzone-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.dropzone-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.table-description {
  color: var(--text-secondary);
  font-size: 13px;
  background: rgba(47, 128, 237, 0.06);
  border-radius: 12px;
  padding: 10px 14px;
}

.selected-file-chip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgba(47, 128, 237, 0.07);
  border: 1px solid rgba(47, 128, 237, 0.12);
}

.schema-panel-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.schema-panel-body {
  background: rgba(6, 18, 36, 0.7);
  border-radius: 14px;
  padding: 12px 10px;
}

.config-panel {
  margin: 28px 0;
}

.chart-container {
  background: rgba(6, 18, 36, 0.78);
  border: 1px solid rgba(66, 195, 255, 0.18);
  border-radius: 18px;
  padding: 24px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.visualization-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 28px;
}

.visualization-header,
.metrics-header,
.qualification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.metrics-container,
.qualification-card {
  background: rgba(6, 18, 36, 0.78);
  border: 1px solid rgba(66, 195, 255, 0.18);
  border-radius: 18px;
  padding: 24px;
}

.metrics-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.metric-item {
  padding: 16px 18px;
  border-radius: 14px;
  background: rgba(8, 22, 44, 0.85);
  border: 1px solid rgba(66, 195, 255, 0.18);
}

.action-button,
.download-buttons .el-button,
.predict-button,
.download-button {
  border-radius: 12px;
}

.chart-wrapper {
  background: rgba(8, 22, 44, 0.85);
  border-radius: 16px;
  padding: 16px;
  border: 1px solid rgba(66, 195, 255, 0.18);
}

.metrics-chart-wrapper {
  height: 480px;
}

.log-section {
  margin-top: 24px;
}

.daily-metrics-container,
.qualification-container {
  margin-top: 24px;
}

@media (max-width: 1280px) {
  .workflow-layout {
    grid-template-columns: 1fr;
  }
}
</style> 