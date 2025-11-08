<template>
  <DigitalPage>
    <DigitalHero
      eyebrow="WIND FARM OPERATIONS"
      title="风电场可视化管理"
      subtitle="集中查看全量风电场的基础信息、运行状态与数据准备度"
      :metrics="heroMetrics"
    >
      <template #meta>
        <span class="digital-status-chip">当前场站：{{ currentWindFarmDisplay || '未选择' }}</span>
      </template>
      <template #actions>
        <el-button type="primary" @click="refreshData" :loading="isLoading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </template>
    </DigitalHero>

    <el-row :gutter="24" class="management-grid">
      <el-col :xs="24" :lg="14">
        <el-card class="glass-panel" shadow="never">
          <div class="panel-header">
            <h2>风电场列表</h2>
            <div class="panel-actions">
              <el-input
                v-model="keyword"
                placeholder="搜索名称或编码"
                prefix-icon="Search"
                size="small"
                clearable
              />
            </div>
          </div>
          <el-table
            :data="filteredFarms"
            v-loading="isLoading"
            border
            stripe
            size="small"
            class="farm-table"
            height="360"
          >
            <el-table-column prop="farm_name" label="场站名称" min-width="180" />
            <el-table-column prop="farm_code" label="编码" min-width="120" />
            <el-table-column prop="capacity" label="装机容量(MW)" min-width="140">
              <template #default="{ row }">
                {{ row.capacity ?? '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="region" label="所属区域" min-width="140">
              <template #default="{ row }">
                {{ row.region || row.province || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active === false ? 'info' : 'success'" effect="dark">
                  {{ row.is_active === false ? '停用' : '启用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" text size="small" @click="jumpToFarm(row)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="glass-panel readiness-panel" v-loading="readinessLoading" shadow="never">
          <div class="panel-header">
            <h2>数据准备度</h2>
            <span class="panel-subtitle">展示训练/预测/仿真数据的上传覆盖情况</span>
          </div>
          <div
            class="readiness-container"
            :class="{ 'readiness-container--active': hasReadinessData }"
          >
            <canvas v-if="hasReadinessData" ref="readinessCanvas" class="readiness-chart"></canvas>
            <el-empty v-else description="暂无可用数据" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card class="glass-panel map-panel" shadow="never">
          <div class="panel-header">
            <h2>地理分布</h2>
            <span class="panel-subtitle">基于经纬度的场站位置散点图</span>
          </div>
          <div class="map-container" v-loading="isLoading">
            <div v-if="hasMapData" ref="mapContainer" class="map-scatter"></div>
            <el-empty v-else description="暂未获取到经纬度信息" />
          </div>
        </el-card>

        <el-card class="glass-panel action-panel" shadow="never">
          <div class="panel-header">
            <h2>快捷操作</h2>
            <span class="panel-subtitle">选择目标场站后快速进入相关模块</span>
          </div>
          <div class="action-body">
            <el-form label-position="top" class="action-form">
              <el-form-item label="目标场站">
                <el-select
                  v-model="actionFarmCode"
                  filterable
                  placeholder="请选择场站"
                  size="small"
                >
                  <el-option
                    v-for="farm in windFarms"
                    :key="farm.farm_code || farm.farm_name"
                    :label="farm.farm_name ? `${farm.farm_name}${farm.farm_code ? ` (${farm.farm_code})` : ''}` : (farm.farm_code || '默认场站')"
                    :value="farm.farm_code || farm.farm_name"
                  />
                </el-select>
              </el-form-item>
            </el-form>
            <el-row :gutter="12" class="action-grid">
              <el-col :xs="12">
                <el-card class="action-card" shadow="hover" @click="navigateTo('ModelTrain')">
                  <div class="action-title">模型训练</div>
                  <div class="action-desc">转至训练模块，使用最新数据训练模型</div>
                </el-card>
              </el-col>
              <el-col :xs="12">
                <el-card class="action-card" shadow="hover" @click="navigateTo('PowerCompare')">
                  <div class="action-title">功率对比</div>
                  <div class="action-desc">查看预测 vs 实测曲线与指标</div>
                </el-card>
              </el-col>
              <el-col :xs="12">
                <el-card class="action-card" shadow="hover" @click="navigateTo('ReportManagement')">
                  <div class="action-title">上报配置</div>
                  <div class="action-desc">配置或查看该场站的自动上报任务</div>
                </el-card>
              </el-col>
              <el-col :xs="12">
                <el-card class="action-card" shadow="hover" @click="navigateTo('PhysicalSimulation')">
                  <div class="action-title">物理仿真</div>
                  <div class="action-desc">跳转至仿真页面，查看或上传仿真数据</div>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </DigitalPage>
</template>

<script>
import { ref, computed, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useWindFarmStore } from '@/store/windFarm'
import axiosInstance from '../api/axios'
import Plotly from 'plotly.js-dist-min'
import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
  Title,
} from 'chart.js'
import DigitalPage from './common/DigitalPage.vue'
import DigitalHero from './common/DigitalHero.vue'

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend, Title)

export default {
  name: 'WindFarmManagement',
  components: {
    DigitalPage,
    DigitalHero,
  },
  setup() {
    const router = useRouter()
    const keyword = ref('')
    const actionFarmCode = ref('')
    const readinessCanvas = ref(null)
    const readinessChart = ref(null)
    const readinessMetrics = ref([])
    const readinessLoading = ref(false)
    const mapContainer = ref(null)
    const mapAnimationPlayed = ref(false)
    const {
      windFarms,
      isLoading,
      loadWindFarms,
      setSelectedWindFarm,
      selectedWindFarm,
    } = useWindFarmStore()

    const totalFarms = computed(() => windFarms.value.length)
    const activeFarms = computed(() => windFarms.value.filter(farm => farm.is_active !== false).length)
    const inactiveFarms = computed(() => Math.max(totalFarms.value - activeFarms.value, 0))
    const totalCapacity = computed(() => {
      const sum = windFarms.value.reduce((acc, farm) => acc + (Number(farm.capacity) || 0), 0)
      return sum.toFixed(1)
    })

    const heroMetrics = computed(() => [
      {
        id: 'total',
        label: '风电场总数',
        value: totalFarms.value,
        meta: '覆盖所有接入系统的场站',
      },
      {
        id: 'active',
        label: '运行中',
        value: activeFarms.value,
        meta: '当前标记为启用的场站',
      },
      {
        id: 'inactive',
        label: '待上线',
        value: inactiveFarms.value,
        meta: '需关注的停用/未激活场站',
      },
      {
        id: 'capacity',
        label: '装机容量',
        value: totalCapacity.value,
        unit: 'MW',
        meta: '合计容量，来源于场站配置',
      },
    ])

    const currentWindFarmDisplay = computed(() => {
      if (!selectedWindFarm.value) {
        return '未选择'
      }
      const farm = windFarms.value.find(f => f.farm_code === selectedWindFarm.value)
      return farm ? `${farm.farm_name}${farm.farm_code ? ` (${farm.farm_code})` : ''}` : '未选择'
    })

    const hasValidCoord = (farm) => farm && farm.latitude !== undefined && farm.latitude !== null && farm.longitude !== undefined && farm.longitude !== null
    const hasMapData = computed(() => windFarms.value.some(hasValidCoord))
    const hasReadinessData = computed(() => readinessMetrics.value.length > 0 && readinessMetrics.value.some(item => item.training_datasets || item.prediction_datasets || item.simulation_records))

    const filteredFarms = computed(() => {
      if (!keyword.value) {
        return windFarms.value
      }
      const lower = keyword.value.toLowerCase()
      return windFarms.value.filter(farm =>
        (farm.farm_name && farm.farm_name.toLowerCase().includes(lower)) ||
        (farm.farm_code && farm.farm_code.toLowerCase().includes(lower))
      )
    })

    const drawFarmMap = () => {
      if (!mapContainer.value) {
        return
      }

      const farmsWithCoords = windFarms.value
        .filter(hasValidCoord)
        .map(farm => ({
          name: farm.farm_name || farm.farm_code,
          code: farm.farm_code,
          lat: Number(farm.latitude),
          lon: Number(farm.longitude),
          capacity: Number(farm.capacity) || 0,
          status: farm.is_active === false ? '停用' : '启用',
        }))

      if (!farmsWithCoords.length) {
        if (mapContainer.value && mapContainer.value.data) {
          Plotly.purge(mapContainer.value)
        }
        return
      }

      const baseMarkerSizes = farmsWithCoords.map(f => Math.max(Math.sqrt(f.capacity) * 2, 8))
      const targetOpacity = 0.85
      const trace = {
        x: farmsWithCoords.map(f => f.lon),
        y: farmsWithCoords.map(f => f.lat),
        text: farmsWithCoords.map(f => `${f.name || f.code}<br/>装机容量: ${f.capacity} MW<br/>状态: ${f.status}`),
        mode: 'markers',
        marker: {
          size: mapAnimationPlayed.value
            ? baseMarkerSizes
            : baseMarkerSizes.map(size => Math.max(size * 0.45, 6)),
          color: farmsWithCoords.map(f => f.status === '启用' ? '#2ecc71' : '#95a5a6'),
          opacity: mapAnimationPlayed.value ? targetOpacity : 0.2,
          line: { width: 1, color: '#2c3e50' },
        },
        hovertemplate: '%{text}<extra></extra>',
        type: 'scatter'
      }

      const layout = {
        margin: { l: 40, r: 20, t: 20, b: 40 },
        xaxis: { title: '经度', zeroline: false, showgrid: false },
        yaxis: { title: '纬度', zeroline: false, showgrid: false },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        hovermode: 'closest',
        transition: { duration: 500, easing: 'cubic-in-out' },
      }

      const config = {
        responsive: true,
        displaylogo: false,
        scrollZoom: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d']
      }

      const reactResult = Plotly.react(mapContainer.value, [trace], layout, config)

      Promise.resolve(reactResult)
        .then(() => {
          if (!mapAnimationPlayed.value) {
            mapAnimationPlayed.value = true
            Plotly.animate(
              mapContainer.value,
              {
                data: [
                  {
                    marker: {
                      size: baseMarkerSizes,
                      opacity: targetOpacity,
                    },
                  },
                ],
              },
              {
                transition: { duration: 700, easing: 'cubic-in-out' },
                frame: { duration: 700, redraw: false },
              }
            ).catch(() => {
              /*
               * Plotly.animate 在部分情况下（如组件卸载）可能被中断，
               * 这里捕获异常以避免打断流程。
               */
            })
          }
        })
        .catch(() => {
          // ignore animate preparation errors
        })
    }

    const fetchReadinessMetrics = async () => {
      readinessLoading.value = true
      try {
        const response = await axiosInstance.get('report/farms/data-readiness', {
          validateStatus: status => status < 400 || status === 404 || status === 405,
        })

        if (response.status >= 400) {
          console.info('数据准备度接口不可用，使用基础数据兜底 (status:', response.status, ')')
          throw new Error(`data-readiness endpoint unavailable (status ${response.status})`)
        }

        const data = Array.isArray(response.data) ? response.data : []
        readinessMetrics.value = data.map(item => ({
          farm_code: item.farm_code,
          farm_name: item.farm_name,
          training_datasets: Number(item.training_datasets) || 0,
          prediction_datasets: Number(item.prediction_datasets) || 0,
          simulation_records: Number(item.simulation_records) || 0,
        }))
      } catch (error) {
        if (error instanceof Error) {
          console.warn('获取数据准备度失败，使用基础数据兜底', error.message || error)
        }
        readinessMetrics.value = windFarms.value.map(farm => ({
          farm_code: farm.farm_code,
          farm_name: farm.farm_name,
          training_datasets: Number(farm.training_dataset_count) || 0,
          prediction_datasets: Number(farm.prediction_dataset_count) || 0,
          simulation_records: Number(farm.simulation_record_count) || 0,
        })).filter(item => item.training_datasets || item.prediction_datasets || item.simulation_records)
      } finally {
        readinessLoading.value = false
        nextTick(() => updateReadinessChart())
      }
    }

    const updateReadinessChart = () => {
      if (!readinessCanvas.value) {
        return
      }
      if (readinessChart.value) {
        readinessChart.value.destroy()
        readinessChart.value = null
      }
      if (!hasReadinessData.value) {
        return
      }

      const labels = readinessMetrics.value.map(item => item.farm_name || item.farm_code)
      const trainingData = readinessMetrics.value.map(item => item.training_datasets)
      const predictionData = readinessMetrics.value.map(item => item.prediction_datasets)
      const simulationData = readinessMetrics.value.map(item => item.simulation_records)

      const animationConfig = {
        duration: 900,
        easing: 'easeOutQuart',
        delay: (context) => {
          if (context.type === 'data' && context.mode === 'default') {
            return context.dataIndex * 140 + context.datasetIndex * 80
          }
          return 0
        },
      }

      readinessChart.value = new Chart(readinessCanvas.value.getContext('2d'), {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: '训练数据集',
              data: trainingData,
              backgroundColor: 'rgba(87, 109, 234, 0.8)',
              borderRadius: 6,
            },
            {
              label: '预测数据集',
              data: predictionData,
              backgroundColor: 'rgba(46, 204, 113, 0.8)',
              borderRadius: 6,
            },
            {
              label: '仿真记录',
              data: simulationData,
              backgroundColor: 'rgba(255, 159, 67, 0.85)',
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          indexAxis: 'y',
          maintainAspectRatio: false,
          animation: animationConfig,
          animations: {
            x: {
              easing: 'easeOutQuart',
              duration: 700,
            },
            y: {
              easing: 'easeOutQuart',
              duration: 700,
            },
          },
          scales: {
            x: {
              stacked: true,
              grid: { color: 'rgba(0,0,0,0.08)' },
              ticks: { color: '#4c576f' },
            },
            y: {
              stacked: true,
              grid: { display: false },
              ticks: { color: '#4c576f' },
            },
          },
          plugins: {
            legend: {
              position: 'top',
              labels: { color: '#2c3e50' },
            },
            tooltip: {
              callbacks: {
                label: (context) => `${context.dataset.label}: ${context.raw}`,
              },
            },
          },
        },
      })
    }

    const refreshData = async () => {
      await Promise.all([loadWindFarms(), fetchReadinessMetrics()])
    }

    const jumpToFarm = (farm) => {
      const code = farm.farm_code || farm.farm_name
      if (code) {
        setSelectedWindFarm(code)
      }
      router.push({ name: 'ReportManagement' })
    }

    const navigateTo = (routeName) => {
      if (actionFarmCode.value) {
        setSelectedWindFarm(actionFarmCode.value)
      }
      router.push({ name: routeName })
    }

    onMounted(async () => {
      if (!windFarms.value.length) {
        await loadWindFarms()
      }
      if (!actionFarmCode.value && windFarms.value.length) {
        actionFarmCode.value = windFarms.value[0].farm_code || windFarms.value[0].farm_name
      }
      await fetchReadinessMetrics()
      nextTick(() => drawFarmMap())
    })

    watch(windFarms, async (newList) => {
      if (!actionFarmCode.value && newList.length) {
        actionFarmCode.value = newList[0].farm_code || newList[0].farm_name
      }
      await nextTick()
      drawFarmMap()
      if (!readinessLoading.value && hasReadinessData.value) {
        updateReadinessChart()
      }
    }, { deep: true })

    watch(readinessMetrics, () => {
      nextTick(() => updateReadinessChart())
    }, { deep: true })

    onBeforeUnmount(() => {
      if (readinessChart.value) {
        readinessChart.value.destroy()
        readinessChart.value = null
      }
      if (mapContainer.value && mapContainer.value.data) {
        Plotly.purge(mapContainer.value)
      }
    })

    return {
      keyword,
      isLoading,
      totalFarms,
      activeFarms,
      inactiveFarms,
      totalCapacity,
      filteredFarms,
      refreshData,
      jumpToFarm,
      hasMapData,
      mapContainer,
      readinessCanvas,
      readinessLoading,
      hasReadinessData,
      actionFarmCode,
      windFarms,
      navigateTo,
      currentWindFarmDisplay,
      heroMetrics,
    }
  },
}
</script>

<style scoped>
.management-grid {
  margin-top: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.panel-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.panel-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  letter-spacing: 0.08em;
}

.farm-table {
  border-radius: 12px;
  overflow: hidden;
}

.readiness-panel {
  margin-top: 24px;
}

.readiness-container {
  min-height: 260px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 20px;
}

.readiness-container::after {
  content: '';
  position: absolute;
  inset: 16px;
  border-radius: 18px;
  border: 1px dashed rgba(66, 195, 255, 0.18);
  background: radial-gradient(circle at 50% 50%, rgba(66, 195, 255, 0.08), transparent 65%);
  opacity: 0;
  transition: opacity 0.6s ease;
  pointer-events: none;
}

.readiness-container--active::after {
  opacity: 0.45;
  animation: readinessPulse 6s ease-in-out infinite;
}

.readiness-chart {
  width: 100%;
  height: 260px;
  z-index: 1;
}

.map-container {
  min-height: 260px;
  position: relative;
}

.map-scatter {
  width: 100%;
  height: 260px;
}

.action-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-grid {
  margin-top: 8px;
}

.action-card {
  position: relative;
  overflow: hidden;
  border-radius: 14px;
  cursor: pointer;
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease;
  min-height: 120px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: linear-gradient(150deg, rgba(8, 24, 48, 0.82) 0%, rgba(6, 18, 36, 0.92) 100%);
  border: 1px solid rgba(66, 195, 255, 0.16);
  box-shadow: 0 14px 28px rgba(8, 24, 48, 0.35);
}

.action-card::after {
  content: '';
  position: absolute;
  inset: -40% -120%;
  background: linear-gradient(115deg, rgba(66, 195, 255, 0.0) 10%, rgba(66, 195, 255, 0.35) 48%, rgba(66, 195, 255, 0.0) 76%);
  transform: translateX(-120%);
  opacity: 0;
  transition: transform 0.6s ease, opacity 0.6s ease;
  pointer-events: none;
}

.action-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.action-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 22px 44px rgba(8, 24, 48, 0.55);
  border-color: rgba(66, 195, 255, 0.45);
}

.action-card:hover::after {
  opacity: 0.55;
  transform: translateX(120%);
}

.action-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.action-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

@keyframes readinessPulse {
  0% {
    transform: scale(0.98);
    opacity: 0.28;
  }
  50% {
    transform: scale(1);
    opacity: 0.45;
  }
  100% {
    transform: scale(0.98);
    opacity: 0.28;
  }
}

@media (max-width: 1024px) {
  .management-grid {
    margin-top: 0;
  }
}
</style>


