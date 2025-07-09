<template>
  <div class="model-train-container">
    <!-- 页面标题和重置按钮区域 -->
    <div class="header-section">
      <h1 class="page-title">模型训练</h1>
      <el-button 
        class="reset-all-button" 
        type="primary" 
        @click="confirmResetAll"
        :disabled="!hasAnyData"
      >
        <el-icon><Refresh /></el-icon>
        重新训练
      </el-button>
    </div>

    <!-- Hero Section 装饰在标题之后 -->
    <div class="hero-section"></div>

    <!-- 主体内容区域：左右两栏 -->
    <div class="content-area">
      <!-- 左侧：文件上传、模型选择与操作面板 -->
      <div class="left-panel">
        <!-- 数据集上传区域 -->
        <section class="panel-section" :class="{ 'is-collapsed': isStepCollapsed[0], 'completed': stepCompleted[0] }">
          <div class="panel-header" @click="toggleStep(0)">
            <div class="step-status">
              <h2>步骤一：选择训练集</h2>
              <span v-if="stepCompleted[0]" class="completed-text">已完成</span>
              <el-icon v-if="stepCompleted[0]" class="completed-icon"><Check /></el-icon>
            </div>
            <el-button type="text" class="toggle-button">
              {{ isStepCollapsed[0] ? '展开' : '收起' }}
              <el-icon class="toggle-icon" :class="{ 'is-rotate': !isStepCollapsed[0] }">
                <arrow-down />
              </el-icon>
            </el-button>
          </div>
          <div class="panel-content" v-show="!isStepCollapsed[0]">
            <FileUploader
              :processing="processing"
              :acceptedFormats="['csv']"
              :uploadText="customUploadText_modeltrain"
              @file-selected="onFileSelected"
            />
            <p class="upload-tip">请上传本系统导出的CSV文件，且不超过500MB</p>
          </div>
        </section>

        <!-- 文件信息区域 -->
        <section class="panel-section" :class="{ 'is-collapsed': isStepCollapsed[1], 'completed': stepCompleted[1] }">
          <div class="panel-header" @click="toggleStep(1)">
            <div class="step-status">
              <h2>步骤二：确认文件并上传</h2>
              <span v-if="stepCompleted[1]" class="completed-text">已完成</span>
              <el-icon v-if="stepCompleted[1]" class="completed-icon"><Check /></el-icon>
            </div>
            <el-button type="text" class="toggle-button">
              {{ isStepCollapsed[1] ? '展开' : '收起' }}
              <el-icon class="toggle-icon" :class="{ 'is-rotate': !isStepCollapsed[1] }">
                <arrow-down />
              </el-icon>
            </el-button>
          </div>
          <div class="panel-content" v-show="!isStepCollapsed[1]">
            <FileInfo 
              :fileInfo="fileInfo" 
              @remove-file="removeSelectedFile"
              @start-upload="handleManualUpload"
              :disabled="!selectedFile"
            />
          </div>
        </section>

        <!-- 模型选择区域 -->
        <section class="panel-section" :class="{ 'is-collapsed': isStepCollapsed[2], 'completed': stepCompleted[2] }">
          <div class="panel-header" @click="toggleStep(2)">
            <div class="step-status">
              <h2>步骤三：设置训练模型</h2>
              <span v-if="stepCompleted[2]" class="completed-text">已完成</span>
              <el-icon v-if="stepCompleted[2]" class="completed-icon"><Check /></el-icon>
            </div>
            <el-button type="text" class="toggle-button">
              {{ isStepCollapsed[2] ? '展开' : '收起' }}
              <el-icon class="toggle-icon" :class="{ 'is-rotate': !isStepCollapsed[2] }">
                <arrow-down />
              </el-icon>
            </el-button>
          </div>
          <div class="panel-content" v-show="!isStepCollapsed[2]">
            <ModelSelector 
              :fileId="fileId" 
              :processing="processing" 
              :selectedModel="selectedModel" 
              :wfCapacity="wfCapacity"
              :predictionstate="predictionstate"
              :trainRatio="trainRatio"
              @model-selected="onModelSelected"
              @model_wf_capacity="onWindFarmCapacityChange"
              @train-ratio-change="onTrainRatioChange"
              @custom-params-change="onCustomParamsChange"
              @reset="confirmReset"
            />
          </div>
        </section>

        <!-- 操作面板区域 -->
        <section class="panel-section" :class="{ 'is-collapsed': isStepCollapsed[3], 'completed': stepCompleted[3] }">
          <div class="panel-header" @click="toggleStep(3)">
            <div class="step-status">
              <h2>步骤四：启动训练</h2>
              <span v-if="stepCompleted[3]" class="completed-text">已完成</span>
              <el-icon v-if="stepCompleted[3]" class="completed-icon"><Check /></el-icon>
            </div>
            <el-button type="text" class="toggle-button">
              {{ isStepCollapsed[3] ? '展开' : '收起' }}
              <el-icon class="toggle-icon" :class="{ 'is-rotate': !isStepCollapsed[3] }">
                <arrow-down />
              </el-icon>
            </el-button>
          </div>
          <div class="panel-content" v-show="!isStepCollapsed[3]">
            <div v-if="!fileInfo || !selectedModel" class="empty-operation-panel">
              <el-icon class="empty-icon"><InfoFilled /></el-icon>
              <p class="empty-text">请完成文件上传和模型选择</p>
            </div>
            <PredictionButtons 
              v-else
              :selectedFile="selectedFile" 
              :uploading="uploading" 
              :fileId="fileId" 
              :wfCapacity="wfCapacity"
              :processing="processing" 
              :downloadUrl="downloadUrl"
              :reportDownloadUrl="reportDownloadUrl"
              :modelDownloadUrl="modelDownloadUrl"
              :scalerDownloadUrl="scalerDownloadUrl"
              @start-upload="handleManualUpload"
              @start-prediction="startPrediction"
              @download-file="downloadFile"
              @fetch-daily-metrics="fetchDailyMetrics"
              @check-status="forceCheckStatus"
            />
          </div>
        </section>
      </div>
    </div>

    <!-- 浮动日志面板 -->
    <div class="log-section" :class="{ 'log-expanded': logVisible }">
      <div class="log-header" @click="toggleLogVisible">
        <h3 class="section-title">训练日志</h3>
        <el-button type="text" class="toggle-button">
          {{ logVisible ? '收起' : '展开' }}
          <el-icon class="toggle-icon" :class="{ 'is-rotate': logVisible }">
            <arrow-down />
          </el-icon>
        </el-button>
      </div>
      <div v-if="logVisible" class="log-content-wrapper">
        <div v-if="!logs" class="empty-log-panel">
          <el-icon class="empty-icon"><InfoFilled /></el-icon>
          <p class="empty-text">暂无日志信息</p>
        </div>
        <LogViewer 
          v-if="logs"
          :logs="logs" 
          @clear-logs="clearLogs"
        />
      </div>
    </div>

    <!-- 上传进度与加载提示 -->
    <UploadProgress 
      :visible="uploading" 
      :percentage="uploadProgress" 
      :status="uploadProgress === 100 ? 'success' : 'active'"
    />
    <LoadingIndicator 
      :visible="uploading" 
      message="上传中..."
    />
    <LoadingIndicator 
      :visible="processing" 
      message="训练中...请耐心等待"
    />

    <!-- 图表展示区域 -->
    <section class="charts-section" v-if="chartData">
      <h2>训练结果分析</h2>
      <div class="chart-grid">
        <div
          v-for="(chart, index) in chartData" 
          :key="index"
          class="chart-wrapper"
        >
          <canvas :ref="`chart${index}`"></canvas>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { upload_train_csv, modeltrain, checkTrainingStatus } from '@/services/apiService';  
import { useSocket } from '@/composables/useSocket'; 
import FileUploader from './FileUploader.vue';
import FileInfo from './FileInfo.vue';
import ModelSelector from './ModelSelector.vue';
import PredictionButtons from './PredictionButtons.vue';
import LogViewer from './LogViewer.vue';
import LoadingIndicator from './LoadingIndicator.vue';
import UploadProgress from './UploadProgress.vue';
import { InfoFilled, ArrowDown, Check, Refresh } from '@element-plus/icons-vue';
import Papa from 'papaparse';
import axios from 'axios';
import { Chart, CategoryScale, LinearScale, LineElement, PointElement, Title, Tooltip, Legend, LineController } from 'chart.js';
Chart.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  LineController
);

export default {
  name: 'ModelTrain',
  components: {
    FileUploader,
    FileInfo,
    ModelSelector,
    PredictionButtons,
    LogViewer,
    LoadingIndicator,
    UploadProgress,
    InfoFilled,
    ArrowDown,
    Check,
    Refresh,
  },
  data() {
    return {
      backendBaseUrl: window.location.hostname !== 'localhost' 
        ? `http://${window.location.hostname}:5000` 
        : 'http://localhost:5000',
      customUploadText_modeltrain: '点击上传训练数据集文件',
      fileId: null,
      selectedFile: null,
      uploading: false,
      uploadProgress: 0,
      fileInfo: null,
      selectedModel: null,
      downloadUrl: '',
      reportDownloadUrl: '',
      modelDownloadUrl: '',
      scalerDownloadUrl: '',
      logs: '',
      processing: false,
      socket: null,
      predictionReady: false,
      predictionstate: false,
      wfCapacity: 453.5,
      trainRatio: 0.9,
      customParams: null,
      dailyMetrics: null,
      chartData: null,
      chartInstances: [],
      trainingTimeoutCheck: null,
      statusCheckInterval: null,
      logVisible: false,
      isStepCollapsed: [false, false, false, false],
      stepCompleted: [false, false, false, false],
    };
  },
  computed: {
    hasAnyData() {
      return !!(this.fileId || this.selectedFile || this.selectedModel || this.fileInfo || this.logs || this.chartData);
    }
  },
  methods: {
    onFileSelected(file) {
      this.resetState();
      this.selectedFile = file;
      this.fileInfo = {
        name: file.name,
        size: file.size,
        type: file.type,
        uploadDate: new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }),
      };
      this.initializeSocket();
    },
    handleUploadSuccess(response) {
      this.uploading = false;
      this.uploadProgress = 0;
      if (response.file_id) {
        this.fileId = response.file_id;
        this.$message.success('文件上传成功！请点击选择模型类型。');
        this.stepCompleted[0] = true;
        this.stepCompleted[1] = true;
        setTimeout(() => {
          this.isStepCollapsed[0] = true;
          this.isStepCollapsed[1] = true;
          this.isStepCollapsed[2] = false;
        }, 500);
      }
      if (response.download_url) {
        this.downloadUrl = `${this.backendBaseUrl}${response.download_url}`;
        this.$message.success('预测结果已生成，您可以下载预测结果。');
      }
      if (response.report_download_url) {
        this.reportDownloadUrl = `${this.backendBaseUrl}${response.report_download_url}`;
        this.$message.success('预测报告已生成，您可以下载评估报告。');
      }
      if (response.model_download_url) {
        this.modelDownloadUrl = `${this.backendBaseUrl}${response.model_download_url}`;
        this.$message.success('模型已保存，您可以下载模型文件。');
      }
      if (response.scaler_download_url) {
        this.scalerDownloadUrl = `${this.backendBaseUrl}${response.scaler_download_url}`;
        this.$message.success('标准化器已保存，您可以下载标准化器文件。');
      }
      this.selectedFile = null;
    },
    handleUploadError(error) {
      this.uploading = false;
      this.uploadProgress = 0;
      console.error('文件上传失败:', error);
      this.$message.error(`文件上传失败：${error.message || '未知错误'}`);
    },
    removeSelectedFile() {
      this.$confirm('确定要删除选中的文件吗？此操作不可恢复。', '删除确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.resetState();
        this.$message({
          type: 'success',
          message: '文件已删除'
        });
      }).catch(() => {
        this.$message({
          type: 'info',
          message: '已取消删除'
        });
      });
    },
    onModelSelected(model) {
      this.selectedModel = model;
      if (model) {
        this.isStepCollapsed[3] = false;
      }
    },
    onWindFarmCapacityChange(value) {
      this.wfCapacity = value;
    },
    onTrainRatioChange(value) {
      this.trainRatio = value;
    },
    onCustomParamsChange(params) {
      this.customParams = params;
    },
    onPredictionReady(value) {
      this.predictionReady = value;
    },
    confirmReset() {
      this.$confirm('确定要重置所有训练设置吗？这将清除当前的所有设置和结果。', '重置确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.resetTraining();
        this.$message({
          type: 'success',
          message: '已重置所有训练设置'
        });
      }).catch(() => {
        this.$message({
          type: 'info',
          message: '已取消重置'
        });
      });
    },
    resetTraining() {
      this.selectedModel = null;
      this.wfCapacity = 453.5;
      this.trainRatio = 0.9;
      this.customParams = null;
      this.downloadUrl = '';
      this.reportDownloadUrl = '';
      this.modelDownloadUrl = '';
      this.scalerDownloadUrl = '';
      this.predictionstate = false;
      this.chartData = null;
      
      if (this.chartInstances && this.chartInstances.length > 0) {
        this.chartInstances.forEach(chart => chart.destroy());
        this.chartInstances = [];
      }
      
      this.logs = '';
      this.clearTimers();
      this.isStepCollapsed = [false, false, false, false];
      this.stepCompleted = [false, false, false, false];
    },
    handleManualUpload() {
      if (!this.selectedFile) {
        this.$message.error('请先选择一个文件！');
        return;
      }
      this.uploading = true;
      this.uploadProgress = 0;

      upload_train_csv(this.selectedFile, (progressEvent) => {
        if (progressEvent.lengthComputable) {
          this.uploadProgress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        }
      })
        .then(response => {
          this.handleUploadSuccess(response.data);
        })
        .catch(error => {
          this.handleUploadError(error);
        });
    },
    startPrediction() {
      if (!this.fileId || !this.selectedModel) {
        this.$message.error('请先选择文件并指定模型！');
        return;
      }
      
      this.stepCompleted[2] = true;
      this.$nextTick(() => {
        setTimeout(() => {
          this.isStepCollapsed[2] = true;
        }, 300);
      });

      this.clearTimers();
      
      this.processing = true;
      this.predictionstate = true;
      
      this.initializeSocket();
      
      this.trainingTimeoutCheck = setTimeout(() => {
        if (this.processing) {
          this.logs += `[系统消息] 训练时间较长，正在检查状态...\n`;
          this.checkTrainingStatus();
        }
      }, 120000);
      
      this.statusCheckInterval = setInterval(() => {
        if (this.processing) {
          console.log('定期检查训练状态...');
          this.checkTrainingStatus();
        } else {
          this.clearTimers();
        }
      }, 30000);
      
      modeltrain(this.fileId, this.selectedModel, this.wfCapacity, this.trainRatio, this.customParams)
        .then(response => {
          this.clearTimers();
          
          if (response.data.download_url) {
            this.downloadUrl = `${this.backendBaseUrl}${response.data.download_url}`;
            this.$message.success('预测结果已生成，您可以下载预测结果。');
          } else {
            this.$message.error('预测完成，但未返回下载链接。');
          }
          
          if (response.data.report_download_url) {
            this.reportDownloadUrl = `${this.backendBaseUrl}${response.data.report_download_url}`;
            this.$message.success('预测报告已生成，您可以下载评估报告。');
          }
          
          if (response.data.model_download_url) {
            this.modelDownloadUrl = `${this.backendBaseUrl}${response.data.model_download_url}`;
            console.log('已更新模型下载链接:', this.modelDownloadUrl);
          }
          
          if (response.data.scaler_download_url) {
            this.scalerDownloadUrl = `${this.backendBaseUrl}${response.data.scaler_download_url}`;
            console.log('已更新标准化器下载链接:', this.scalerDownloadUrl);
          }
          
          this.processing = false;
        })
        .catch(error => {
          console.error('训练请求错误:', error);
          if (error.response && error.response.status === 500) {
            this.$message.warning('模型训练请求超时，但后端仍在继续处理。训练过程将通过日志区域显示，请耐心等待。');
          } else {
            this.$message.error(`预测失败：${error.response?.data?.error || '未知错误'}`);
            this.processing = false;
            this.clearTimers();
          }
        });
    },
    downloadFile(downloadUrl) {
      window.open(downloadUrl);
    },
    initializeSocket() {
      if (this.socket) return;
      
      this.socket = useSocket(this.backendBaseUrl, { path: '/socket.io', transports: ['websocket'] });
      
      this.socket.on('connect', () => {
        console.log('Socket连接成功');
        
        if (this.processing && this.fileId) {
          this.checkTrainingStatus();
        }
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
        
        this.checkTrainingCompletionFromLog(message);
      });
      
      this.socket.on('error', (error) => {
        console.error('Socket错误:', error);
        this.$message.error(`Socket连接错误: ${error}`);
      });
      
      this.socket.on('disconnect', (reason) => {
        console.log('Socket连接断开:', reason);
        this.logs += `[系统消息] Socket连接已断开: ${reason}\n`;
        
        setTimeout(() => {
          if (this.processing) {
            console.log('正在尝试重新连接Socket...');
            this.socket.connect();
          }
        }, 3000);
      });
      
      this.socket.on('reconnect', (attemptNumber) => {
        console.log(`Socket重新连接成功，尝试次数: ${attemptNumber}`);
        this.logs += `[系统消息] Socket已重新连接，尝试次数: ${attemptNumber}\n`;
        
        if (this.processing && this.fileId) {
          this.checkTrainingStatus();
        }
      });
    },
    checkTrainingCompletionFromLog(message) {
      if (!message) return;
      
      const completionKeywords = [
        '训练完成', 'Training completed', '下载链接', 
        '预测文件下载url', '训练报告下载url',
        '测试集评估完成', '总体评估指标', 'MAE:',
        '将原生报告复制到以下路径'
      ];
      
      const isCompleted = completionKeywords.some(keyword => message.includes(keyword));
      
      if (isCompleted) {
        this.extractDownloadLinks(message);
        
        if (this.processing) {
          console.log('从日志中检测到训练完成信号');
          this.processing = false;
          this.$message.success('模型训练已完成！');
          this.clearTimers();
          this.stepCompleted[3] = true;
        }
      }
    },
    extractDownloadLinks(message) {
      const predictUrlPattern = /预测文件下载url为:\s+([^\s]+)/;
      const predictMatch = message.match(predictUrlPattern);
      if (predictMatch && predictMatch[1]) {
        this.downloadUrl = `${this.backendBaseUrl}${predictMatch[1]}`;
        console.log('提取到预测文件下载链接:', this.downloadUrl);
      }
      
      const reportUrlPattern = /训练报告下载url为:\s+([^\s]+)/;
      const reportMatch = message.match(reportUrlPattern);
      if (reportMatch && reportMatch[1]) {
        this.reportDownloadUrl = `${this.backendBaseUrl}${reportMatch[1]}`;
        console.log('提取到报告下载链接:', this.reportDownloadUrl);
      }
      
      const modelUrlPattern = /model_download_url=([^\s]+)/;
      const modelMatch = message.match(modelUrlPattern);
      if (modelMatch && modelMatch[1]) {
        this.modelDownloadUrl = `${this.backendBaseUrl}${modelMatch[1]}`;
        console.log('提取到模型下载链接:', this.modelDownloadUrl);
      }
      
      const scalerUrlPattern = /scaler_download_url=([^\s]+)/;
      const scalerMatch = message.match(scalerUrlPattern);
      if (scalerMatch && scalerMatch[1]) {
        this.scalerDownloadUrl = `${this.backendBaseUrl}${scalerMatch[1]}`;
        console.log('提取到标准化器下载链接:', this.scalerDownloadUrl);
      }
    },
    clearTimers() {
      if (this.trainingTimeoutCheck) {
        clearTimeout(this.trainingTimeoutCheck);
        this.trainingTimeoutCheck = null;
      }
      
      if (this.statusCheckInterval) {
        clearInterval(this.statusCheckInterval);
        this.statusCheckInterval = null;
      }
    },
    async checkTrainingStatus(forceCheck = false) {
      if (!this.fileId) return;
      
      try {
        console.log('主动检查训练状态...');
        if (!forceCheck) {
          this.logs += `<div class="system-message">[系统消息] 正在检查训练状态...</div>\n`;
        }
        
        const response = await checkTrainingStatus(this.fileId);
        
        console.log('训练状态检查结果:', response.data);
        
        if (response.data.status === 'completed') {
          this.processing = false;
          this.$message.success('模型训练已完成！');
          
          if (response.data.download_url) {
            this.downloadUrl = `${this.backendBaseUrl}${response.data.download_url}`;
            console.log('已更新下载链接:', this.downloadUrl);
          }
          
          if (response.data.report_download_url) {
            this.reportDownloadUrl = `${this.backendBaseUrl}${response.data.report_download_url}`;
            console.log('已更新报告链接:', this.reportDownloadUrl);
          }
          
          if (response.data.model_download_url) {
            this.modelDownloadUrl = `${this.backendBaseUrl}${response.data.model_download_url}`;
            console.log('已更新模型下载链接:', this.modelDownloadUrl);
          }
          
          if (response.data.scaler_download_url) {
            this.scalerDownloadUrl = `${this.backendBaseUrl}${response.data.scaler_download_url}`;
            console.log('已更新标准化器下载链接:', this.scalerDownloadUrl);
          }
          
          this.logs += `<div class="success-message">[系统消息] 训练已完成，可以下载结果。</div>\n`;
          this.clearTimers();
        } else if (response.data.status === 'in_progress') {
          this.logs += `<div class="system-message">[系统消息] 训练仍在进行中，请耐心等待。</div>\n`;
          
          if (forceCheck) {
            this.checkLogForCompletion();
          }
        } else {
          this.logs += `<div class="warning-message">[系统消息] 未能获取清晰的训练状态，正在分析日志...</div>\n`;
          this.checkLogForCompletion();
        }
      } catch (error) {
        console.error('检查训练状态失败:', error);
        this.logs += `[系统消息] 检查训练状态失败: ${error.message}\n`;
        
        if (forceCheck) {
          this.checkLogForCompletion();
        }
      }
    },
    checkLogForCompletion() {
      if (!this.logs) return;
      
      this.logs += `<div class="system-message">[系统消息] 正在分析日志内容...</div>\n`;
      
      const logLines = this.logs.split('\n');
      let foundCompletionSignal = false;
      
      for (const line of logLines) {
        if (line.includes('总体评估指标') || 
            line.includes('MAE:') ||
            line.includes('MSE:') ||
            line.includes('RMSE:') ||
            line.includes('ACC:') || 
            line.includes('PE:') ||
            line.includes('K:')) {
          foundCompletionSignal = true;
          console.log('在日志中找到评估指标:', line);
        }
        
        if (line.includes('预测文件下载url为:') || 
            line.includes('训练报告下载url为:') ||
            line.includes('model_download_url=') ||
            line.includes('scaler_download_url=')) {
          foundCompletionSignal = true;
          this.extractDownloadLinks(line);
          console.log('在日志中找到下载链接:', line);
        }
      }
      
      if (foundCompletionSignal && this.processing) {
        this.processing = false;
        this.$message.success('根据日志分析，模型训练已完成！');
        this.clearTimers();
        this.logs += `<div class="success-message">[系统消息] 根据日志分析，训练已完成</div>\n`;
        this.stepCompleted[3] = true;
      }
    },
    clearLogs() {
      this.logs = '';
    },
    resetState() {
      this.selectedFile = null;
      this.fileInfo = null;
      this.fileId = null;
      this.uploading = false;
      this.uploadProgress = 0;
      this.processing = false;
      this.selectedModel = null;
      this.downloadUrl = '';
      this.reportDownloadUrl = '';
      this.modelDownloadUrl = '';
      this.scalerDownloadUrl = '';
      this.predictionstate = false;
      this.trainRatio = 0.9;
      this.customParams = null;
      this.clearTimers();
      this.isStepCollapsed = [false, false, false, false];
      this.stepCompleted = [false, false, false, false];
    },
    async fetchDailyMetrics() {
      if (!this.fileId) {
        this.$message.error('请先上传文件！');
        return;
      }

      try {
        const response = await axios.get(`${this.backendBaseUrl}/get-daily-metrics?file_id=${this.fileId}`);
        
        if (!response.data) {
          this.$message.error('未获取到日常指标数据');
          return;
        }

        const parseData = new Promise((resolve) => {
          Papa.parse(response.data, {
            complete: (result) => {
              if (result.errors.length > 0) {
                this.$message.error('CSV 解析失败');
                console.error(result.errors);
                return;
              }
              resolve(result.data);
            }
          });
        });

        const data = await parseData;
        await this.processChartData(data);
        
      } catch (error) {
        this.$message.error(`获取日常指标失败：${error.message}`);
        console.error('Error fetching daily metrics:', error);
      }
    },
    async processChartData(data) {
      if (!data || data.length === 0) {
        this.$message.error('CSV 数据格式错误，请检查文件内容');
        return;
      }

      const labels = [];
      const maeValues = [];
      const mseValues = [];
      const rmseValues = [];
      const accValues = [];
      const kValues = [];
      const peValues = [];

      const dataRows = data.slice(1);
      dataRows.forEach(item => {
        const rawDate = item[0];
        const date = new Date(rawDate);
        if (isNaN(date.getTime())) {
          console.warn('Skipping invalid date:', rawDate);
          return;
        }
        const formattedDate = date.toISOString().slice(0, 10).replace(/-/g, '/');
        labels.push(formattedDate);
        
        const mae = parseFloat(item[1]);
        const mse = parseFloat(item[2]);
        const rmse = parseFloat(item[3]);
        const acc = parseFloat(item[4]);
        const k = parseFloat(item[5]);
        const pe = parseFloat(item[6]);

        if (isNaN(mae) || isNaN(mse) || isNaN(rmse) || isNaN(acc) || isNaN(k) || isNaN(pe)) {
          console.warn('Skipping row with invalid values:', item);
          return;
        }

        maeValues.push(mae);
        mseValues.push(mse);
        rmseValues.push(rmse);
        accValues.push(acc);
        kValues.push(k);
        peValues.push(pe);
      });

      if (labels.length === 0 || maeValues.length === 0) {
        this.$message.error('无效的数据，无法绘制图表');
        return;
      }

      this.chartData = null;
      await this.$nextTick();

      this.chartData = [
        { label: '平均绝对误差 MAE', data: maeValues, borderColor: '#4caf50', backgroundColor: 'rgba(76, 175, 80, 0.2)', fill: true },
        { label: '均方误差 MSE', data: mseValues, borderColor: '#ff5722', backgroundColor: 'rgba(255, 87, 34, 0.2)', fill: true },
        { label: '均方根误差 RMSE', data: rmseValues, borderColor: '#2196f3', backgroundColor: 'rgba(33, 150, 243, 0.2)', fill: true },
        { label: '预测精度 ACC', data: accValues, borderColor: '#ff9800', backgroundColor: 'rgba(255, 152, 0, 0.2)', fill: true },
        { label: '预测精度 K', data: kValues, borderColor: '#9c27b0', backgroundColor: 'rgba(156, 39, 176, 0.2)', fill: true },
        { label: '日均考核电量 Pe', data: peValues, borderColor: '#00bcd4', backgroundColor: 'rgba(0, 188, 212, 0.2)', fill: true },
      ];

      await this.$nextTick();
      this.renderCharts(labels);
    },
    renderCharts(labels) {
      if (this.chartInstances) {
        this.chartInstances.forEach(chart => chart.destroy());
      }
      this.chartInstances = [];

      this.chartData.forEach((dataset, index) => {
        const canvas = this.$refs[`chart${index}`][0];
        if (canvas) {
          const ctx = canvas.getContext('2d');
          
          const meanValue = dataset.data.reduce((a, b) => a + b, 0) / dataset.data.length;
          
          const chart = new Chart(ctx, {
            type: 'line',
            data: {
              labels: labels,
              datasets: [{
                label: `${dataset.label} (平均值: ${meanValue.toFixed(4)})`,
                data: dataset.data,
                borderColor: dataset.borderColor,
                backgroundColor: dataset.backgroundColor,
                fill: dataset.fill
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: true,
              plugins: {
                legend: {
                  position: 'top'
                },
                title: {
                  display: true,
                  text: dataset.label
                }
              },
              scales: {
                y: {
                  beginAtZero: true
                }
              }
            }
          });
          this.chartInstances.push(chart);
        }
      });
    },
    beforeDestroy() {
      this.clearTimers();
      if (this.socket) {
        this.socket.disconnect();
        this.socket = null;
      }
      if (this.chartInstances) {
        this.chartInstances.forEach(chart => chart.destroy());
      }
    },
    forceCheckStatus() {
      if (!this.fileId) {
        this.$message.warning('没有正在进行的训练任务');
        return;
      }
      
      this.$message.info('正在检查训练状态...');
      this.logs += `[系统消息] 用户手动触发状态检查\n`;
      
      this.checkTrainingStatus(true);
    },
    toggleLogVisible() {
      this.logVisible = !this.logVisible;
    },
    toggleStep(index) {
      this.isStepCollapsed[index] = !this.isStepCollapsed[index];
    },
    confirmResetAll() {
      this.$confirm('确定要重置所有训练数据吗？这将清除当前的所有设置、日志和结果。', '重置确认', {
        confirmButtonText: '确定重置',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.resetState();
        this.clearLogs();
        this.$message({
          type: 'success',
          message: '已重置所有训练数据'
        });
      }).catch(() => {
        this.$message({
          type: 'info',
          message: '已取消重置'
        });
      });
    },
  },
};
</script>

<style scoped>
.model-train-container {
  min-height: 100vh;
  padding: 20px;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
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

.header-section {
  width: 100%;
  max-width: 800px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  position: relative;
}

.reset-all-button {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  padding: 8px 16px;
  font-size: 14px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.3s ease;
}

.reset-all-button:hover {
  transform: translateY(-50%) translateX(-2px);
}

.reset-all-button :deep(.el-icon) {
  font-size: 16px;
}

.page-title {
  color: white;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  font-size: 28px;
  margin: 0;
  text-align: center;
  flex: 1;
}

.content-area {
  width: 100%;
  max-width: 800px;
  margin: 0 auto 40px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.left-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.panel-section {
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.05);
  border-radius: 12px;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  will-change: max-height;
}

.panel-section:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  cursor: pointer;
  background: #ffffff;
  border-bottom: 1px solid transparent;
  transition: all 0.3s ease;
}

.panel-section.is-collapsed .panel-header {
  border-bottom-color: transparent;
}

.panel-section:not(.is-collapsed) .panel-header {
  border-bottom-color: rgba(0, 0, 0, 0.06);
}

.panel-content {
  padding: 20px;
  opacity: 1;
  transition: opacity 0.3s ease;
}

.panel-section.is-collapsed .panel-content {
  opacity: 0;
  height: 0;
  padding: 0;
  overflow: hidden;
}

.panel-section h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-section .toggle-button {
  color: #606266;
  font-size: 13px;
  display: flex;
  align-items: center;
  padding: 0;
}

.panel-section .toggle-icon {
  margin-left: 4px;
  transition: transform 0.3s ease;
  font-size: 12px;
}

.panel-section .toggle-icon.is-rotate {
  transform: rotate(180deg);
}

.panel-section.is-collapsed {
  background: #f8f9fa;
  max-height: 56px;
  transition: max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: max-height;
}

.panel-section:not(.is-collapsed) {
  max-height: 800px;
  transition: max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: max-height;
}

.panel-section.is-collapsed.completed .panel-header {
  background: #f0f9ff;
}

.panel-header .step-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-status .completed-text {
  color: #0077ED;
  font-size: 13px;
  opacity: 0;
  transform: translateX(-10px);
  transition: all 0.3s ease;
}

.panel-section.is-collapsed.completed .step-status .completed-text {
  opacity: 1;
  transform: translateX(0);
}

.step-status .completed-icon {
  color: #0077ED;
  font-size: 16px;
  opacity: 0;
  transform: scale(0.8);
  transition: all 0.3s ease;
}

.panel-section.is-collapsed.completed .step-status .completed-icon {
  opacity: 1;
  transform: scale(1);
}

.upload-tip {
  color: #606266;
  margin-top: 8px;
  font-size: 12px;
  text-align: center;
}

.hero-section {
  text-align: center;
  padding: 20px;
  position: relative;
  margin-bottom: 20px;
}

.hero-section::before,
.hero-section::after {
  font-size: 18px;
  opacity: 0.5;
}

.charts-section {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.05);
  box-sizing: border-box;
}

.charts-section h2 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin: 0;
}

.chart-wrapper {
  aspect-ratio: 16/9;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  min-height: 200px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02);
}

.empty-operation-panel, .empty-log-panel {
  padding: 20px;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px dashed #e4e7ed;
}

.empty-icon {
  font-size: 20px;
  color: #909399;
  margin-bottom: 8px;
}

.empty-text {
  color: #909399;
  font-size: 13px;
  text-align: center;
  margin: 0;
}

/* 日志面板样式优化 */
.log-section {
  position: fixed;
  bottom: 0;
  right: 16px;
  width: 360px;
  background: #ffffff;
  border-radius: 8px 8px 0 0;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 1000;
  max-height: 40px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.log-expanded {
  max-height: 360px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  background: linear-gradient(90deg, #0077ED, #00A2FF);
  border-radius: 8px 8px 0 0;
  height: 40px;
}

.log-header .section-title {
  color: white;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.toggle-button {
  color: white !important;
  font-size: 13px;
  padding: 0;
}

.toggle-icon {
  margin-left: 4px;
  transition: transform 0.3s ease;
  font-size: 12px;
}

.toggle-icon.is-rotate {
  transform: rotate(180deg);
}

.log-content-wrapper {
  padding: 12px;
  max-height: 320px;
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

@media (max-width: 840px) {
  .content-area {
    margin-bottom: 60px;
  }
  
  .content-area,
  .charts-section {
    max-width: 100%;
    padding: 16px;
  }
  
  .chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .model-train-container {
    padding: 16px;
  }
  
  .header-section {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .reset-all-button {
    position: static;
    transform: none;
    width: 100%;
    justify-content: center;
  }
  
  .page-title {
    text-align: center;
    font-size: 24px;
  }
  
  .panel-section {
    padding: 16px;
  }
  
  .log-section {
    width: calc(100% - 32px);
    right: 16px;
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

/* 统一按钮样式 */
:deep(.el-button) {
  --el-button-bg-color: #0077ED !important;
  --el-button-border-color: transparent !important;
  --el-button-text-color: #ffffff !important;
  --el-button-hover-text-color: #ffffff !important;
  --el-button-hover-bg-color: #1890ff !important;
  --el-button-hover-border-color: transparent !important;
  --el-button-active-bg-color: #0062d1 !important;
  --el-button-active-border-color: transparent !important;
  --el-button-disabled-bg-color: #a8d4ff !important;
  --el-button-disabled-border-color: transparent !important;
}

:deep(.el-button--primary),
:deep(.el-button--success),
:deep(.el-button--default) {
  color: #ffffff !important;
  background-color: #0077ED !important;
  border-color: transparent !important;
  outline: none !important;
}

:deep(.el-button--primary:hover),
:deep(.el-button--success:hover),
:deep(.el-button--default:hover) {
  background-color: #1890ff !important;
  border-color: transparent !important;
  outline: none !important;
}

:deep(.el-button--primary:active),
:deep(.el-button--success:active),
:deep(.el-button--default:active) {
  background-color: #0062d1 !important;
  border-color: transparent !important;
  outline: none !important;
}

:deep(.el-button--primary.is-disabled),
:deep(.el-button--success.is-disabled),
:deep(.el-button--default.is-disabled) {
  background-color: #a8d4ff !important;
  border-color: transparent !important;
  outline: none !important;
}
</style>

