<template>
  <div class="windfarm-management-container">
    <div class="page-shell windfarm-management-content">
      <div class="header-panel glass-panel">
        <div class="header-text">
          <h1 class="page-title">风电场可视化管理</h1>
          <p class="page-subtitle">集中查看全量风电场的基础信息、运行状态与数据准备度</p>
        </div>
        <div class="header-actions">
          <span class="status-indicator wind-farm-chip">当前场站：{{ currentWindFarmDisplay || '未选择' }}</span>
          <el-button type="primary" @click="refreshData" :loading="isLoading">
            <el-icon><Refresh /></el-icon>
            刷新数据
          </el-button>
        </div>
      </div>

    <el-row :gutter="20" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card overview glass-panel">
          <div class="card-label">风电场总数</div>
          <div class="card-value">{{ totalFarms }}</div>
          <div class="card-footnote">覆盖所有接入系统的场站</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card active glass-panel">
          <div class="card-label">运行中</div>
          <div class="card-value">{{ activeFarms }}</div>
          <div class="card-footnote">当前标记为启用的场站</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card inactive glass-panel">
          <div class="card-label">待上线</div>
          <div class="card-value">{{ inactiveFarms }}</div>
          <div class="card-footnote">需重点关注的停用/未激活场站</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card capacity glass-panel">
          <div class="card-label">装机容量 (MW)</div>
          <div class="card-value">{{ totalCapacity }}</div>
          <div class="card-footnote">合计容量，来源于场站配置</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-grid">
      <el-col :xs="24" :lg="14">
        <el-card class="panel-card glass-panel">
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

        <el-card class="panel-card readiness-panel glass-panel" v-loading="readinessLoading">
          <div class="panel-header">
            <h2>数据准备度</h2>
            <span class="panel-subtitle">展示训练/预测/仿真数据的上传覆盖情况</span>
          </div>
          <div class="readiness-container">
            <canvas v-if="hasReadinessData" ref="readinessCanvas" class="readiness-chart"></canvas>
            <el-empty v-else description="暂无可用数据" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card class="panel-card map-panel glass-panel">
          <div class="panel-header">
            <h2>地理分布</h2>
            <span class="panel-subtitle">基于经纬度的场站位置散点图</span>
          </div>
          <div class="map-container" v-loading="isLoading">
            <div v-if="hasMapData" ref="mapContainer" class="map-scatter"></div>
            <el-empty v-else description="暂未获取到经纬度信息" />
          </div>
        </el-card>

        <el-card class="panel-card action-panel glass-panel">
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
    </div>
  </div>
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

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend, Title)

export default {
  name: 'WindFarmManagement',
  setup() {
    const router = useRouter()
    const keyword = ref('')
    const actionFarmCode = ref('')
    const readinessCanvas = ref(null)
    const readinessChart = ref(null)
    const readinessMetrics = ref([])
    const readinessLoading = ref(false)
    const mapContainer = ref(null)
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

      const trace = {
        x: farmsWithCoords.map(f => f.lon),
        y: farmsWithCoords.map(f => f.lat),
        text: farmsWithCoords.map(f => `${f.name || f.code}<br/>装机容量: ${f.capacity} MW<br/>状态: ${f.status}`),
        mode: 'markers',
        marker: {
          size: farmsWithCoords.map(f => Math.max(Math.sqrt(f.capacity) * 2, 8)),
          color: farmsWithCoords.map(f => f.status === '启用' ? '#2ecc71' : '#95a5a6'),
          opacity: 0.85,
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
      }

      Plotly.react(mapContainer.value, [trace], layout, { responsive: true, displaylogo: false })
    }

    const fetchReadinessMetrics = async () => {
      readinessLoading.value = true
      try {
        const response = await axiosInstance.get('/report/farms/data-readiness', {
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
    }
  },
}
</script>

<style scoped>
.windfarm-management-container {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-shell {
  background-color: #f5f7ff;
  border-radius: 24px;
  padding: 24px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
}

.header-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px 24px;
  background-color: #ffffff;
  border-radius: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.page-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: #1f2d3d;
}

.page-subtitle {
  margin: 0;
  color: rgba(31, 45, 61, 0.65);
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-indicator {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
  background-color: #e0e6ed;
  padding: 4px 10px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.wind-farm-chip {
  background-color: #e0e6ed;
  color: #1f2d3d;
}

.summary-grid {
  margin-bottom: 8px;
}

.summary-card {
  border-radius: 16px;
  border: none;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
  padding: 16px;
}

.summary-card .card-label {
  font-size: 14px;
  color: rgba(31, 45, 61, 0.6);
}

.summary-card .card-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2d3d;
}

.summary-card .card-footnote {
  font-size: 12px;
  color: rgba(31, 45, 61, 0.55);
  margin-top: 6px;
}

.summary-card.overview {
  background: linear-gradient(135deg, #f5f7ff 0%, #edefff 100%);
}

.summary-card.active {
  background: linear-gradient(135deg, #e5fff6 0%, #f0fff1 100%);
}

.summary-card.inactive {
  background: linear-gradient(135deg, #fff4f4 0%, #ffecec 100%);
}

.summary-card.capacity {
  background: linear-gradient(135deg, #f4f9ff 0%, #e8f3ff 100%);
}

.glass-panel {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.content-grid {
  margin-bottom: 16px;
}

.panel-card {
  border-radius: 18px;
  border: none;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
}


.panel-actions {
  display: flex;
  gap: 8px;
}

.panel-subtitle {
  font-size: 12px;
  color: rgba(31, 45, 61, 0.55);
}

.farm-table {
  border-radius: 12px;
  overflow: hidden;
}

.map-container {
  min-height: 260px;
  position: relative;
}

.map-scatter {
  width: 100%;
  height: 260px;
}

.readiness-panel {
  margin-top: 20px;
}

.readiness-container {
  min-height: 260px;
  position: relative;
}

.readiness-chart {
  width: 100%;
  height: 260px;
}

.action-panel {
  margin-top: 20px;
}

.action-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-form {
  margin-bottom: 4px;
}

.action-grid {
  margin-top: 4px;
}

.action-card {
  border-radius: 14px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  min-height: 120px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.action-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 36px rgba(87, 109, 234, 0.25);
}

.action-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2d3d;
}

.action-desc {
  font-size: 12px;
  color: rgba(31, 45, 61, 0.6);
}

@media (max-width: 1024px) {
  .windfarm-management-container {
    padding: 16px;
  }

  .page-title {
    font-size: 24px;
  }
}
</style>


