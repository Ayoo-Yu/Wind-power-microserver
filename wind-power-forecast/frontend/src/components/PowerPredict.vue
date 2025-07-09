<template>
  <div class="power-predict-container">
    <div class="content-wrapper">
      <h1 class="page-title">功率预测</h1>

      <div class="main-content">
        <div class="upload-section">
          <!-- 数据集上传区域 -->
          <div class="upload-card">
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
          <div class="upload-card">
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
          <div class="upload-card">
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

        <div class="right-panel">
          <!-- 步骤提示 -->
          <div class="status-card">
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
          <div class="action-card">
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
      <div v-if="predictions.length > 0" class="visualization-section">
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
        
        <!-- 图表区域 -->
        <div class="chart-container">
          <div ref="chartRef" style="width: 100%; height: 400px;"></div>
        </div>

        <!-- 评估指标展示区域 -->
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
    </div>

    <!-- 日志查看器 -->
    <div class="log-section" :class="{ 'log-expanded': logVisible }">
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
  </div>
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

export default {
  name: 'PowerPredict',
  components: {
    FileUploader,
    FileInfo,
    LogViewer,
    StepHintBox,
    ArrowDown,
    InfoFilled,
    Download
  },
  data() {
    return {
      // API地址设置
      backendBaseUrl: window.location.hostname !== 'localhost' 
        ? `http://${window.location.hostname}:5000` 
        : 'http://localhost:5000',
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
          this.downloadUrl = `${this.backendBaseUrl}${response.data.download_url}`;
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
      this.socket = useSocket(this.backendBaseUrl, { path: '/socket.io', transports: ['websocket'] });
      this.socket.on('connect', () => {
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
  min-height: 100vh;
  padding: 40px 0;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
  position: relative;
}

.content-wrapper {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 40px;
  box-sizing: border-box;
  padding-bottom: 60px;
}

.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

@keyframes gradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.page-title {
  font-size: 42px !important;
  font-weight: 600;
  color: white;
  text-align: center;
  margin-bottom: 40px;
  letter-spacing: -0.003em;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.main-content {
  display: flex;
  gap: 25px;
  margin-bottom: 30px;
  position: relative;
  align-items: stretch;
}

/* 添加装饰元素 */
.main-content::before {
  content: "✨";
  position: absolute;
  top: -20px;
  left: -10px;
  font-size: 24px;
  opacity: 0.5;
}

.main-content::after {
  content: "✨";
  position: absolute;
  bottom: -20px;
  right: -10px;
  font-size: 24px;
  opacity: 0.5;
}

.upload-section {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.upload-card {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
  border: 1px solid rgba(0, 0, 0, 0.03);
  position: relative;
  display: flex;
  flex-direction: column;
}

/* 添加卡片装饰 */
.upload-card::before {
  content: "✦";
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 14px;
  color: #0077ED;
  opacity: 0.5;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.step-number {
  width: 30px;
  height: 30px;
  border-radius: 15px;
  background: linear-gradient(135deg, #0077ED 0%, #00A2FF 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  box-shadow: 0 3px 8px rgba(0, 119, 237, 0.2);
  flex-shrink: 0;
}

.upload-card h2 {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
  letter-spacing: -0.003em;
}

.right-panel {
  width: 300px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex-shrink: 0;
}

.status-card, .action-card {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
}

.status-card {
  flex: 1;
  overflow: visible;
}

.status-card .card-content {
  overflow: visible;
  width: 100%;
}

.action-card {
  flex: 1;
  justify-content: center;
}

.status-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0 0 14px 0;
  letter-spacing: -0.003em;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  align-items: center;
}

.action-button {
  height: 36px;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: all 0.3s ease;
  width: 100%;
  max-width: 240px;
  letter-spacing: -0.01em;
  display: flex;
  justify-content: center;
  align-items: center;
}

.predict-button {
  background: #0077ED;
  color: #ffffff;
}

.predict-button:hover:not(:disabled) {
  background: #0062CC;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 119, 237, 0.25);
}

.download-button {
  background: #34C759;
  color: #ffffff;
}

.download-button:hover {
  background: #30B753;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(52, 199, 89, 0.25);
}

.visualization-section {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 20px;
  margin: 30px 0;
}

.visualization-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.visualization-controls {
  display: flex;
  gap: 15px;
  align-items: center;
}

.chart-container {
  background: white;
  border-radius: 15px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  margin-bottom: 15px;
}

.metrics-container {
  background: white;
  border-radius: 15px;
  padding: 15px 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.metrics-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 10px;
}

.download-metrics {
  display: flex;
  align-items: center;
}

.metrics-container h4 {
  font-size: 18px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: #f8f9fa;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.metric-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.metric-label {
  font-weight: 600;
  color: #1d1d1f;
  font-size: 16px;
}

.metric-value {
  font-size: 18px;
  color: #0077ED;
  font-weight: 600;
}

/* 上传按钮的特定样式 */
.el-upload .el-button,
.el-button.el-button--success,
.el-button--success:hover,
.el-button--success:focus,
.el-button--success:active {
  background-color: #34C759 !important;
  border-color: transparent !important;
  border: 0 !important;
  color: white !important;
  outline: none !important;
}

/* 覆盖Element Plus的默认样式 */
:deep(.el-button) {
  border: 0 !important;
  outline: none !important;
}

:deep(.el-button--success) {
  --el-button-border-color: transparent !important;
  --el-button-bg-color: #34C759 !important;
  border: none !important;
}

:deep(.el-upload) {
  .el-button {
    border: 0 !important;
    background-color: #34C759 !important;
  }
}

/* 删除按钮样式 */
.el-button--danger {
  background-color: #ff3b30 !important;
  border: none !important;
  color: white !important;
}

.one-click-upload {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.one-click-button {
  background: linear-gradient(135deg, #0077ED 0%, #00A2FF 100%);
  color: #ffffff;
  width: 100%;
  max-width: 240px;
  margin-top: 8px;
  animation: pulse 2s infinite;
}

.one-click-button:hover:not(:disabled) {
  background: linear-gradient(135deg, #0062CC 0%, #0091E8 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 119, 237, 0.3);
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(0, 119, 237, 0.4);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(0, 119, 237, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(0, 119, 237, 0);
  }
}

/* 响应式设计 */
@media (max-width: 1400px) {
  .main-content {
    flex-direction: column;
  }

  .right-panel {
    width: 100%;
    flex-direction: row;
    margin-top: 0;
  }

  .status-card, .action-card {
    min-height: auto;
    flex: 1;
  }
  
  :deep(.step-item) {
    margin-bottom: 6px;
  }
  
  :deep(.step-status) {
    max-width: 100%;
    font-size: 12px;
  }
}

@media (max-width: 1200px) {
  .upload-section {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .content-wrapper {
    padding: 0 30px;
  }
  
  .right-panel {
    flex-direction: column;
  }
}

@media (max-width: 768px) {
  .content-wrapper {
    padding: 0 16px;
  }

  .power-predict-container {
    padding: 20px 0;
  }

  .upload-section {
    grid-template-columns: 1fr;
  }

  .right-panel {
    flex-direction: column;
  }

  .page-title {
    font-size: 32px !important;
    margin-bottom: 30px;
  }
  
  .upload-card, .status-card, .action-card {
    padding: 12px;
  }
  
  :deep(.step-item) {
    flex-direction: row;
    align-items: flex-start;
  }
  
  :deep(.step-number) {
    margin-top: 2px;
  }
  
  :deep(.step-status) {
    word-break: break-all;
    font-size: 11px;
  }
}

.empty-action-panel, .empty-log-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px dashed #dcdfe6;
  min-height: 80px;
  width: 100%;
  box-sizing: border-box;
}

.empty-icon {
  font-size: 22px;
  color: #909399;
  margin-bottom: 8px;
}

.empty-text {
  color: #909399;
  font-size: 14px;
  text-align: center;
  margin: 0;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: #1d1d1f;
  margin: 0;
  letter-spacing: -0.003em;
}

/* 日志面板样式 */
.log-section {
  position: fixed;
  bottom: 0;
  right: 20px;
  width: 400px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 1000;
  max-height: 50px;
  overflow: hidden;
}

.log-expanded {
  max-height: 400px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  cursor: pointer;
  background: linear-gradient(90deg, #0077ED, #00A2FF);
  border-radius: 12px 12px 0 0;
}

.log-header .section-title {
  color: white;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.toggle-button {
  color: white !important;
  font-size: 14px;
  padding: 0;
}

.toggle-icon {
  margin-left: 5px;
  transition: transform 0.3s ease;
}

.toggle-icon.is-rotate {
  transform: rotate(180deg);
}

.log-content-wrapper {
  padding: 15px;
  max-height: 330px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.5;
  color: #1d1d1f;
  background-color: #ffffff;
}

/* 为不同类型的日志消息设置不同的颜色 */
:deep(.log-content) {
  .system-message {
    color: #606266;
    font-style: italic;
  }
  
  .error-message {
    color: #f56c6c;
  }
  
  .success-message {
    color: #67c23a;
  }
  
  .warning-message {
    color: #e6a23c;
  }
  
  /* 普通日志消息 */
  .log-message {
    color: #1d1d1f;
  }
}

/* 自定义滚动条样式 */
.log-content-wrapper::-webkit-scrollbar {
  width: 4px;
}

.log-content-wrapper::-webkit-scrollbar-track {
  background: #f5f5f5;
  border-radius: 2px;
}

.log-content-wrapper::-webkit-scrollbar-thumb {
  background: #ddd;
  border-radius: 2px;
}

.log-content-wrapper::-webkit-scrollbar-thumb:hover {
  background: #ccc;
}

/* 确保日志查看器不会被其他元素遮挡 */
.content-wrapper {
  padding-bottom: 60px;
}

/* 优化FileUploader和FileInfo组件的样式 */
:deep(.file-uploader) {
  margin-bottom: 10px;
}

:deep(.file-info) {
  margin-top: 10px;
}

:deep(.el-upload-dragger) {
  padding: 12px;
  height: auto;
  min-height: 80px;
}

:deep(.step-hint-box) {
  margin-bottom: 0;
  width: 100%;
  overflow: visible;
}

:deep(.step-item) {
  margin-bottom: 10px;
  overflow: visible;
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
}

:deep(.step-number) {
  flex-shrink: 0;
  margin-right: 8px;
  width: 24px;
  height: 24px;
  border-radius: 12px;
  background: #0077ED;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  margin-top: 2px;
}

:deep(.step-label) {
  margin-right: 6px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
}

:deep(.step-status) {
  word-break: break-all;
  overflow-wrap: break-word;
  font-family: monospace;
  font-size: 13px;
  color: #0077ED;
  max-width: 100%;
}

:deep(.status-null) {
  color: #ff3b30;
  font-style: italic;
}

:deep(.el-table .cell) {
  text-align: center;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  color: #1d1d1f;
  font-weight: 600;
  padding: 10px 0;
}

:deep(.el-table__header-wrapper) {
  border-bottom: 1px solid #ebeef5;
}
</style>

