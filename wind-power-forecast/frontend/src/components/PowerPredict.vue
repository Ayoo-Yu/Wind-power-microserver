<template>
  <DigitalPage>
    <DigitalHero
      eyebrow="POWER FORECAST PIPELINE"
      title="功率预测"
      subtitle="多源数据驱动的功率预测流程"
      :metrics="heroMetrics"
    >
      <template #meta>
        <span class="digital-status-chip">当前场站：{{ currentWindFarmDisplay || '未选择' }}</span>
      </template>
    </DigitalHero>

    <div class="workflow-layout">
      <div class="upload-grid">
        <!-- 数据集上传区域 -->
        <div class="upload-card glass-panel">
          <div class="card-header">
            <h2>选择预测数据集</h2>
            <div class="step-number">1</div>
          </div>
          <div class="card-content">
            <FileUploader
              :processing="processing"
              :acceptedFormats="['csv']"
              :uploadText="customUploadText_datacsv"
              @file-selected="onCsvFileSelected"
            />
            <FileInfo 
              :fileInfo="csvfileInfo" 
              @remove-file="removeSelectedCsvFile"
              @start-upload="csvHandleManualUpload"
            />
          </div>
        </div>

        <!-- 模型上传区域 -->
        <div class="upload-card glass-panel">
          <div class="card-header">
            <h2>选择预测模型</h2>
            <div class="step-number">2</div>
          </div>
          <div class="card-content">
            <FileUploader
              :processing="processing"
              :acceptedFormats="['joblib']"
              :uploadText="customUploadText_model"
              @file-selected="onModelFileSelected"
              :disabled="!csvfileId"
            />
            <FileInfo 
              :fileInfo="modelfileInfo" 
              @remove-file="removeSelectedModelFile"
              @start-upload="modelHandleManualUpload"
            />
          </div>
        </div>

        <!-- 归一化模型上传区域 -->
        <div class="upload-card glass-panel">
          <div class="card-header">
            <h2>选择归一化模型</h2>
            <div class="step-number">3</div>
          </div>
          <div class="card-content">
            <FileUploader
              :processing="processing"
              :acceptedFormats="['joblib']"
              :uploadText="customUploadText_scaler"
              @file-selected="onScalerFileSelected"
              :disabled="!modelfileId"
            />
            <FileInfo 
              :fileInfo="scalerfileInfo"
              @remove-file="removeSelectedScalerFile"
              @start-upload="scalerHandleManualUpload"
            />
          </div>
        </div>
      </div>

      <div class="workflow-sidebar">
        <!-- 步骤提示 -->
        <div class="status-card glass-panel">
          <h3>预测文件ID</h3>
          <div class="card-content">
            <StepHintBox 
              :csvfileid="csvfileId" 
              :modelfileid="modelfileId" 
              :scalerfileid="scalerfileId"
            />
            <!-- 一键上传按钮 -->
            <div v-if="selectedCsvFile && selectedModelFile && selectedScalerFile && !csvfileId && !modelfileId && !scalerfileId" class="one-click-upload">
              <button 
                type="button" 
                class="action-button one-click-button"
                @click="handleOneClickUpload"
                :disabled="processing || uploading"
              >
                {{ uploading ? '上传中...' : '一键上传所有文件' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-card glass-panel">
          <div v-if="!csvfileId || !modelfileId || !scalerfileId" class="empty-action-panel">
            <el-icon class="empty-icon"><InfoFilled /></el-icon>
            <p class="empty-text">请完成所有文件上传后开始预测</p>
          </div>
          <div v-else class="action-buttons">
            <button 
              type="button" 
              class="action-button predict-button"
              @click="handlePredict"
              :disabled="processing"
            >
              {{ processing ? '预测中...' : '开始预测' }}
            </button>
            <button 
              v-if="downloadUrl"
              type="button" 
              class="action-button download-button"
              @click="downloadFile(downloadUrl)"
            >
              下载预测结果
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 预测结果可视化区域 -->
    <div v-if="predictions.length > 0" class="visualization-section glass-panel">
      <div class="visualization-header">
        <h3 class="section-title">预测结果可视化</h3>
        <div class="visualization-controls">
          <el-checkbox v-model="showActualValues" @change="handleShowActualValues">
            显示实测值对比
          </el-checkbox>
          <el-button 
            v-if="showActualValues && actualValues.length > 0"
            type="primary"
            size="small"
            @click="calculateMetrics"
          >
            计算评估指标
          </el-button>
        </div>
      </div>
      <div class="chart-container">
        <div ref="chartRef" style="width: 100%; height: 400px;"></div>
      </div>
      <div v-if="metrics" class="metrics-container">
        <div class="metrics-header">
          <h4>评估指标</h4>
          <div class="download-metrics">
            <el-button type="text" size="small" @click="downloadMetrics">
              <el-icon><Download /></el-icon>
              导出指标
            </el-button>
          </div>
        </div>
        <div class="metrics-grid">
          <div class="metric-item">
            <span class="metric-label">MAE:</span>
            <span class="metric-value">{{ metrics.mae.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">MSE:</span>
            <span class="metric-value">{{ metrics.mse.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">RMSE:</span>
            <span class="metric-value">{{ metrics.rmse.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">ACC:</span>
            <span class="metric-value">{{ metrics.acc.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">K:</span>
            <span class="metric-value">{{ metrics.k.toFixed(2) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">R²:</span>
            <span class="metric-value">{{ metrics.r2.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 日志查看器 -->
    <div class="log-section glass-panel" :class="{ 'log-expanded': logVisible }">
      <div class="log-header" @click="toggleLogVisible">
        <h3 class="section-title">预测日志</h3>
        <el-button type="text" class="toggle-button">
          {{ logVisible ? '收起' : '展开' }}
          <el-icon class="toggle-icon" :class="{ 'is-rotate': logVisible }">
            <arrow-down />
          </el-icon>
        </el-button>
      </div>
      <div v-if="logVisible" class="log-content-wrapper">
        <div v-if="!csvfileInfo" class="empty-log-panel">
          <el-icon class="empty-icon"><InfoFilled /></el-icon>
          <p class="empty-text">暂无日志信息</p>
        </div>
        <LogViewer 
          v-else
          :logs="logs" 
          @clear-logs="clearLogs" 
        />
      </div>
    </div>
  </DigitalPage>
</template>

<script>
import { upload_predict_csv,upload_model,upload_scaler,predict, getActualValues } from '@/services/apiService';  // 使用 API 服务
import { useSocket } from '@/composables/useSocket'; // 使用组合式 API 来管理 WebSocket
import FileUploader from './FileUploader.vue';
import StepHintBox from "./StepHintBox.vue";
import FileInfo from './FileInfo.vue';
import LogViewer from './LogViewer.vue';
import * as echarts from 'echarts';
import { ArrowDown, InfoFilled, Download } from '@element-plus/icons-vue';
import axiosInstance from '../api/axios';
import { useWindFarmStore } from '@/store/windFarm';
import DigitalPage from './common/DigitalPage.vue'
import DigitalHero from './common/DigitalHero.vue'

const rawBaseURL = axiosInstance.defaults && axiosInstance.defaults.baseURL ? axiosInstance.defaults.baseURL : '';
const API_BASE_PATH = rawBaseURL.replace(/\/$/, '');
const SOCKET_BASE_URL = window.location.origin;
const SOCKET_PATH = API_BASE_PATH ? `${API_BASE_PATH}/socket.io` : '/socket.io';

const windFarmStore = useWindFarmStore();

function buildDownloadUrl(basePath, path) {
  if (!path) {
    return '';
  }
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const normalizedBase = basePath || '';
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
}

export default {
  name: 'PowerPredict',
  components: {
    DigitalPage,
    DigitalHero,
    FileUploader,
    FileInfo,
    LogViewer,
    StepHintBox,
    ArrowDown,
    InfoFilled,
    Download
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
      const datasetStatus = this.csvfileId
        ? '已就绪'
        : this.selectedCsvFile
          ? '待上传'
          : '未选择'

      const modelStatus = this.modelfileId
        ? '已就绪'
        : this.selectedModelFile
          ? '待上传'
          : '未选择'

      const scalerStatus = this.scalerfileId
        ? '已就绪'
        : this.selectedScalerFile
          ? '待上传'
          : '未选择'

      const predictionStatus = this.processing
        ? 'RUNNING'
        : this.downloadUrl
          ? 'COMPLETED'
          : 'IDLE'

      return [
        {
          id: 'dataset',
          label: '预测数据集',
          value: datasetStatus,
          meta: this.csvfileInfo?.name || 'CSV 文件',
        },
        {
          id: 'model',
          label: '预测模型',
          value: modelStatus,
          meta: this.modelfileInfo?.name || 'Model 文件',
        },
        {
          id: 'scaler',
          label: '归一化模型',
          value: scalerStatus,
          meta: this.scalerfileInfo?.name || 'Scaler 文件',
        },
        {
          id: 'status',
          label: '预测状态',
          value: predictionStatus,
          meta: this.predictions.length ? `条目 ${this.predictions.length}` : '等待执行',
        },
      ]
    },
  },
  watch: {
    selectedWindFarm() {
      this.handleWindFarmSelectionChange();
    }
  },
  data() {
    return {
       // API地址设置
      backendBaseUrl: API_BASE_PATH,
      socketBaseUrl: SOCKET_BASE_URL,
      socketPath: SOCKET_PATH,
      customUploadText_datacsv: '选择预测数据集',
      customUploadText_model: '请选择预测模型',
      customUploadText_scaler: '请选择归一化模型',
      csvfileId: null,
      modelfileId: null,
      scalerfileId: null,
      selectedCsvFile: null,
      selectedModelFile: null,
      selectedScalerFile: null,
      uploading: false,
      uploadProgress: 0,
      csvfileInfo: null,
      modelfileInfo: null,
      scalerfileInfo: null,
      downloadUrl: '',
      logs: '',
      processing: false,
      socket: null,
      predictions: [],
      actualValues: [],
      showActualValues: false,
      metrics: null,
      chart: null,
      logVisible: false,
    };
  },
  methods: {
    handleWindFarmSelectionChange() {
      this.$message.info(`已切换到场站：${this.currentWindFarmDisplay}`);
      ['Csv', 'Model', 'Scaler'].forEach(type => this.resetState(type));
      this.predictions = [];
      this.actualValues = [];
      this.showActualValues = false;
      this.metrics = null;
      this.downloadUrl = '';
      this.clearLogs();
      if (this.socket) {
        try {
          this.socket.disconnect();
        } catch (error) {
          console.warn('断开socket失败:', error);
        }
        this.socket = null;
      }
    },
    composeDownloadUrl(path) {
      return buildDownloadUrl(this.backendBaseUrl, path);
    },
    // 模型文件处理
    onModelFileSelected(file) {
      this.onFileSelected(file, 'Model');
    },
    modelHandleUploadSuccess(response) {
      this.handleUploadSuccess(response, 'Model', '模型文件上传成功，请继续选择本地归一化文件！');
    },
    removeSelectedModelFile() {
      this.removeSelectedFile('Model');
    },
    modelHandleManualUpload() {
      this.handleManualUpload(
        'Model',
        '请先选择一个文件！',
        this.modelHandleUploadSuccess
      );
    },

    // Scaler文件处理
    onScalerFileSelected(file) {
      this.onFileSelected(file, 'Scaler');
    },
    scalerHandleUploadSuccess(response) {
      this.handleUploadSuccess(response, 'Scaler', '归一化模型文件上传成功，请点击"开始预测"以执行预测！');
    },
    removeSelectedScalerFile() {
      this.removeSelectedFile('Scaler');
    },
    scalerHandleManualUpload() {
      this.handleManualUpload(
        'Scaler',
        '请先选择一个文件！',
        this.scalerHandleUploadSuccess
      );
    },
    // Csv文件处理
    onCsvFileSelected(file) {
      this.onFileSelected(file, 'Csv');
    },
    csvHandleUploadSuccess(response) {
      this.handleUploadSuccess(response, 'Csv', 'Csv文件选择成功，请继续选择本地模型文件！');
    },
    removeSelectedCsvFile() {
      this.removeSelectedFile('Csv');
    },
    csvHandleManualUpload() {
      this.handleManualUpload(
        'Csv',
        '请选择一个不同的文件！',
        this.csvHandleUploadSuccess
      );
    },

    onFileSelected(file, type) {
      this.resetState(type);
      this[`selected${type}File`] = file;
      this[`${type.toLowerCase()}fileInfo`] = {
        name: file.name,
        size: file.size,
        type: type === 'Csv' ? file.type : 'joblib',
        uploadDate: new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }),
      };
      this.initializeSocket();
    },

    handleUploadSuccess(response, type, successMessage) {
      this.uploading = false;
      this.uploadProgress = 0;
      if (response.file_id) {
        this[`${type.toLowerCase()}fileId`] = response.file_id;
        this.$message.success(successMessage);
      }
      this[`selected${type}File`] = null;
    },

    handleUploadError(error) {
      this.uploading = false;
      this.uploadProgress = 0;
      console.error('文件上传失败:', error);
      this.$message.error(`文件上传失败：${error.message || '未知错误'}`);
    },

    removeSelectedFile(type) {
      this.resetState(type);
      this.$message.info('已删除选中的文件。');
    },

    handleManualUpload(type, errorMessage, successCallback) {
      const file = this[`selected${type}File`];
      if (!file) {
        this.$message.error(errorMessage);
        return;
      }

      this.uploading = true;
      this.uploadProgress = 0;

      if (type === 'Csv') {
        upload_predict_csv(file, (progressEvent) => {
          if (progressEvent.lengthComputable) {
            this.uploadProgress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          }
        })
        .then(response => {
          successCallback(response.data);
        })
        .catch(error => {
          this.handleUploadError(error);
        });
      } else if (type === 'Model') {
        upload_model(file, (progressEvent) => {
          if (progressEvent.lengthComputable) {
            this.uploadProgress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          }
        })
        .then(response => {
          successCallback(response.data);
        })
        .catch(error => {
          this.handleUploadError(error);
        });
      } else if (type === 'Scaler') {
        upload_scaler(file, (progressEvent) => {
          if (progressEvent.lengthComputable) {
            this.uploadProgress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          }
        })
        .then(response => {
          successCallback(response.data);
        })
        .catch(error => {
          this.handleUploadError(error);
        });
      } else {
        this.$message.error('文件类型错误！');
      }
    },

    async handlePredict() {
      if (!this.csvfileId || !this.modelfileId || !this.scalerfileId) {
        this.$message.error('请先选择所有文件！');
        return;
      }
      this.processing = true;
      try {
        const response = await predict(this.csvfileId, this.modelfileId, this.scalerfileId);
        console.log('预测响应:', response.data);
        if (response.data.download_url) {
          this.downloadUrl = this.composeDownloadUrl(response.data.download_url);
          this.predictions = response.data.predictions;
          console.log('预测数据加载成功，数据长度:', this.predictions.length);
          this.$message.success('预测完成！');
          this.$nextTick(() => {
            console.log('开始初始化图表');
            this.initChart();
          });
        } else {
          this.$message.error('预测完成，但未返回下载链接。');
        }
      } catch (error) {
        console.error('预测失败:', error);
        this.$message.error(`预测失败：${error.response?.data?.error || '未知错误'}`);
      } finally {
        this.processing = false;
      }
    },

    async handleShowActualValues() {
      if (!this.showActualValues) {
        this.actualValues = [];
        this.metrics = null;
        this.updateChart();
        return;
      }

      try {
        if (!this.predictions || this.predictions.length === 0) {
          this.$message.warning('没有预测数据，无法获取对应时间段的实测值');
          this.showActualValues = false;
          return;
        }

        // 确保有有效的时间戳
        const firstTimestamp = this.predictions[0]?.Timestamp;
        const lastTimestamp = this.predictions[this.predictions.length - 1]?.Timestamp;
        
        if (!firstTimestamp || !lastTimestamp) {
          this.$message.warning('预测数据中缺少有效的时间戳');
          this.showActualValues = false;
          return;
        }

        const response = await getActualValues(firstTimestamp, lastTimestamp);
        this.actualValues = response.data.实测值 || [];
        
        if (this.actualValues.length === 0) {
          this.$message.warning('所选时间段内没有实测值数据');
          this.showActualValues = false;
          return;
        }
        
        // 验证实测值数据格式
        const hasInvalidData = this.actualValues.some(v => 
          !v.timestamp || (typeof v.power !== 'number' && isNaN(parseFloat(v.power)))
        );
        
        if (hasInvalidData) {
          console.warn('实测值数据中存在无效数据，将被过滤');
          this.actualValues = this.actualValues.filter(v => 
            v.timestamp && (typeof v.power === 'number' || !isNaN(parseFloat(v.power)))
          );
          
          if (this.actualValues.length === 0) {
            this.$message.warning('过滤后没有有效的实测值数据');
            this.showActualValues = false;
            return;
          }
        }
        
        this.updateChart();
      } catch (error) {
        console.error('获取实测值失败:', error);
        this.$message.error('获取实测值失败');
        this.showActualValues = false;
      }
    },

    initChart() {
      if (this.chart) {
        this.chart.dispose();
      }
      
      this.$nextTick(() => {
        if (this.$refs.chartRef) {
          this.chart = echarts.init(this.$refs.chartRef);
          this.updateChart();
          console.log('图表已初始化');
        } else {
          console.error('找不到图表DOM引用');
        }
      });
    },

    updateChart() {
      if (!this.chart) {
        console.error('图表实例不存在');
        return;
      }

      if (!this.predictions || this.predictions.length === 0) {
        console.error('没有预测数据');
        return;
      }

      console.log('更新图表，数据长度:', this.predictions.length);

      try {
        // 确保数据格式正确
        const timestamps = this.predictions.map(p => {
          if (!p || p.Timestamp === undefined) {
            console.warn('发现缺失时间戳数据');
            return '';
          }
          return p.Timestamp || '';
        });

        const predictedValues = this.predictions.map(p => {
          if (!p) {
            console.warn('发现无效预测数据项');
            return 0;
          }
          const value = p['Predicted Power'];
          // 确保值是数字类型
          if (value === undefined || value === null) {
            console.warn('发现缺失预测功率值');
            return 0;
          }
          return typeof value === 'number' ? value : parseFloat(value) || 0;
        });

        // 准备用于数据视图的数据
        let actualValues = [];
        if (this.showActualValues && this.actualValues && this.actualValues.length > 0) {
          actualValues = this.actualValues.map(v => {
            if (!v) return 0;
            const value = v.power;
            if (value === undefined || value === null) return 0;
            return typeof value === 'number' ? value : parseFloat(value) || 0;
          });
        }

        const option = {
          tooltip: {
            trigger: 'axis',
            formatter: function(params) {
              let result = params[0].axisValue + '<br/>';
              params.forEach(param => {
                result += param.marker + ' ' + param.seriesName + ': ' + param.value + ' MW<br/>';
              });
              return result;
            }
          },
          legend: {
            data: ['预测值'],
            top: 10
          },
          grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            top: '40px',
            containLabel: true
          },
          toolbox: {
            feature: {
              saveAsImage: {
                title: '保存为图片'
              }
            },
            right: '20px'
          },
          xAxis: {
            type: 'category',
            boundaryGap: false,
            data: timestamps,
            axisLabel: {
              rotate: 45,
              formatter: function(value) {
                if (!value) return '';
                return value.substring(5, 16); // 只显示月-日 时:分
              }
            },
            name: '时间戳'
          },
          yAxis: {
            type: 'value',
            name: '功率 (MW)',
            nameTextStyle: {
              padding: [0, 0, 0, 40]
            },
            splitLine: {
              lineStyle: {
                type: 'dashed'
              }
            }
          },
          series: [
            {
              name: '预测值',
              type: 'line',
              data: predictedValues,
              itemStyle: {
                color: '#0077ED'
              },
              lineStyle: {
                width: 2
              },
              symbol: 'circle',
              symbolSize: 6,
              smooth: true
            }
          ]
        };

        if (this.showActualValues && this.actualValues && this.actualValues.length > 0) {
          option.legend.data.push('实测值');
          option.series.push({
            name: '实测值',
            type: 'line',
            data: actualValues,
            itemStyle: {
              color: '#34C759'
            },
            lineStyle: {
              width: 2
            },
            symbol: 'circle',
            symbolSize: 6,
            smooth: true
          });
        }

        this.chart.setOption(option, true);
      } catch (error) {
        console.error('设置图表选项时出错:', error);
        this.$message.error('更新图表失败: ' + (error.message || '未知错误'));
      }
    },

    calculateMetrics() {
      if (!this.actualValues || !this.actualValues.length || !this.predictions || !this.predictions.length) {
        console.warn('无法计算评估指标：缺少实测值或预测值数据');
        return;
      }

      try {
        // 确保数据长度匹配
        if (this.actualValues.length !== this.predictions.length) {
          console.warn(`实测值和预测值数据长度不匹配: 实测值=${this.actualValues.length}, 预测值=${this.predictions.length}`);
          // 使用较短的长度
          const minLength = Math.min(this.actualValues.length, this.predictions.length);
          if (minLength === 0) {
            console.error('没有可用于计算指标的有效数据');
            return;
          }
        }

        // 提取并验证数据
        const actual = this.actualValues.map(v => {
          if (!v || v.power === undefined || v.power === null) return null;
          const power = typeof v.power === 'number' ? v.power : parseFloat(v.power);
          return isNaN(power) ? null : power;
        }).filter(v => v !== null);

        const predicted = this.predictions.map(p => {
          if (!p || p['Predicted Power'] === undefined || p['Predicted Power'] === null) return null;
          const power = typeof p['Predicted Power'] === 'number' ? p['Predicted Power'] : parseFloat(p['Predicted Power']);
          return isNaN(power) ? null : power;
        }).filter(v => v !== null);

        // 确保过滤后仍有足够的数据
        if (actual.length === 0 || predicted.length === 0) {
          console.error('过滤无效数据后没有可用于计算指标的数据');
          return;
        }

        // 使用较短的长度
        const minLength = Math.min(actual.length, predicted.length);
        const actualData = actual.slice(0, minLength);
        const predictedData = predicted.slice(0, minLength);

        // 计算MAE (平均绝对误差)
        const mae = actualData.reduce((sum, a, i) => sum + Math.abs(a - predictedData[i]), 0) / minLength;

        // 计算MSE (均方误差)
        const mse = actualData.reduce((sum, a, i) => sum + Math.pow(a - predictedData[i], 2), 0) / minLength;

        // 计算RMSE (均方根误差)
        const rmse = Math.sqrt(mse);

        // 风电场装机容量
        const wfcapacity = 453.5; // 单位：MW
        
        // 计算ACC (预测精度)
        // 按照evaluator_model.py中的公式：ACC = 1 - RMSE / wfcapacity
        const acc = 1 - rmse / wfcapacity;
        
        // 计算K (合格率)
        // 按照evaluator_model.py中的公式：
        // m_values = ((predicted - actual) / np.maximum(actual, threshold)) ** 2
        // k_value = 1 - np.sqrt(np.mean(m_values))
        const threshold = 0.2 * wfcapacity; // 防止分母为0
        let mValuesSum = 0;
        
        for (let i = 0; i < minLength; i++) {
          const denominator = Math.max(actualData[i], threshold);
          const mValue = Math.pow((predictedData[i] - actualData[i]) / denominator, 2);
          mValuesSum += mValue;
        }
        
        const k = 1 - Math.sqrt(mValuesSum / minLength);

        // 计算R² (决定系数)
        const meanActual = actualData.reduce((sum, a) => sum + a, 0) / minLength;
        const ssTot = actualData.reduce((sum, a) => sum + Math.pow(a - meanActual, 2), 0);
        const ssRes = actualData.reduce((sum, a, i) => sum + Math.pow(a - predictedData[i], 2), 0);
        const r2 = ssTot === 0 ? 0 : 1 - (ssRes / ssTot);


        const accPercent = acc;
        const kPercent = k;

        this.metrics = {
          mae: isNaN(mae) ? 0 : mae,
          mse: isNaN(mse) ? 0 : mse,
          rmse: isNaN(rmse) ? 0 : rmse,
          acc: isNaN(accPercent) || !isFinite(accPercent) ? 0 : accPercent,
          k: isNaN(kPercent) || !isFinite(kPercent) ? 0 : kPercent,
          r2: isNaN(r2) || !isFinite(r2) ? 0 : r2
        };
      } catch (error) {
        console.error('计算评估指标时出错:', error);
        this.$message.error('计算评估指标失败');
      }
    },

    // 下载文件
    downloadFile(downloadUrl) {
      window.open(downloadUrl);
    },

    // 初始化 WebSocket 连接
    initializeSocket() {
      if (this.socket) return;
 
      this.socket = useSocket(this.socketBaseUrl, { path: this.socketPath, transports: ['websocket'] });
 
      this.socket.on('connect', () => {
        console.log('Socket 连接成功');
        // 连接成功逻辑
      });
      
      this.socket.on('log', (data) => {
        const message = data.message;
        let messageClass = 'log-message';
        
        // 根据消息内容判断类型
        if (message.includes('[系统消息]')) {
          messageClass = 'system-message';
        } else if (message.includes('错误') || message.includes('失败')) {
          messageClass = 'error-message';
        } else if (message.includes('成功') || message.includes('完成')) {
          messageClass = 'success-message';
        } else if (message.includes('警告') || message.includes('注意')) {
          messageClass = 'warning-message';
        }
        
        this.logs += `<div class="${messageClass}">${message}</div>\n`;
        
        this.$nextTick(() => {
          const logContent = this.$el.querySelector('.log-content');
          if (logContent) {
            logContent.scrollTop = logContent.scrollHeight;
          }
        });
      });
    },

    clearLogs() {
      this.logs = '';
    },

    toggleLogVisible() {
      this.logVisible = !this.logVisible;
    },

    resetState(type) {
      this[`selected${type}File`] = null;
      this[`${type.toLowerCase()}fileInfo`] = null;
      this[`${type.toLowerCase()}fileId`] = null;
      this.uploading = false;
      this.uploadProgress = 0;
      this.processing = false;
      this.selectedModel = null;
      this.downloadUrl = '';
    },

    downloadMetrics() {
      if (!this.metrics) return;
      
      const metricsData = [
        ['指标', '值'],
        ['MAE', this.metrics.mae.toFixed(4)],
        ['MSE', this.metrics.mse.toFixed(4)],
        ['RMSE', this.metrics.rmse.toFixed(4)],
        ['ACC', this.metrics.acc.toFixed(4)],
        ['K', this.metrics.k.toFixed(4)],
        ['R²', this.metrics.r2.toFixed(4)]
      ];
      
      // 添加UTF-8 BOM标记，解决中文乱码问题
      let csvContent = '\ufeff'; // UTF-8 BOM
      
      metricsData.forEach(row => {
        csvContent += row.join(',') + '\r\n';
      });
      
      // 使用Blob对象创建CSV文件
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      
      // 创建下载链接
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `预测评估指标_${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }).slice(0, 10)}.csv`);
      document.body.appendChild(link);
      
      // 触发下载
      link.click();
      
      // 清理资源
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    },

    // 一键上传功能
    async handleOneClickUpload() {
      if (!this.selectedCsvFile || !this.selectedModelFile || !this.selectedScalerFile) {
        this.$message.warning('请先选择所有三个文件');
        return;
      }
      
      this.uploading = true;
      this.$message.info('开始上传所有文件，请稍候...');
      
      try {
        // 1. 上传CSV文件
        await this.uploadFile('Csv', this.selectedCsvFile, this.csvHandleUploadSuccess);
        
        // 2. 上传模型文件
        await this.uploadFile('Model', this.selectedModelFile, this.modelHandleUploadSuccess);
        
        // 3. 上传归一化模型文件
        await this.uploadFile('Scaler', this.selectedScalerFile, this.scalerHandleUploadSuccess);
        
        this.$message.success('所有文件上传成功！');
      } catch (error) {
        console.error('一键上传失败:', error);
        this.$message.error(`上传失败: ${error.message || '未知错误'}`);
      } finally {
        this.uploading = false;
      }
    },
    
    uploadFile(type, file, successCallback) {
      return new Promise((resolve, reject) => {
        let uploadFunction;
        
        if (type === 'Csv') {
          uploadFunction = upload_predict_csv;
        } else if (type === 'Model') {
          uploadFunction = upload_model;
        } else if (type === 'Scaler') {
          uploadFunction = upload_scaler;
        } else {
          reject(new Error('文件类型错误'));
          return;
        }
        
        uploadFunction(file, (progressEvent) => {
          if (progressEvent.lengthComputable) {
            this.uploadProgress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          }
        })
        .then(response => {
          successCallback(response.data);
          resolve(response);
        })
        .catch(error => {
          this.handleUploadError(error);
          reject(error);
        });
      });
    },
  },
  mounted() {
    window.addEventListener('resize', () => {
      if (this.chart) {
        this.chart.resize();
      }
    });
  },
  beforeUnmount() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    if (this.chart) {
      this.chart.dispose();
      this.chart = null;
    }
    window.removeEventListener('resize', () => {
      if (this.chart) {
        this.chart.resize();
      }
    });
  }
};
</script>

<style scoped>
.power-predict-container {
  padding: 32px 0 140px;
  background: transparent;
  color: var(--text-primary);
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.header-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 32px;
  box-shadow: 0 24px 68px rgba(4, 16, 40, 0.45);
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.header-text .page-title {
  margin: 0;
  text-align: left;
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.wind-farm-chip {
  letter-spacing: 0.16em;
  text-transform: uppercase;
  padding: 10px 22px;
  background: rgba(34, 246, 170, 0.16);
  border: 1px solid rgba(34, 246, 170, 0.38);
  box-shadow: inset 0 0 12px rgba(34, 246, 170, 0.32);
}

.workflow-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 320px);
  gap: 28px;
  align-items: start;
}

.upload-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}

.upload-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 26px 24px;
  min-height: 260px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.step-number {
  width: 36px;
  height: 36px;
  border-radius: 18px;
  background: var(--accent-gradient-strong);
  color: #031320;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  letter-spacing: 0.08em;
  box-shadow: var(--accent-shadow);
}

.card-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.workflow-sidebar {
  display: flex;
  flex-direction: column;
  gap: 24px;
  position: sticky;
  top: 120px;
}

.status-card,
.action-card {
  padding: 26px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.status-card h3 {
  margin: 0;
  font-size: 17px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.status-card .card-content {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.action-button {
  height: 44px;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
  background: rgba(6, 18, 36, 0.82);
  color: var(--text-primary);
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.action-button:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: var(--surface-border-strong);
  box-shadow: var(--accent-glow-soft);
}

.action-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.predict-button {
  background: var(--accent-gradient-strong);
  border: none;
  color: #031320;
  box-shadow: var(--accent-shadow);
}

.download-button {
  border-color: rgba(34, 246, 170, 0.4);
  background: rgba(6, 30, 36, 0.82);
}

.one-click-upload {
  display: flex;
  justify-content: flex-start;
}

.one-click-button {
  width: 100%;
  max-width: 260px;
  background: radial-gradient(circle at 0% 50%, rgba(56, 196, 255, 0.4), transparent 70%), var(--accent-gradient-strong);
  border: none;
  color: #031320;
  box-shadow: 0 18px 46px rgba(34, 246, 170, 0.35);
  letter-spacing: 0.16em;
}

.one-click-button:disabled {
  opacity: 0.6;
  box-shadow: none;
}

.empty-action-panel,
.empty-log-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  border-radius: 14px;
  background: rgba(6, 18, 36, 0.65);
  border: 1px dashed rgba(56, 196, 255, 0.24);
  color: var(--text-secondary);
  text-align: center;
}

.empty-icon {
  font-size: 24px;
  color: var(--text-muted);
}

.visualization-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 28px 30px;
}

.visualization-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.visualization-controls {
  display: flex;
  align-items: center;
  gap: 18px;
}

.chart-container {
  background: rgba(4, 16, 38, 0.72);
  border: 1px solid rgba(56, 196, 255, 0.18);
  border-radius: 18px;
  padding: 18px;
}

.metrics-container {
  background: rgba(4, 16, 38, 0.72);
  border: 1px solid rgba(56, 196, 255, 0.18);
  border-radius: 18px;
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.metrics-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.metrics-header h4 {
  margin: 0;
  font-size: 16px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.metrics-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.metric-item {
  position: relative;
  padding: 16px 18px;
  border-radius: 14px;
  background: linear-gradient(160deg, rgba(8, 22, 44, 0.95) 0%, rgba(5, 15, 32, 0.85) 100%);
  border: 1px solid rgba(56, 196, 255, 0.18);
  box-shadow: 0 16px 42px rgba(4, 16, 40, 0.4);
}

.metric-label {
  display: block;
  font-size: 12px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.metric-value {
  font-family: 'Rajdhani', 'Inter', sans-serif;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--accent-primary);
}

.log-section {
  position: fixed;
  bottom: 32px;
  right: 32px;
  width: 360px;
  max-height: 66px;
  overflow: hidden;
  padding: 0;
  transition: max-height 0.35s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.35s;
  z-index: 1200;
}

.log-expanded {
  max-height: 420px;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  cursor: pointer;
  background: rgba(6, 18, 36, 0.9);
  border-bottom: 1px solid rgba(56, 196, 255, 0.18);
}

.log-header .section-title {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.toggle-button {
  color: var(--text-secondary) !important;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.toggle-icon {
  transition: transform 0.3s ease;
}

.toggle-icon.is-rotate {
  transform: rotate(180deg);
}

.log-content-wrapper {
  padding: 18px 20px;
  max-height: 340px;
  overflow-y: auto;
  background: rgba(6, 18, 36, 0.78);
}

.log-content-wrapper::-webkit-scrollbar {
  width: 6px;
}

.log-content-wrapper::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 999px;
}

.log-content-wrapper::-webkit-scrollbar-thumb {
  background: rgba(56, 196, 255, 0.6);
  border-radius: 999px;
}

.log-content-wrapper::-webkit-scrollbar-thumb:hover {
  background: rgba(56, 196, 255, 0.8);
}

.visualization-controls :deep(.el-button.is-text) {
  color: var(--text-secondary);
}

.visualization-controls :deep(.el-button.is-text:hover) {
  color: var(--accent-primary);
}

:deep(.el-checkbox__label) {
  color: var(--text-secondary);
  letter-spacing: 0.08em;
}

:deep(.el-button.is-text) {
  color: var(--text-secondary);
}

:deep(.el-button.is-text:hover) {
  color: var(--accent-primary);
}

:deep(.el-button--text .el-icon) {
  font-size: 16px;
}

:deep(.file-uploader),
:deep(.file-info) {
  background: rgba(8, 22, 44, 0.72);
  border: 1px solid rgba(56, 196, 255, 0.22);
  border-radius: 14px;
  padding: 14px;
}

:deep(.el-upload) {
  width: 100%;
}

:deep(.el-upload-dragger) {
  background: rgba(4, 16, 30, 0.85);
  border: 1px dashed rgba(56, 196, 255, 0.32);
  color: var(--text-secondary);
  border-radius: 12px;
  padding: 18px;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

:deep(.el-upload-dragger:hover) {
  border-color: rgba(56, 196, 255, 0.55);
  box-shadow: var(--accent-glow-soft);
}

:deep(.step-hint-box) {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 20px;
  border-radius: 14px;
  background: rgba(6, 18, 36, 0.78);
  border: 1px solid rgba(56, 196, 255, 0.22);
}

:deep(.step-item) {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: center;
}

:deep(.step-number) {
  width: 26px;
  height: 26px;
  border-radius: 13px;
  background: var(--accent-gradient);
  color: #031320;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--accent-glow-soft);
}

:deep(.step-label) {
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

:deep(.step-status) {
  font-family: 'Rajdhani', 'Inter', sans-serif;
  font-size: 14px;
  letter-spacing: 0.08em;
  color: var(--text-primary);
  word-break: break-all;
}

:deep(.status-null) {
  color: #ff647c;
}

:deep(.step-status span) {
  word-break: break-all;
}

:deep(.log-content .system-message) {
  color: var(--text-secondary);
  font-style: italic;
}

:deep(.log-content .error-message) {
  color: #ff647c;
}

:deep(.log-content .success-message) {
  color: #29f4aa;
}

:deep(.log-content .warning-message) {
  color: #f7c341;
}

:deep(.log-content .log-message) {
  color: var(--text-primary);
}

@media (max-width: 1280px) {
  .workflow-layout {
    grid-template-columns: 1fr;
  }

  .workflow-sidebar {
    position: static;
  }
}

@media (max-width: 768px) {
  .header-panel {
    flex-direction: column;
    align-items: flex-start;
    padding: 24px;
  }

  .workflow-layout {
    gap: 24px;
  }

  .log-section {
    right: 16px;
    left: 16px;
    width: auto;
  }

  .upload-grid {
    grid-template-columns: 1fr;
  }
}
</style>

