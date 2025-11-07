<template>
  <div class="windfarm-management-container">
    <div class="page-header">
      <div class="header-text">
        <h1 class="page-title">风电场可视化管理</h1>
        <p class="page-description">集中查看全量风电场的基础信息、运行状态与数据准备度</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" plain @click="refreshData" :loading="isLoading">刷新数据</el-button>
      </div>
    </div>

    <el-row :gutter="20" class="summary-grid">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card overview">
          <div class="card-label">风电场总数</div>
          <div class="card-value">{{ totalFarms }}</div>
          <div class="card-footnote">覆盖所有接入系统的场站</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card active">
          <div class="card-label">运行中</div>
          <div class="card-value">{{ activeFarms }}</div>
          <div class="card-footnote">当前标记为启用的场站</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card inactive">
          <div class="card-label">待上线</div>
          <div class="card-value">{{ inactiveFarms }}</div>
          <div class="card-footnote">需要关注的停用/未激活场站</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="summary-card capacity">
          <div class="card-label">装机容量 (MW)</div>
          <div class="card-value">{{ totalCapacity }}</div>
          <div class="card-footnote">合计容量，来源于场站配置</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-grid">
      <el-col :xs="24" :lg="14">
        <el-card class="panel-card">
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
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card class="panel-card map-panel">
          <div class="panel-header">
            <h2>地理分布 (规划中)</h2>
          </div>
          <div class="map-placeholder">
            <el-empty description="即将上线：地图分布视图" />
          </div>
        </el-card>
        <el-card class="panel-card kpi-panel">
          <div class="panel-header">
            <h2>数据准备度 (规划中)</h2>
          </div>
          <div class="kpi-placeholder">
            <el-empty description="将在后续版本展示各数据集覆盖情况" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWindFarmStore } from '@/store/windFarm'

export default {
  name: 'WindFarmManagement',
  setup() {
    const router = useRouter()
    const keyword = ref('')
    const {
      windFarms,
      isLoading,
      loadWindFarms,
      setSelectedWindFarm,
    } = useWindFarmStore()

    const totalFarms = computed(() => windFarms.value.length)
    const activeFarms = computed(() => windFarms.value.filter(farm => farm.is_active !== false).length)
    const inactiveFarms = computed(() => Math.max(totalFarms.value - activeFarms.value, 0))
    const totalCapacity = computed(() => {
      const sum = windFarms.value.reduce((acc, farm) => acc + (Number(farm.capacity) || 0), 0)
      return sum.toFixed(1)
    })

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

    const refreshData = async () => {
      await loadWindFarms()
    }

    const jumpToFarm = (farm) => {
      const code = farm.farm_code || farm.farm_name
      if (code) {
        setSelectedWindFarm(code)
      }
      router.push({ name: 'ReportManagement' })
    }

    onMounted(async () => {
      if (!windFarms.value.length) {
        await loadWindFarms()
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

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
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

.page-description {
  margin: 0;
  color: rgba(31, 45, 61, 0.65);
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

.farm-table {
  border-radius: 12px;
  overflow: hidden;
}

.map-placeholder,
.kpi-placeholder {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
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


