<template>
  <DigitalPage>
    <div class="physical-simulation">
      <section class="simulation-hero digital-panel">
        <div class="simulation-hero__content">
          <p class="hero-eyebrow">物理仿真</p>
          <h1 class="hero-title">物理仿真数据展示</h1>
          <p class="hero-subtitle">通过双线性插值计算任意工况下的风机表现</p>
          <div class="hero-meta">
            <span class="digital-status-chip">当前场站：{{ currentWindFarmDisplay }}</span>
            <el-tag
              v-if="selectedFarm"
              type="info"
              effect="plain"
              size="small"
            >
              已选择风电场：{{ selectedFarm }}
            </el-tag>
          </div>
        </div>
        <div class="simulation-hero__metrics">
          <div
            v-for="metric in heroMetrics"
            :key="metric.label"
            class="simulation-hero-metric"
          >
            <span class="metric-label">{{ metric.label }}</span>
            <span class="metric-value">
              {{ metric.value }}
              <span v-if="metric.unit" class="metric-unit">{{ metric.unit }}</span>
            </span>
            <span v-if="metric.meta" class="metric-meta">{{ metric.meta }}</span>
          </div>
        </div>
      </section>

      <div class="simulation-content">
        <div class="dataset-upload-section">
          <el-card class="dataset-upload-card digital-panel" shadow="hover">
          <template #header>
            <div class="dataset-upload-header">
              <div class="header-left">
                <span class="icon-bubble">
                  <el-icon><UploadFilled /></el-icon>
                </span>
                <div class="header-copy">
                  <span class="title">仿真数据集管理</span>
                  <span class="subtitle">上传风机、工况与测点数据以支撑物理仿真计算</span>
                </div>
              </div>
              <el-tag type="info" effect="dark" size="small">当前场站：{{ currentWindFarmDisplay }}</el-tag>
            </div>
          </template>
          <el-tabs v-model="activeUploadTab" class="dataset-upload-tabs" type="border-card">
            <el-tab-pane
              v-for="entry in datasetUploadEntries"
              :key="entry.key"
              :name="entry.key"
            >
              <template #label>
                <span class="tab-label">{{ entry.title }}</span>
              </template>
              <el-row :gutter="24" class="dataset-upload-pane">
                <el-col :xs="24" :lg="14">
                  <div class="upload-panel">
                    <p class="upload-subtitle">{{ entry.subtitle }}</p>
                    <ul class="upload-tips">
                      <li v-for="tip in entry.tips" :key="tip">{{ tip }}</li>
                    </ul>
                    <div class="upload-drop-wrapper">
                      <el-upload
                        class="dataset-upload-dropzone"
                        drag
                        :auto-upload="false"
                        accept=".csv"
                        :limit="1"
                        :show-file-list="false"
                        :file-list="entry.state.fileList"
                        @change="(file, fileList) => handleDatasetFileChange(entry.key, file, fileList)"
                        @remove="() => handleDatasetFileRemove(entry.key)"
                      >
                        <div class="dropzone-inner">
                          <el-icon class="dropzone-icon"><UploadFilled /></el-icon>
                          <div class="dropzone-title">拖拽或点击上传 CSV 文件</div>
                          <p class="dropzone-desc">系统会自动绑定当前场站「{{ currentWindFarmDisplay }}」</p>
                        </div>
                      </el-upload>
                    </div>

                    <transition name="fade-slide">
                      <div v-if="entry.state.file" class="selected-file-chip">
                        <div class="file-info">
                          <span class="file-name">{{ entry.state.file.name }}</span>
                          <span class="file-size">{{ (entry.state.file.size / 1024).toFixed(1) }} KB</span>
                        </div>
                        <el-button type="text" size="small" @click="resetDatasetUploadState(entry.key, { clearMessages: true })">更换文件</el-button>
                      </div>
                    </transition>

                    <div class="upload-actions">
                      <el-button
                        type="primary"
                        size="large"
                        :loading="entry.state.uploading"
                        @click="submitDatasetUpload(entry.key)"
                      >
                        {{ entry.state.uploading ? '上传中...' : '上传数据' }}
                      </el-button>
                      <el-button size="large" @click="resetDatasetUploadState(entry.key, { clearMessages: true })">清空</el-button>
                    </div>

                    <transition name="fade-slide">
                      <el-alert
                        v-if="entry.state.result"
                        type="success"
                        :title="entry.state.result?.message || '上传成功'"
                        show-icon
                        closable
                        @close="entry.state.result = null"
                      />
                    </transition>
                    <transition name="fade-slide">
                      <el-alert
                        v-if="entry.state.error"
                        type="error"
                        :title="entry.state.error"
                        show-icon
                        closable
                        @close="entry.state.error = null"
                      />
                    </transition>
                  </div>
                </el-col>
                <el-col :xs="24" :lg="10">
                  <div class="dataset-schema-panel">
                    <h4>必备字段</h4>
                    <div class="dataset-columns">
                      <div class="dataset-columns-head">
                        <span>字段名</span>
                        <span>说明</span>
                      </div>
                      <div
                        v-for="col in entry.columns"
                        :key="entry.key + col.name"
                        class="dataset-column-row"
                      >
                        <span class="col-name">{{ col.name }}</span>
                        <span class="col-desc">{{ col.description }}</span>
                      </div>
                    </div>
                  </div>
                </el-col>
              </el-row>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </div>

      <div class="main-content">
        <!-- 参数设置区域 -->
        <div class="upload-section">
          <div class="upload-card digital-panel digital-panel--interactive">
            <div class="card-header">
              <h2>选择风电场</h2>
              <div class="step-number">1</div>
            </div>
            <div class="card-content">
              <el-select
                v-model="selectedFarm"
                placeholder="请选择风电场"
                @change="handleFarmSelection"
                :loading="loadingFarms"
                style="width: 100%"
                size="large"
              >
                <el-option
                  v-for="farm in farmNames"
                  :key="farm"
                  :label="farm"
                  :value="farm"
                />
              </el-select>
            </div>
          </div>

          <div class="upload-card digital-panel digital-panel--interactive">
            <div class="card-header">
              <h2>设置目标风速</h2>
              <div class="step-number">2</div>
            </div>
            <div class="card-content">
              <el-input
                v-model.number="targetWindSpeed"
                placeholder="请输入目标风速 (m/s)"
                type="number"
                :disabled="!selectedFarm"
                size="large"
              >
                <template #suffix>m/s</template>
              </el-input>
            </div>
          </div>

          <div class="upload-card digital-panel digital-panel--interactive">
            <div class="card-header">
              <h2>设置目标风向</h2>
              <div class="step-number">3</div>
            </div>
            <div class="card-content">
              <el-input
                v-model.number="targetWindDirection"
                placeholder="请输入目标风向 (°)"
                type="number"
                :disabled="!selectedFarm"
                size="large"
              >
                <template #suffix>°</template>
              </el-input>
            </div>
          </div>
        </div>

        <!-- 右侧操作面板 -->
        <div class="right-panel">
          <div class="action-card digital-panel">
            <div v-if="!isReadyForSimulation" class="empty-action-panel">
              <el-icon class="empty-icon"><InfoFilled /></el-icon>
              <p class="empty-text">请完成参数设置后开始仿真计算</p>
            </div>
            <div v-else class="action-buttons">
              <el-button
                type="primary"
                size="large"
                @click="runSimulation"
                :loading="loadingSimulation"
                class="action-button predict-button"
              >
                {{ loadingSimulation ? '计算中...' : '开始仿真计算' }}
              </el-button>
            </div>
          </div>

          <!-- 仿真参数显示 -->
          <div v-if="selectedFarm" class="status-card digital-panel">
            <h3>仿真参数</h3>
            <div class="card-content">
              <div class="param-item">
                <span class="param-label">风电场:</span>
                <span class="param-value">{{ selectedFarm }}</span>
              </div>
              <div class="param-item">
                <span class="param-label">目标风速:</span>
                <span class="param-value">{{ targetWindSpeed || '-' }} m/s</span>
              </div>
              <div class="param-item">
                <span class="param-label">目标风向:</span>
                <span class="param-value">{{ targetWindDirection || '-' }}°</span>
              </div>
              <div class="param-item">
                <span class="param-label">风机数量:</span>
                <span class="param-value">{{ farmTurbines.length }} 台</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 仿真结果展示区域 -->
      <div v-if="simulationResults.length > 0" class="visualization-section">
        <div class="visualization-header">
          <h3 class="section-title">仿真结果</h3>
        </div>
        
        <div class="results-container">
          <!-- 可视化图表 -->
          <div class="chart-card digital-panel digital-panel--interactive">
            <div class="card-header">
              <h3>风电场布局及仿真风速分布</h3>
            </div>
            <div class="chart-container">
              <div ref="plot" style="width: 100%; height: 500px;"></div>
            </div>
          </div>

          <!-- 数据表格 -->
          <div class="table-card digital-panel digital-panel--interactive">
            <div class="card-header">
              <h3>详细仿真数据</h3>
              <el-button type="primary" size="small" @click="exportResults">
                <el-icon><Download /></el-icon>
                导出数据
              </el-button>
            </div>
            <div class="table-container">
              <el-table
                :data="simulationResults"
                style="width: 100%"
                v-loading="loadingSimulation"
                stripe
                border
                height="452"
                :scroll-with-animation="true"
              >
                <el-table-column prop="turbine_number" label="风机编号" width="120" />
                <el-table-column prop="longitude" label="经度" width="120" />
                <el-table-column prop="latitude" label="纬度" width="120" />
                <el-table-column prop="simulated_wind_speed" label="仿真风速 (m/s)" width="150" />
                <el-table-column prop="simulated_power_output" label="仿真功率 (kW)" width="150" />
              </el-table>
            </div>
          </div>
        </div>
      </div>
    </div>
    </div>
  </DigitalPage>
</template>

<script>
import axiosInstance from '../api/axios';
import Plotly from 'plotly.js-dist-min';
import { ElMessage } from 'element-plus';
import { InfoFilled, Download, UploadFilled } from '@element-plus/icons-vue';
import { useWindFarmStore } from '@/store/windFarm';
import DigitalPage from './common/DigitalPage.vue';

export default {
  name: 'PhysicalSimulation',
  components: {
    DigitalPage,
    InfoFilled,
    Download,
    UploadFilled,
  },
  data() {
    const windFarmStore = useWindFarmStore();
    return {
      windFarmStore,
      farmNames: [],
      selectedFarm: null,
      targetWindSpeed: null,
      targetWindDirection: null,
      
      loadingFarms: false,
      loadingSimulation: false,
      
      farmConditions: [],
      farmTurbines: [],
      
      simulationResults: [],
      activeUploadTab: 'turbines',
      datasetUploadMeta: {
        turbines: {
          title: '风机基础数据',
          subtitle: '用于描述风机的经纬度、编号等静态信息',
          endpoint: 'physical_simulation/turbines/batch',
          tips: ['CSV文件需包含当前场站名称', '重复风机编号将执行更新而非新增'],
          columns: [
            { name: 'farm_name', description: '风电场名称（需与列表一致）' },
            { name: 'turbine_number', description: '风机编号（同场站内唯一）' },
            { name: 'longitude', description: '风机经度 (°)' },
            { name: 'latitude', description: '风机纬度 (°)' },
          ],
        },
        conditions: {
          title: '工况条件数据',
          subtitle: '风速 / 风向 离散节点，支持后续插值计算',
          endpoint: 'physical_simulation/conditions/batch',
          tips: ['同一风电场下相同风速+风向组合将被更新', '可附加 is_interpolated 列标记数据来源'],
          columns: [
            { name: 'farm_name', description: '风电场名称（需与列表一致）' },
            { name: 'wind_speed', description: '测点风速 (m/s)' },
            { name: 'wind_direction', description: '测点风向 (°)' },
            { name: 'is_interpolated', description: '是否插值结果（可选，0/1）' },
          ],
        },
        readings: {
          title: '仿真读数数据',
          subtitle: '与工况及风机关联的测点/仿真输出',
          endpoint: 'physical_simulation/readings/batch',
          tips: ['condition_id 与 turbine_id 需已存在', '未提供的列保持原值不变'],
          columns: [
            { name: 'condition_id', description: '关联工况条件 ID' },
            { name: 'turbine_id', description: '关联风机 ID' },
            { name: 'turbine_wind_speed', description: '风机入流风速 (m/s)' },
            { name: 'power_output', description: '风机输出功率 (kW，可选)' },
          ],
        },
      },
      datasetUploadState: {
        turbines: { file: null, fileList: [], uploading: false, result: null, error: null },
        conditions: { file: null, fileList: [], uploading: false, result: null, error: null },
        readings: { file: null, fileList: [], uploading: false, result: null, error: null },
      },
    };
  },
  computed: {
    selectedWindFarmCode() {
      return this.windFarmStore.selectedWindFarm.value;
    },
    currentWindFarmRecord() {
      const finder = this.windFarmStore.findWindFarmByCode;
      if (typeof finder === 'function') {
        return finder(this.selectedWindFarmCode);
      }
      return null;
    },
    currentWindFarmDisplay() {
      const record = this.currentWindFarmRecord;
      if (record) {
        return record.farm_name || record.farm_code || this.selectedWindFarmCode;
      }
      return this.selectedFarm || this.selectedWindFarmCode || '未选择场站';
    },
    isReadyForSimulation() {
      return this.selectedFarm && 
             this.targetWindSpeed !== null && 
             this.targetWindDirection !== null &&
             this.targetWindSpeed !== '' &&
             this.targetWindDirection !== '';
    },
    datasetUploadEntries() {
      return Object.entries(this.datasetUploadMeta).map(([key, meta]) => ({
        key,
        ...meta,
        state: this.datasetUploadState[key],
      }));
    },
    heroMetrics() {
      const turbineCount = this.farmTurbines.length;
      const conditionCount = this.farmConditions.length;
      const resultCount = this.simulationResults.length;
      return [
        {
          label: '绑定风机',
          value: turbineCount || '—',
          unit: turbineCount ? '台' : '',
          meta: this.selectedFarm ? `场站：${this.selectedFarm}` : '等待选择场站',
        },
        {
          label: '工况节点',
          value: conditionCount || '—',
          unit: conditionCount ? '个' : '',
          meta: conditionCount ? '用于插值的节点' : '尚未上传工况数据',
        },
        {
          label: '仿真结果',
          value: resultCount || '—',
          unit: resultCount ? '条' : '',
          meta: this.loadingSimulation ? '正在计算' : (resultCount ? '最新一次仿真输出' : '尚未运行仿真'),
        },
      ];
    },
  },
  watch: {
    selectedWindFarmCode(newCode, oldCode) {
      if (newCode === oldCode) {
        return;
      }
      this.reloadForSelectedWindFarm();
    }
  },
  mounted() {
    this.reloadForSelectedWindFarm();
  },
  methods: {
    handleDatasetFileChange(key, uploadFile, uploadFiles) {
      const state = this.datasetUploadState[key];
      state.fileList = uploadFiles.slice(-1);
      state.file = uploadFile?.raw || null;
      state.result = null;
      state.error = null;
    },
    handleDatasetFileRemove(key) {
      this.resetDatasetUploadState(key, { clearMessages: true });
    },
    resetDatasetUploadState(key, options = {}) {
      const state = this.datasetUploadState[key];
      const { clearMessages = false } = options;
      state.file = null;
      state.fileList = [];
      if (clearMessages) {
        state.result = null;
        state.error = null;
      }
    },
    async submitDatasetUpload(key) {
      const state = this.datasetUploadState[key];
      const meta = this.datasetUploadMeta[key];
      if (!meta || !state) {
        ElMessage.error('未知的数据集类型');
        return;
      }
      if (!state.file) {
        ElMessage.warning('请先选择要上传的 CSV 文件');
        return;
      }

      const formData = new FormData();
      formData.append('file', state.file);
      if (this.selectedWindFarmCode) {
        formData.append('wind_farm_code', this.selectedWindFarmCode);
      }
      if (this.selectedFarm) {
        formData.append('farm_name', this.selectedFarm);
      }

      state.uploading = true;
      try {
        const response = await axiosInstance.post(meta.endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        state.result = response.data;
        state.error = null;
        state.file = null;
        state.fileList = [];
        ElMessage.success(response.data?.message || `${meta.title}上传成功`);

        if (this.selectedFarm) {
          await this.handleFarmSelection(this.selectedFarm, { syncStore: false });
        } else {
          await this.fetchFarmNames();
        }
      } catch (error) {
        console.error('submitDatasetUpload error:', error);
        const message = error.response?.data?.error || error.message || '上传失败';
        state.error = message;
        state.result = null;
        ElMessage.error(message);
      } finally {
        state.uploading = false;
      }
    },
    async reloadForSelectedWindFarm() {
      this.targetWindSpeed = null;
      this.targetWindDirection = null;
      this.simulationResults = [];
      Object.keys(this.datasetUploadState).forEach(key => {
        this.resetDatasetUploadState(key, { clearMessages: true });
      });
      await this.fetchFarmNames();

      const defaultName = this.getDefaultFarmName();
      if (defaultName) {
        this.selectedFarm = defaultName;
        await this.handleFarmSelection(defaultName, { syncStore: false });
      } else {
        this.selectedFarm = null;
        this.farmConditions = [];
        this.farmTurbines = [];
      }
    },

    getDefaultFarmName() {
      const record = this.currentWindFarmRecord;
      if (record && record.farm_name) {
        return record.farm_name;
      }
      return this.farmNames.length > 0 ? this.farmNames[0] : null;
    },

    findFarmRecordByName(farmName) {
      if (!farmName || !this.windFarmStore || !this.windFarmStore.windFarms) {
        return null;
      }
      const farms = this.windFarmStore.windFarms.value || [];
      return farms.find(
        (farm) => farm.farm_name === farmName || farm.farm_code === farmName
      ) || null;
    },

    async fetchFarmNames() {
      this.loadingFarms = true;
      try {
        const params = {};
        if (this.selectedWindFarmCode) {
          params.wind_farm_code = this.selectedWindFarmCode;
        }
        const response = await axiosInstance.get('physical_simulation/conditions', { params });
        const uniqueFarms = [...new Set(response.data.map(item => item.farm_name))];
        this.farmNames = uniqueFarms;
        const defaultName = this.getDefaultFarmName();
        if (defaultName && !this.farmNames.includes(defaultName)) {
          this.farmNames.unshift(defaultName);
        }
      } catch (error) {
        console.error('Error fetching farm names:', error);
        ElMessage.error('获取风电场列表失败');
      } finally {
        this.loadingFarms = false;
      }
    },
    
    async handleFarmSelection(farmName, options = {}) {
      const { syncStore = true } = options;
      if (!farmName) {
        this.farmConditions = [];
        this.farmTurbines = [];
        return;
      }

      if (syncStore) {
        const record = this.findFarmRecordByName(farmName);
        if (record && record.farm_code && record.farm_code !== this.selectedWindFarmCode) {
          this.windFarmStore.setSelectedWindFarm(record.farm_code);
          return;
        }
      }
      
      this.loadingSimulation = true;
      try {
        const [conditionsRes, turbinesRes] = await Promise.all([
          axiosInstance.get('physical_simulation/conditions', {
            params: {
              farm_name: farmName,
              wind_farm_code: this.selectedWindFarmCode
            }
          }),
          axiosInstance.get('physical_simulation/turbines', {
            params: {
              farm_name: farmName,
              wind_farm_code: this.selectedWindFarmCode
            }
          }),
        ]);
        this.farmConditions = conditionsRes.data;
        this.farmTurbines = turbinesRes.data;
        this.selectedFarm = farmName;
        
        ElMessage.success(`已加载 ${this.farmTurbines.length} 台风机数据`);
      } catch (error) {
        console.error(`Error fetching data for farm ${farmName}:`, error);
        ElMessage.error('获取风电场数据失败');
      } finally {
        this.loadingSimulation = false;
      }
    },
    
    findSurroundingConditions() {
      const windSpeeds = [...new Set(this.farmConditions.map(c => c.wind_speed))].sort((a, b) => a - b);
      const windDirections = [...new Set(this.farmConditions.map(c => c.wind_direction))].sort((a, b) => a - b);

      const findBounds = (arr, target) => {
        // 检查是否精确匹配现有数据点
        if (arr.includes(target)) {
          return { lower: target, upper: target, isExact: true };
        }
        
        const upper = arr.find(v => v > target);
        const lower = arr.slice().reverse().find(v => v < target);
        return { lower, upper, isExact: false };
      };

      const wsBounds = findBounds(windSpeeds, this.targetWindSpeed);
      const wdBounds = findBounds(windDirections, this.targetWindDirection);

      if ([wsBounds.lower, wsBounds.upper, wdBounds.lower, wdBounds.upper].some(v => v === undefined)) {
        ElMessage.warning("输入的目标工况超出现有数据范围，无法进行插值");
        return null;
      }

      const getConditionId = (ws, wd) => this.farmConditions.find(c => c.wind_speed === ws && c.wind_direction === wd);
      
      // 处理精确匹配的情况
      if (wsBounds.isExact && wdBounds.isExact) {
        // 两个维度都精确匹配，直接返回该条件
        const exactCondition = getConditionId(wsBounds.lower, wdBounds.lower);
        return { 
          Q11: exactCondition, Q12: exactCondition, Q21: exactCondition, Q22: exactCondition,
          wsBounds, wdBounds, isExactMatch: true 
        };
      } else if (wsBounds.isExact) {
        // 风速精确匹配，只需在风向上插值
        const Q11 = getConditionId(wsBounds.lower, wdBounds.lower);
        const Q12 = getConditionId(wsBounds.lower, wdBounds.upper);
        return { 
          Q11, Q12, Q21: Q11, Q22: Q12,
          wsBounds, wdBounds, isWindSpeedExact: true 
        };
      } else if (wdBounds.isExact) {
        // 风向精确匹配，只需在风速上插值
        const Q11 = getConditionId(wsBounds.lower, wdBounds.lower);
        const Q21 = getConditionId(wsBounds.upper, wdBounds.lower);
        return { 
          Q11, Q12: Q11, Q21, Q22: Q21,
          wsBounds, wdBounds, isWindDirectionExact: true 
        };
      } else {
        // 常规双线性插值情况
        const Q11 = getConditionId(wsBounds.lower, wdBounds.lower);
        const Q12 = getConditionId(wsBounds.lower, wdBounds.upper);
        const Q21 = getConditionId(wsBounds.upper, wdBounds.lower);
        const Q22 = getConditionId(wsBounds.upper, wdBounds.upper);
        
        if (!Q11 || !Q12 || !Q21 || !Q22) {
          ElMessage.warning("数据网格不完整，缺少必要的角点数据，无法进行插值");
          return null;
        }
        
        return { Q11, Q12, Q21, Q22, wsBounds, wdBounds };
      }
    },
    
    linearInterpolate(p1, p2, x) {
      const [x1, y1] = p1;
      const [x2, y2] = p2;
      
      // 处理边界情况，避免除零错误
      if (Math.abs(x2 - x1) < 1e-10) {
        return y1; // 如果两点x坐标相同，返回y1
      }
      
      return y1 + (y2 - y1) * (x - x1) / (x2 - x1);
    },
    
    async runSimulation() {
      this.loadingSimulation = true;
      this.simulationResults = [];

      const surrounding = this.findSurroundingConditions();
      if (!surrounding) {
        this.loadingSimulation = false;
        return;
      }
      
      const { Q11, Q12, Q21, Q22, wsBounds, wdBounds, isExactMatch, isWindSpeedExact, isWindDirectionExact } = surrounding;

      try {
        // 获取所有需要的读数数据
        const uniqueConditions = [...new Set([Q11, Q12, Q21, Q22].map(q => q.condition_id))];
        const readingPromises = uniqueConditions.map(conditionId => 
          axiosInstance.get('physical_simulation/readings', {
            params: { condition_id: conditionId }
          })
        );
        const readingResponses = await Promise.all(readingPromises);
        
        // 创建条件ID到读数数据的映射
        const readingsMap = {};
        uniqueConditions.forEach((conditionId, index) => {
          readingsMap[conditionId] = readingResponses[index].data;
        });

        const results = this.farmTurbines.map(turbine => {
          const getReadingForTurbine = (conditionId, turbineId) => 
            readingsMap[conditionId].find(r => r.turbine_id === turbineId);

          const tQ11 = getReadingForTurbine(Q11.condition_id, turbine.turbine_id);
          const tQ12 = getReadingForTurbine(Q12.condition_id, turbine.turbine_id);
          const tQ21 = getReadingForTurbine(Q21.condition_id, turbine.turbine_id);
          const tQ22 = getReadingForTurbine(Q22.condition_id, turbine.turbine_id);

          if (!tQ11 || !tQ12 || !tQ21 || !tQ22) {
            return null;
          }

          let final_ws, final_power;

          if (isExactMatch) {
            // 精确匹配，直接使用数据
            final_ws = tQ11.turbine_wind_speed;
            final_power = tQ11.power_output || 0;
          } else if (isWindSpeedExact) {
            // 只在风向上插值
            final_ws = this.linearInterpolate(
              [wdBounds.lower, tQ11.turbine_wind_speed], 
              [wdBounds.upper, tQ12.turbine_wind_speed], 
              this.targetWindDirection
            );
            final_power = this.linearInterpolate(
              [wdBounds.lower, tQ11.power_output || 0], 
              [wdBounds.upper, tQ12.power_output || 0], 
              this.targetWindDirection
            );
          } else if (isWindDirectionExact) {
            // 只在风速上插值
            final_ws = this.linearInterpolate(
              [wsBounds.lower, tQ11.turbine_wind_speed], 
              [wsBounds.upper, tQ21.turbine_wind_speed], 
              this.targetWindSpeed
            );
            final_power = this.linearInterpolate(
              [wsBounds.lower, tQ11.power_output || 0], 
              [wsBounds.upper, tQ21.power_output || 0], 
              this.targetWindSpeed
            );
          } else {
            // 双线性插值计算风速
            const r1_ws = this.linearInterpolate([wsBounds.lower, tQ11.turbine_wind_speed], [wsBounds.upper, tQ21.turbine_wind_speed], this.targetWindSpeed);
            const r2_ws = this.linearInterpolate([wsBounds.lower, tQ12.turbine_wind_speed], [wsBounds.upper, tQ22.turbine_wind_speed], this.targetWindSpeed);
            final_ws = this.linearInterpolate([wdBounds.lower, r1_ws], [wdBounds.upper, r2_ws], this.targetWindDirection);

            // 双线性插值计算功率
            const r1_power = this.linearInterpolate([wsBounds.lower, tQ11.power_output || 0], [wsBounds.upper, tQ21.power_output || 0], this.targetWindSpeed);
            const r2_power = this.linearInterpolate([wsBounds.lower, tQ12.power_output || 0], [wsBounds.upper, tQ22.power_output || 0], this.targetWindSpeed);
            final_power = this.linearInterpolate([wdBounds.lower, r1_power], [wdBounds.upper, r2_power], this.targetWindDirection);
          }

          return {
            ...turbine,
            simulated_wind_speed: final_ws.toFixed(3),
            simulated_power_output: final_power.toFixed(3),
          };
        }).filter(Boolean);

        this.simulationResults = results;
        this.drawPlot();
        
        ElMessage.success(`仿真计算完成，共计算 ${results.length} 台风机数据`);

      } catch (error) {
        console.error("Error during simulation:", error);
        ElMessage.error("仿真计算过程中发生错误");
      } finally {
        this.loadingSimulation = false;
      }
    },
    
    drawPlot() {
      this.$nextTick(() => {
        this.$nextTick(() => {
          // 确保DOM元素存在
          if (!this.$refs.plot) {
            console.error('Plot element not found');
            // 如果元素不存在，稍后重试
            setTimeout(() => this.drawPlot(), 100);
            return;
          }

          const trace = {
            x: this.simulationResults.map(r => r.longitude),
            y: this.simulationResults.map(r => r.latitude),
            text: this.simulationResults.map(r => `风机: ${r.turbine_number}<br>风速: ${r.simulated_wind_speed} m/s<br>功率: ${r.simulated_power_output} kW`),
            mode: 'markers',
            marker: {
              size: 15,
              color: this.simulationResults.map(r => parseFloat(r.simulated_wind_speed)),
              colorscale: 'Viridis',
              showscale: true,
              colorbar: {
                title: '仿真风速 (m/s)'
              }
            },
            type: 'scatter'
          };

          const layout = {
            title: `${this.selectedFarm} - 仿真结果分布图`,
            xaxis: { title: '经度' },
            yaxis: { title: '纬度', scaleanchor: "x", scaleratio: 1 },
            hovermode: 'closest',
            margin: { t: 50, l: 50, r: 50, b: 50 }
          };

          try {
            Plotly.newPlot(this.$refs.plot, [trace], layout, {responsive: true});
          } catch (error) {
            console.error('Error creating plot:', error);
            ElMessage.error('图表绘制失败');
          }
        });
      });
    },
    
    exportResults() {
      if (this.simulationResults.length === 0) {
        ElMessage.warning('暂无数据可导出');
        return;
      }
      
      // CSV导出功能，添加BOM以解决中文乱码问题
      const headers = ['风机编号', '经度', '纬度', '仿真风速(m/s)', '仿真功率(kW)'];
      const csvContent = [
        headers.join(','),
        ...this.simulationResults.map(row => [
          row.turbine_number,
          row.longitude,
          row.latitude,
          row.simulated_wind_speed,
          row.simulated_power_output
        ].join(','))
      ].join('\n');
      
      // 添加UTF-8 BOM标记以确保中文正确显示
      const BOM = '\uFEFF';
      const csvWithBOM = BOM + csvContent;
      
      const blob = new Blob([csvWithBOM], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${this.selectedFarm}_仿真结果_${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      
      ElMessage.success('数据导出成功');
    }
  },
};
</script>

<style scoped>
.physical-simulation {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.simulation-content {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.simulation-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.95fr);
  gap: 32px;
  padding: 32px 36px;
}

.simulation-hero__content {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-eyebrow {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.36em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.hero-title {
  margin: 0;
  font-size: 38px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.hero-subtitle {
  margin: 0;
  font-size: 16px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.simulation-hero__metrics {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  align-content: flex-start;
}

.simulation-hero-metric {
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid rgba(66, 195, 255, 0.26);
  background: linear-gradient(155deg, rgba(9, 26, 54, 0.78) 0%, rgba(6, 18, 38, 0.9) 100%);
  box-shadow: 0 24px 58px rgba(3, 18, 44, 0.55);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-label {
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.metric-value {
  font-family: 'Rajdhani', 'Inter', sans-serif;
  font-size: 30px;
  letter-spacing: 0.12em;
  color: var(--text-primary);
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.metric-unit {
  font-size: 16px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

.metric-meta {
  font-size: 12px;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.dataset-upload-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.dataset-upload-card {
  padding: 0;
}

.dataset-upload-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.dataset-upload-header .header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.icon-bubble {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(66, 195, 255, 0.35);
  background: linear-gradient(140deg, rgba(66, 195, 255, 0.2) 0%, rgba(34, 246, 170, 0.08) 100%);
  color: var(--accent-primary);
  font-size: 20px;
}

.header-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-copy .title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-primary);
}

.header-copy .subtitle {
  font-size: 13px;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.dataset-upload-tabs {
  margin-top: 18px;
}

.dataset-upload-tabs :deep(.el-tabs__header) {
  background: transparent;
  border-color: rgba(66, 195, 255, 0.22);
}

.dataset-upload-tabs :deep(.el-tabs__item) {
  color: var(--text-secondary);
  letter-spacing: 0.06em;
}

.dataset-upload-tabs :deep(.el-tabs__item.is-active) {
  color: var(--text-primary);
  font-weight: 600;
}

.dataset-upload-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.dataset-upload-pane {
  margin-top: 12px;
}

.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px;
  border-radius: 18px;
  border: 1px solid rgba(66, 195, 255, 0.22);
  background: linear-gradient(180deg, rgba(6, 22, 44, 0.75) 0%, rgba(4, 18, 36, 0.9) 100%);
  box-shadow: 0 20px 48px rgba(3, 16, 40, 0.55);
}

.upload-subtitle {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.upload-tips {
  margin: 0;
  padding-left: 18px;
  color: var(--text-muted);
  font-size: 13px;
  letter-spacing: 0.04em;
}

.upload-drop-wrapper {
  border-radius: 16px;
  overflow: hidden;
}

.dataset-upload-dropzone :deep(.el-upload) {
  width: 100%;
}

.dataset-upload-dropzone :deep(.el-upload-dragger) {
  border: 1px dashed rgba(66, 195, 255, 0.35);
  background: rgba(6, 24, 50, 0.72);
  border-radius: 16px;
  padding: 26px;
  transition: all 0.25s ease;
}

.dataset-upload-dropzone :deep(.el-upload-dragger:hover) {
  border-color: rgba(66, 195, 255, 0.65);
  box-shadow: 0 20px 46px rgba(6, 24, 52, 0.55);
}

.dropzone-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.dropzone-icon {
  font-size: 26px;
  color: var(--accent-primary);
}

.dropzone-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.04em;
}

.dropzone-desc {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.03em;
}

.selected-file-chip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(66, 195, 255, 0.28);
  background: rgba(66, 195, 255, 0.12);
}

.selected-file-chip .file-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.04em;
}

.file-size {
  font-size: 12px;
  color: var(--text-secondary);
}

.upload-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.dataset-schema-panel {
  padding: 22px;
  border-radius: 18px;
  border: 1px solid rgba(66, 195, 255, 0.2);
  background: linear-gradient(180deg, rgba(6, 22, 44, 0.65) 0%, rgba(4, 18, 36, 0.88) 100%);
  box-shadow: 0 20px 48px rgba(3, 16, 40, 0.5);
}

.dataset-schema-panel h4 {
  margin: 0 0 14px;
  font-size: 16px;
  letter-spacing: 0.08em;
  color: var(--text-primary);
}

.dataset-columns {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dataset-columns-head {
  display: grid;
  grid-template-columns: 140px 1fr;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
  opacity: 0.8;
}

.dataset-column-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(5, 20, 42, 0.55);
  border: 1px solid rgba(66, 195, 255, 0.18);
}

.col-name {
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.06em;
}

.col-desc {
  color: var(--text-secondary);
  letter-spacing: 0.03em;
  font-size: 13px;
}

.main-content {
  display: grid;
  gap: 24px;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 0.9fr);
  align-items: start;
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  letter-spacing: 0.08em;
  color: var(--text-primary);
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid rgba(66, 195, 255, 0.4);
  color: var(--accent-primary);
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.08em;
}

.card-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty-action-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 12px;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
}

.empty-icon {
  font-size: 32px;
  color: var(--accent-primary);
  opacity: 0.8;
}

.empty-text {
  margin: 0;
}

.action-buttons {
  display: flex;
  justify-content: center;
}

.predict-button {
  min-width: 220px;
}

.status-card h3 {
  margin: 0 0 16px;
  font-size: 16px;
  letter-spacing: 0.08em;
  color: var(--text-primary);
}

.status-card .card-content {
  gap: 10px;
}

.param-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.param-label {
  text-transform: uppercase;
  color: var(--text-muted);
}

.param-value {
  color: var(--text-primary);
}

.visualization-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.visualization-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  margin: 0;
  font-size: 20px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.results-container {
  display: grid;
  gap: 24px;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  align-items: stretch;
}

.chart-container,
.table-container {
  margin-top: 18px;
}

.table-container :deep(.el-table) {
  --el-table-header-bg-color: rgba(6, 22, 44, 0.9);
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.25s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 1280px) {
  .simulation-hero {
    grid-template-columns: 1fr;
  }

  .main-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .simulation-hero {
    padding: 26px;
  }

  .results-container {
    grid-template-columns: 1fr;
  }
}
</style> 