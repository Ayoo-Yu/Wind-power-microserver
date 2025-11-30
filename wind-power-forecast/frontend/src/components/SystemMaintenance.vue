<template>
  <DigitalPage>
    <DigitalHero
      eyebrow="OPERATIONS CONTROL"
      title="系统维护中枢"
      subtitle="实时掌握硬件配置、软件环境以及关键运行参数"
      :metrics="heroMetrics"
    >
      <template #meta>
        <span class="digital-status-chip">当前场站：{{ currentWindFarmDisplay || '未选择' }}</span>
      </template>
    </DigitalHero>

    <div class="digital-grid digital-grid--two-column">
      <el-card class="glass-panel" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Monitor /></el-icon>
            <span class="card-title">硬件系统</span>
            <el-button
              type="primary"
              size="small"
              @click="refreshHardwareInfo"
              :loading="loadingHardware"
            >
              刷新
            </el-button>
          </div>
        </template>

        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">CPU</span>
            <span class="info-value">{{ hardwareInfo.cpu }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">内存</span>
            <span class="info-value">{{ hardwareInfo.memory }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">存储</span>
            <span class="info-value">{{ hardwareInfo.storage }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">网络</span>
            <span class="info-value">{{ hardwareInfo.network }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">GPU</span>
            <span class="info-value">{{ hardwareInfo.gpu }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">系统架构</span>
            <span class="info-value">{{ hardwareInfo.architecture }}</span>
          </div>
        </div>
      </el-card>

      <el-card class="glass-panel" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Platform /></el-icon>
            <span class="card-title">软件系统</span>
            <el-button
              type="primary"
              size="small"
              @click="refreshSoftwareInfo"
              :loading="loadingSoftware"
            >
              刷新
            </el-button>
          </div>
        </template>

        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">操作系统</span>
            <span class="info-value">{{ softwareInfo.os }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Python版本</span>
            <span class="info-value">{{ softwareInfo.python }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Node.js版本</span>
            <span class="info-value">{{ softwareInfo.nodejs }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">数据库</span>
            <span class="info-value">{{ softwareInfo.database }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Web服务器</span>
            <span class="info-value">{{ softwareInfo.webserver }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">系统版本</span>
            <span class="info-value">{{ softwareInfo.version }}</span>
          </div>
        </div>
      </el-card>

      <el-card class="glass-panel runtime-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Setting /></el-icon>
            <span class="card-title">运行参数</span>
            <el-button
              type="primary"
              size="small"
              @click="refreshRuntimeInfo"
              :loading="loadingRuntime"
            >
              刷新
            </el-button>
          </div>
        </template>

        <div class="runtime-card__content">
          <div class="runtime-trend" v-if="runtimeHistory.labels.length">
            <canvas ref="runtimeChartCanvas"></canvas>
          </div>

          <div class="info-grid info-grid--runtime">
            <div class="info-item">
              <span class="info-label">系统运行时间</span>
              <span class="info-value">{{ runtimeInfo.uptime }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">CPU使用率</span>
              <span class="info-value">
                <el-progress
                  :percentage="runtimeInfo.cpuUsage"
                  :color="getProgressColor(runtimeInfo.cpuUsage)"
                  :show-text="true"
                  :format="(percentage) => `${percentage}%`"
                />
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">内存使用率</span>
              <span class="info-value">
                <el-progress
                  :percentage="runtimeInfo.memoryUsage"
                  :color="getProgressColor(runtimeInfo.memoryUsage)"
                  :show-text="true"
                  :format="(percentage) => `${percentage}%`"
                />
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">磁盘使用率</span>
              <span class="info-value">
                <el-progress
                  :percentage="runtimeInfo.diskUsage"
                  :color="getProgressColor(runtimeInfo.diskUsage)"
                  :show-text="true"
                  :format="(percentage) => `${percentage}%`"
                />
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">活跃连接数</span>
              <span class="info-value">{{ runtimeInfo.connections }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">最后更新时间</span>
              <span class="info-value">{{ runtimeInfo.lastUpdate }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <el-card class="glass-panel" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon class="card-icon"><Document /></el-icon>
          <span class="card-title">系统日志</span>
          <div class="log-controls">
            <el-select v-model="selectedLogLevel" placeholder="日志级别" size="small" style="width: 120px; margin-right: 10px;">
              <el-option label="全部" value="all" />
              <el-option label="错误" value="error" />
              <el-option label="警告" value="warning" />
              <el-option label="信息" value="info" />
            </el-select>
            <el-button
              type="primary"
              size="small"
              @click="refreshLogs"
              :loading="loadingLogs"
            >
              刷新日志
            </el-button>
          </div>
        </div>
      </template>

      <div class="log-container">
        <div v-if="logs.length === 0" class="no-logs">
          暂无日志信息
        </div>
        <transition-group
          v-else
          name="log-fade"
          tag="div"
          class="log-list"
          appear
        >
          <div
            v-for="log in filteredLogs"
            :key="log.id"
            :class="['log-item', `log-${log.level}`]"
          >
            <span class="log-time">{{ log.timestamp }}</span>
            <span class="log-level">{{ log.level.toUpperCase() }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </transition-group>
      </div>
    </el-card>
  </DigitalPage>
</template>

<script>
import { ref, computed, onMounted, watch, nextTick, onBeforeUnmount, markRaw } from 'vue'
import { ElMessage } from 'element-plus'
import axiosInstance from '../api/axios'
import { useWindFarmStore } from '@/store/windFarm'
import {
  Monitor,
  Platform,
  Setting,
  Document
} from '@element-plus/icons-vue'
import DigitalPage from './common/DigitalPage.vue'
import DigitalHero from './common/DigitalHero.vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend)

export default {
  name: 'SystemMaintenance',
  components: {
    DigitalPage,
    DigitalHero,
    Monitor,
    Platform,
    Setting,
    Document
  },
  setup() {
    const { selectedWindFarm, findWindFarmByCode } = useWindFarmStore()
    const currentWindFarmRecord = computed(() => findWindFarmByCode(selectedWindFarm.value))
    const currentWindFarmDisplay = computed(() => {
      const record = currentWindFarmRecord.value
      if (record) {
        return record.farm_name || record.farm_code || selectedWindFarm.value
      }
      return selectedWindFarm.value
    })

    // 加载状态
    const loadingHardware = ref(false)
    const loadingSoftware = ref(false)
    const loadingRuntime = ref(false)
    const loadingLogs = ref(false)

    // 硬件信息
    const hardwareInfo = ref({
      cpu: '获取中...',
      memory: '获取中...',
      storage: '获取中...',
      network: '获取中...',
      gpu: '获取中...',
      architecture: '获取中...'
    })

    // 软件信息
    const softwareInfo = ref({
      os: '获取中...',
      python: '获取中...',
      nodejs: '获取中...',
      database: '获取中...',
      webserver: '获取中...',
      version: '获取中...'
    })

    // 运行参数
    const runtimeInfo = ref({
      uptime: '获取中...',
      cpuUsage: 0,
      memoryUsage: 0,
      diskUsage: 0,
      connections: 0,
      lastUpdate: '获取中...'
    })
    const runtimeHistory = ref({
      labels: [],
      cpu: [],
      memory: [],
      disk: [],
    })
    const runtimeChartCanvas = ref(null)
    const runtimeTrendChart = ref(null)

    const heroMetrics = computed(() => [
      {
        id: 'uptime',
        label: '运行时间',
        value: runtimeInfo.value.uptime || '--',
        meta: '系统在线',
      },
      {
        id: 'cpuUsage',
        label: 'CPU 使用率',
        value: runtimeInfo.value.cpuUsage != null ? `${runtimeInfo.value.cpuUsage}%` : '--',
        meta: '实时监控',
      },
      {
        id: 'connections',
        label: '活跃连接',
        value: runtimeInfo.value.connections ?? 0,
        meta: '当前会话',
      },
    ])

    // 日志相关
    const selectedLogLevel = ref('all')
    const logs = ref([])

    // 过滤后的日志
    const filteredLogs = computed(() => {
      if (selectedLogLevel.value === 'all') {
        return logs.value
      }
      return logs.value.filter(log => log.level === selectedLogLevel.value)
    })

    // 获取进度条颜色
    const getProgressColor = (percentage) => {
      if (percentage < 50) return '#67c23a'
      if (percentage < 80) return '#e6a23c'
      return '#f56c6c'
    }

    const appendRuntimeSnapshot = (data) => {
      if (data == null) return
      const timestamp = new Date().toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
      const cpu = Number(data.cpuUsage ?? data.cpu_usage ?? 0)
      const memory = Number(data.memoryUsage ?? data.memory_usage ?? 0)
      const disk = Number(data.diskUsage ?? data.disk_usage ?? 0)

      const history = runtimeHistory.value
      history.labels.push(timestamp)
      history.cpu.push(cpu)
      history.memory.push(memory)
      history.disk.push(disk)

      const maxPoints = 14
      if (history.labels.length > maxPoints) {
        history.labels.shift()
        history.cpu.shift()
        history.memory.shift()
        history.disk.shift()
      }

      nextTick(() => {
        updateRuntimeChart()
      })
    }

    const buildGradient = (ctx, color) => {
      const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height || 180)
      gradient.addColorStop(0, `${color}70`)
      gradient.addColorStop(1, `${color}05`)
      return gradient
    }

    const createRuntimeChart = () => {
      if (!runtimeChartCanvas.value || runtimeTrendChart.value) {
        return
      }
      const ctx = runtimeChartCanvas.value.getContext('2d')
      const labels = [...runtimeHistory.value.labels]
      const cpuData = [...runtimeHistory.value.cpu]
      const memoryData = [...runtimeHistory.value.memory]
      const diskData = [...runtimeHistory.value.disk]
      runtimeTrendChart.value = markRaw(new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'CPU%',
              data: cpuData,
              borderColor: '#38c4ff',
              backgroundColor: buildGradient(ctx, '#38c4ff'),
              fill: true,
              tension: 0.38,
              pointRadius: 0,
            },
            {
              label: '内存%',
              data: memoryData,
              borderColor: '#22f6aa',
              backgroundColor: buildGradient(ctx, '#22f6aa'),
              fill: true,
              tension: 0.38,
              pointRadius: 0,
            },
            {
              label: '磁盘%',
              data: diskData,
              borderColor: '#ffaf45',
              backgroundColor: buildGradient(ctx, '#ffaf45'),
              fill: true,
              tension: 0.38,
              pointRadius: 0,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          responsive: true,
          plugins: {
            legend: {
              display: true,
              labels: {
                color: '#88a1c6',
                usePointStyle: true,
                boxWidth: 10,
              },
            },
            tooltip: {
              mode: 'index',
              intersect: false,
              displayColors: false,
              callbacks: {
                title: (items) => (items[0] ? `刷新：${items[0].label}` : ''),
                label: (context) => `${context.dataset.label}：${context.formattedValue}%`,
              },
            },
          },
          scales: {
            x: {
              grid: {
                display: false,
              },
              ticks: {
                color: '#617093',
                maxRotation: 0,
              },
            },
            y: {
              min: 0,
              max: 100,
              grid: {
                color: 'rgba(255,255,255,0.04)',
              },
              ticks: {
                color: '#617093',
                callback: (value) => `${value}%`,
              },
            },
          },
          interaction: {
            mode: 'index',
            intersect: false,
          },
          animation: {
            duration: 600,
            easing: 'easeOutCubic',
          },
        },
      }))
    }

    const updateRuntimeChart = () => {
      if (!runtimeHistory.value.labels.length) {
        return
      }
      if (!runtimeTrendChart.value) {
        createRuntimeChart()
      }
      const chart = runtimeTrendChart.value
      if (!chart) return
      chart.data.labels = [...runtimeHistory.value.labels]
      chart.data.datasets[0].data = [...runtimeHistory.value.cpu]
      chart.data.datasets[1].data = [...runtimeHistory.value.memory]
      chart.data.datasets[2].data = [...runtimeHistory.value.disk]
      chart.update('active')
    }

    // 刷新硬件信息
    const refreshHardwareInfo = async () => {
      loadingHardware.value = true
      try {
        const response = await axiosInstance.get('system/hardware')
        hardwareInfo.value = response.data
        ElMessage.success('硬件信息已更新')
      } catch (error) {
        console.error('获取硬件信息失败:', error)
        ElMessage.error('获取硬件信息失败')
      } finally {
        loadingHardware.value = false
      }
    }

    // 刷新软件信息
    const refreshSoftwareInfo = async () => {
      loadingSoftware.value = true
      try {
        const response = await axiosInstance.get('system/software')
        softwareInfo.value = response.data
        ElMessage.success('软件信息已更新')
      } catch (error) {
        console.error('获取软件信息失败:', error)
        ElMessage.error('获取软件信息失败')
      } finally {
        loadingSoftware.value = false
      }
    }

    // 刷新运行参数
    const refreshRuntimeInfo = async () => {
      loadingRuntime.value = true
      try {
        const response = await axiosInstance.get('system/runtime')
        runtimeInfo.value = response.data
        appendRuntimeSnapshot(response.data)
        ElMessage.success('运行参数已更新')
      } catch (error) {
        console.error('获取运行参数失败:', error)
        ElMessage.error('获取运行参数失败')
      } finally {
        loadingRuntime.value = false
      }
    }

    // 刷新日志
    const refreshLogs = async () => {
      loadingLogs.value = true
      try {
        const response = await axiosInstance.get('system/logs')
        logs.value = response.data
        ElMessage.success('日志已更新')
      } catch (error) {
        console.error('获取日志失败:', error)
        ElMessage.error('获取日志失败')
      } finally {
        loadingLogs.value = false
      }
    }

    // 初始化所有数据
    const initializeData = async () => {
      await Promise.all([
        refreshHardwareInfo(),
        refreshSoftwareInfo(),
        refreshRuntimeInfo(),
        refreshLogs()
      ])
    }

    // 组件挂载时初始化
    onMounted(async () => {
      await initializeData()
      nextTick(() => {
        createRuntimeChart()
      })
    })

    watch(() => selectedWindFarm.value, () => {
      initializeData()
      ElMessage.info(`已切换到场站：${currentWindFarmDisplay.value}`)
    })

    onBeforeUnmount(() => {
      if (runtimeTrendChart.value) {
        runtimeTrendChart.value.destroy()
        runtimeTrendChart.value = null
      }
    })

    return {
      currentWindFarmDisplay,
      loadingHardware,
      loadingSoftware,
      loadingRuntime,
      loadingLogs,
      hardwareInfo,
      softwareInfo,
      runtimeInfo,
      runtimeHistory,
      runtimeChartCanvas,
      heroMetrics,
      selectedLogLevel,
      logs,
      filteredLogs,
      getProgressColor,
      refreshHardwareInfo,
      refreshSoftwareInfo,
      refreshRuntimeInfo,
      refreshLogs
    }
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-icon {
  font-size: 22px;
  padding: 10px;
  border-radius: 14px;
  background: rgba(56, 196, 255, 0.12);
  color: #38c4ff;
  box-shadow: 0 12px 24px rgba(56, 196, 255, 0.18);
}

.card-title {
  font-weight: 600;
  font-size: 20px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.log-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 18px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 20px;
  border-radius: 14px;
  background: rgba(4, 18, 36, 0.72);
  border: 1px solid rgba(56, 196, 255, 0.12);
  box-shadow: inset 0 0 0 1px rgba(56, 196, 255, 0.05);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.info-item:hover {
  transform: translateY(-2px);
  box-shadow: inset 0 0 0 1px rgba(56, 196, 255, 0.18);
}

.info-label {
  font-size: 13px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.info-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.04em;
}

.info-grid--runtime .info-item {
  min-height: 120px;
  justify-content: space-between;
}

.info-grid--runtime .info-item :deep(.el-progress) {
  width: 100%;
}

.runtime-card {
  grid-column: 1 / -1;
}

.runtime-card__content {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.runtime-trend {
  position: relative;
  width: 100%;
  height: 220px;
  border-radius: 18px;
  background: linear-gradient(160deg, rgba(9, 26, 54, 0.72) 0%, rgba(4, 18, 36, 0.85) 100%);
  border: 1px solid rgba(56, 196, 255, 0.16);
  box-shadow: inset 0 0 20px rgba(56, 196, 255, 0.08);
  overflow: hidden;
}

.runtime-trend::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(circle at 20% 20%, rgba(56, 196, 255, 0.22), transparent 55%);
  opacity: 0.35;
}

.runtime-trend canvas {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
}

.log-container {
  max-height: 420px;
  overflow-y: auto;
}

.no-logs {
  text-align: center;
  color: var(--text-secondary);
  padding: 48px 0;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  border-radius: 12px;
  background: rgba(4, 18, 36, 0.72);
  border-left: 4px solid rgba(56, 196, 255, 0.18);
  box-shadow: 0 12px 24px rgba(3, 13, 30, 0.35);
  opacity: 0.92;
}

.log-item.log-warning {
  border-left-color: rgba(230, 162, 60, 0.6);
}

.log-item.log-error {
  border-left-color: rgba(245, 108, 108, 0.6);
}

.log-time {
  flex-shrink: 0;
  width: 140px;
  color: var(--text-secondary);
  font-family: 'Courier New', monospace;
}

.log-level {
  flex-shrink: 0;
  width: 60px;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

.log-message {
  flex: 1;
  color: var(--text-primary);
  margin-left: 16px;
}

.log-container::-webkit-scrollbar {
  width: 6px;
}

.log-container::-webkit-scrollbar-track {
  background: rgba(4, 18, 36, 0.6);
  border-radius: 3px;
}

.log-container::-webkit-scrollbar-thumb {
  background: rgba(56, 196, 255, 0.35);
  border-radius: 3px;
}

.log-container::-webkit-scrollbar-thumb:hover {
  background: rgba(56, 196, 255, 0.5);
}

.log-fade-enter-active,
.log-fade-leave-active {
  transition: all 0.35s ease;
}

.log-fade-enter-from,
.log-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.log-fade-move {
  transition: transform 0.35s ease;
}

@media (max-width: 1280px) {
  .runtime-card {
    grid-column: auto;
  }
}
</style>