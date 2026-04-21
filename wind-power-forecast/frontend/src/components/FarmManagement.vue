<template>
  <div class="page-shell farm-management">
    <el-card class="panel-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">场站管理</div>
            <div class="sub">卡片 / 表格 / 地图三视图，支持场站启停与高级参数配置</div>
          </div>
          <div class="actions">
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button label="card">卡片</el-radio-button>
              <el-radio-button label="table">表格</el-radio-button>
              <el-radio-button label="map">地图</el-radio-button>
            </el-radio-group>
            <el-button type="primary" @click="openCreateDrawer">新建场站</el-button>
          </div>
        </div>
      </template>

      <div v-if="!loading && farms.length === 0" class="empty-state panel-card">
        <el-icon><WindPower /></el-icon>
        <p>暂无场站数据，请先新建场站。</p>
      </div>

      <div v-else-if="viewMode === 'card'" class="farm-grid">
        <el-card v-for="row in farms" :key="row.farm_code" class="farm-card" shadow="hover">
          <div class="card-header">
            <div class="left">
              <div class="farm-title">{{ row.farm_name }} | {{ toMw(row.capacity) }} MW</div>
              <div class="farm-code">{{ row.farm_code }}</div>
            </div>
            <div class="status-pill" :class="row.is_active ? 'active' : 'inactive'">
              <StatusDot :active="row.is_active" />
              <span>{{ row.is_active ? '运行中' : '离线' }}</span>
            </div>
          </div>

          <div class="core-meta">
            <div class="meta-item">
              <span class="meta-label">省份/区域</span>
              <span class="meta-value">{{ row.province || '-' }} / {{ row.region || '-' }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">机组台数</span>
              <span class="meta-value">{{ row.turbine_count || 0 }} 台</span>
            </div>
          </div>

          <div class="biz-status">
            <div class="biz-row">
              <span>当前实测</span>
              <strong>{{ toMw(row.current_actual_power) }} MW</strong>
            </div>
            <div class="biz-row">
              <span>数据源状态</span>
              <span class="source-status">
                SCADA({{ normalizeSourceLabel(row.scada_status) }}) | NWP({{ normalizeSourceLabel(row.nwp_status) }})
              </span>
            </div>
          </div>

          <div class="card-footer">
            <el-switch
              :model-value="!!row.is_active"
              active-text="启用"
              inactive-text="停用"
              @change="(val) => handleSetActive(row, val)"
            />
            <div class="footer-actions">
              <el-button size="small" @click="openEditDrawer(row)">编辑参数</el-button>
              <el-button size="small" type="warning" @click="handleTogglePredict(row)">
                {{ row.is_active ? '停用预测' : '启用预测' }}
              </el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </div>
          </div>
        </el-card>
      </div>

      <el-table v-else-if="viewMode === 'table'" :data="farms" v-loading="loading" border>
        <el-table-column prop="farm_code" label="场站编码" min-width="140" />
        <el-table-column prop="farm_name" label="场站名称" min-width="180" />
        <el-table-column label="装机容量(MW)" min-width="120">
          <template #default="{ row }">{{ toMw(row.capacity) }}</template>
        </el-table-column>
        <el-table-column label="经度" min-width="100">
          <template #default="{ row }">{{ formatCoord(row.longitude) }}</template>
        </el-table-column>
        <el-table-column label="纬度" min-width="100">
          <template #default="{ row }">{{ formatCoord(row.latitude) }}</template>
        </el-table-column>
        <el-table-column label="预测模型" min-width="170">
          <template #default="{ row }">
            {{ row.supershort_model || '-' }} / {{ row.short_model || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="180">
          <template #default="{ row }">
            <div class="table-status">
              <el-tag :type="row.is_active ? 'success' : 'info'" class="status-tag">
                <StatusDot :active="row.is_active" />
                <span>{{ row.is_active ? '运行中' : '离线' }}</span>
              </el-tag>
              <el-switch :model-value="!!row.is_active" @change="(val) => handleSetActive(row, val)" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEditDrawer(row)">编辑参数</el-button>
            <el-button size="small" type="warning" @click="handleTogglePredict(row)">
              {{ row.is_active ? '停用预测' : '启用预测' }}
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="map-view-wrap">
        <div ref="mapChartRef" class="map-chart"></div>
        <div v-if="coordFarms.length === 0" class="map-empty">
          没有可展示的经纬度数据，请在“编辑参数 -> 基础与地理信息”中补全经纬度。
        </div>
      </div>
    </el-card>

    <el-drawer
      v-model="drawerVisible"
      :title="isEdit ? '编辑场站' : '新建场站'"
      size="760px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="130px" class="farm-form">
        <el-tabs v-model="activeTab" class="form-tabs">
          <el-tab-pane label="基础与地理信息" name="basic">
            <el-row :gutter="14">
              <el-col :span="12">
                <el-form-item label="场站名称" prop="farm_name">
                  <el-input v-model="formData.farm_name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="场站编码" prop="farm_code">
                  <el-input v-model="formData.farm_code" :disabled="isEdit" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="14">
              <el-col :span="12">
                <el-form-item label="并网日期">
                  <el-date-picker
                    v-model="formData.commissioning_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="请选择并网日期"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="装机容量(MW)" prop="capacity">
                  <el-input-number v-model="formData.capacity" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="14">
              <el-col :span="8">
                <el-form-item label="经度">
                  <el-input-number v-model="formData.longitude" :precision="6" :step="0.000001" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="纬度">
                  <el-input-number v-model="formData.latitude" :precision="6" :step="0.000001" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="海拔高度(m)">
                  <el-input-number v-model="formData.altitude" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="14">
              <el-col :span="12">
                <el-form-item label="所属省份">
                  <el-input v-model="formData.province" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="所属区域">
                  <el-input v-model="formData.region" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="硬件与机组配置" name="hardware">
            <el-row :gutter="14">
              <el-col :span="12">
                <el-form-item label="风机总台数">
                  <el-input-number v-model="formData.turbine_count" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="轮毂高度(m)">
                  <el-input-number v-model="formData.hub_height" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="14">
              <el-col :span="12">
                <el-form-item label="测风塔数量">
                  <el-input-number v-model="formData.met_tower_count" :min="0" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="功率曲线文件名">
                  <el-input v-model="formData.power_curve_file_name" placeholder="如 power_curve_v1.csv" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="功率曲线地址/说明">
              <el-input
                v-model="formData.power_curve_url"
                type="textarea"
                :rows="3"
                placeholder="可填文件路径、对象存储地址或配置说明"
              />
            </el-form-item>
          </el-tab-pane>

          <el-tab-pane label="预测模型参数" name="model">
            <el-row :gutter="14">
              <el-col :span="12">
                <el-form-item label="超短期预测算法">
                  <el-select v-model="formData.supershort_model" placeholder="请选择" style="width: 100%">
                    <el-option label="BP神经网络" value="BP神经网络" />
                    <el-option label="LightGBM" value="LightGBM" />
                    <el-option label="历史相似日" value="历史相似日" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="短期预测算法">
                  <el-select v-model="formData.short_model" placeholder="请选择" style="width: 100%">
                    <el-option label="BP神经网络" value="BP神经网络" />
                    <el-option label="LightGBM" value="LightGBM" />
                    <el-option label="历史相似日" value="历史相似日" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="14">
              <el-col :span="12">
                <el-form-item label="出力下限(MW)">
                  <el-input-number v-model="formData.lower_power_limit" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="限电判定阈值">
                  <el-input-number v-model="formData.curtailment_threshold" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="数据测点映射" name="mapping">
            <el-form-item label="实测总有功功率测点">
              <el-input v-model="formData.point_act_power" placeholder="Point_Act_Power_001" />
            </el-form-item>
            <el-form-item label="实测风速测点">
              <el-input v-model="formData.point_wind_speed" placeholder="Point_Wind_Speed_001" />
            </el-form-item>
            <el-form-item label="机组可用台数测点">
              <el-input v-model="formData.point_avail_count" placeholder="Point_Avail_Count" />
            </el-form-item>
            <el-form-item label="数据源健康状态">
              <el-row :gutter="14" style="width: 100%">
                <el-col :span="12">
                  <el-select v-model="formData.scada_status" style="width: 100%">
                    <el-option label="正常" value="normal" />
                    <el-option label="异常" value="abnormal" />
                    <el-option label="未知" value="unknown" />
                  </el-select>
                </el-col>
                <el-col :span="12">
                  <el-select v-model="formData.nwp_status" style="width: 100%">
                    <el-option label="正常" value="normal" />
                    <el-option label="异常" value="abnormal" />
                    <el-option label="未知" value="unknown" />
                  </el-select>
                </el-col>
              </el-row>
            </el-form-item>
            <el-form-item label="当前实测功率(MW)">
              <el-input-number v-model="formData.current_actual_power" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item label="场站启用">
              <el-switch v-model="formData.is_active" />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </el-form>

      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { WindPower } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { createFarm, deleteFarm, getFarms, updateFarm } from '@/api/farmApi'
import StatusDot from './common/StatusDot.vue'

const LOCAL_EXT_KEY = 'farm_management_ext_configs_v2_backendized'

const loading = ref(false)
const submitting = ref(false)
const farms = ref([])
const drawerVisible = ref(false)
const isEdit = ref(false)
const viewMode = ref('card')
const activeTab = ref('basic')
const formRef = ref(null)

const mapChartRef = ref(null)
let mapChart = null
let mapDisposed = false

const formData = reactive({
  farm_code: '',
  farm_name: '',
  capacity: 0,
  location: '',
  is_active: true,
  commissioning_date: '',
  province: '',
  region: '',
  longitude: null,
  latitude: null,
  altitude: null,
  turbine_count: 0,
  hub_height: null,
  met_tower_count: 0,
  power_curve_file_name: '',
  power_curve_url: '',
  supershort_model: '',
  short_model: '',
  lower_power_limit: 0,
  curtailment_threshold: null,
  point_act_power: '',
  point_wind_speed: '',
  point_avail_count: '',
  scada_status: 'normal',
  nwp_status: 'normal',
  current_actual_power: 0
})

const rules = {
  farm_code: [{ required: true, message: '请输入场站编码', trigger: 'blur' }],
  farm_name: [{ required: true, message: '请输入场站名称', trigger: 'blur' }],
  capacity: [{ required: true, message: '请输入装机容量', trigger: 'change' }]
}

const coordFarms = computed(() =>
  farms.value.filter((item) => isFiniteNumber(item.longitude) && isFiniteNumber(item.latitude))
)

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function parseCoord(value) {
  if (value === null || value === undefined || value === '') return null
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function toMw(value) {
  const num = Number(value || 0)
  if (!Number.isFinite(num)) return '0.00'
  return num.toFixed(2)
}

function formatCoord(value) {
  if (!isFiniteNumber(value)) return '-'
  return value.toFixed(6)
}

function normalizeSourceLabel(value) {
  const text = String(value || '').toLowerCase()
  if (text === 'normal') return '正常'
  if (text === 'abnormal') return '异常'
  return '未知'
}

function buildLocationText() {
  const parts = [formData.province, formData.region].filter(Boolean)
  return parts.join('-')
}

function normalizeFarm(raw = {}) {
  const source = { ...raw, ...getExtConfig(raw.farm_code) }
  const locationText = source.location || ''
  const locationParts = String(locationText).split('-')

  return {
    ...source,
    capacity: Number(source.capacity || 0),
    is_active: !!source.is_active,
    province: source.province || locationParts[0] || '',
    region: source.region || locationParts[1] || '',
    longitude: parseCoord(source.longitude),
    latitude: parseCoord(source.latitude),
    turbine_count: Number(source.turbine_count || 0),
    current_actual_power: Number(source.current_actual_power || 0),
    scada_status: source.scada_status || 'normal',
    nwp_status: source.nwp_status || 'normal'
  }
}

function readExtConfigMap() {
  try {
    void LOCAL_EXT_KEY
    return {}
  } catch (error) {
    console.warn('读取场站扩展配置失败:', error)
    return {}
  }
}

function writeExtConfigMap(data) {
  return data
}

function getExtConfig(farmCode) {
  if (!farmCode) return {}
  const configMap = readExtConfigMap()
  return configMap[farmCode] || {}
}

function saveExtConfig(farmCode, config) {
  if (!farmCode) return
  writeExtConfigMap(config)
}

function removeExtConfig(farmCode) {
  return farmCode
}

function resetForm() {
  Object.assign(formData, {
    farm_code: '',
    farm_name: '',
    capacity: 0,
    location: '',
    is_active: true,
    commissioning_date: '',
    province: '',
    region: '',
    longitude: null,
    latitude: null,
    altitude: null,
    turbine_count: 0,
    hub_height: null,
    met_tower_count: 0,
    power_curve_file_name: '',
    power_curve_url: '',
    supershort_model: '',
    short_model: '',
    lower_power_limit: 0,
    curtailment_threshold: null,
    point_act_power: '',
    point_wind_speed: '',
    point_avail_count: '',
    scada_status: 'normal',
    nwp_status: 'normal',
    current_actual_power: 0
  })
}

async function fetchFarms() {
  loading.value = true
  try {
    const rows = await getFarms()
    farms.value = (rows || []).map((item) => normalizeFarm(item))
    nextTick(() => {
      if (viewMode.value === 'map') {
        renderMapChart()
      }
    })
  } finally {
    loading.value = false
  }
}

function openCreateDrawer() {
  isEdit.value = false
  activeTab.value = 'basic'
  resetForm()
  drawerVisible.value = true
}

function openEditDrawer(row) {
  isEdit.value = true
  activeTab.value = 'basic'
  Object.assign(formData, {
    farm_code: row.farm_code || '',
    farm_name: row.farm_name || '',
    capacity: Number(row.capacity || 0),
    location: row.location || '',
    is_active: !!row.is_active,
    commissioning_date: row.commissioning_date || '',
    province: row.province || '',
    region: row.region || '',
    longitude: parseCoord(row.longitude),
    latitude: parseCoord(row.latitude),
    altitude: parseCoord(row.altitude),
    turbine_count: Number(row.turbine_count || 0),
    hub_height: parseCoord(row.hub_height),
    met_tower_count: Number(row.met_tower_count || 0),
    power_curve_file_name: row.power_curve_file_name || '',
    power_curve_url: row.power_curve_url || '',
    supershort_model: row.supershort_model || '',
    short_model: row.short_model || '',
    lower_power_limit: Number(row.lower_power_limit || 0),
    curtailment_threshold: parseCoord(row.curtailment_threshold),
    point_act_power: row.point_act_power || '',
    point_wind_speed: row.point_wind_speed || '',
    point_avail_count: row.point_avail_count || '',
    scada_status: row.scada_status || 'normal',
    nwp_status: row.nwp_status || 'normal',
    current_actual_power: Number(row.current_actual_power || 0)
  })
  drawerVisible.value = true
}

function buildExtPayload() {
  return {
    commissioning_date: formData.commissioning_date || '',
    province: formData.province || '',
    region: formData.region || '',
    longitude: parseCoord(formData.longitude),
    latitude: parseCoord(formData.latitude),
    altitude: parseCoord(formData.altitude),
    turbine_count: Number(formData.turbine_count || 0),
    hub_height: parseCoord(formData.hub_height),
    met_tower_count: Number(formData.met_tower_count || 0),
    power_curve_file_name: formData.power_curve_file_name || '',
    power_curve_url: formData.power_curve_url || '',
    supershort_model: formData.supershort_model || '',
    short_model: formData.short_model || '',
    lower_power_limit: Number(formData.lower_power_limit || 0),
    curtailment_threshold: parseCoord(formData.curtailment_threshold),
    point_act_power: formData.point_act_power || '',
    point_wind_speed: formData.point_wind_speed || '',
    point_avail_count: formData.point_avail_count || '',
    scada_status: formData.scada_status || 'normal',
    nwp_status: formData.nwp_status || 'normal',
    current_actual_power: Number(formData.current_actual_power || 0)
  }
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const locationText = formData.location || buildLocationText()
    const extPayload = buildExtPayload()
    const payload = {
      farm_name: formData.farm_name,
      capacity: Number(formData.capacity || 0),
      location: locationText,
      is_active: !!formData.is_active,
      ...extPayload
    }

    if (isEdit.value) {
      await updateFarm(formData.farm_code, payload)
      ElMessage.success('场站更新成功')
    } else {
      await createFarm({ farm_code: formData.farm_code, ...payload })
      ElMessage.success('场站创建成功')
    }

    saveExtConfig(formData.farm_code, extPayload)
    drawerVisible.value = false
    await fetchFarms()
  } finally {
    submitting.value = false
  }
}

async function handleSetActive(row, nextActive) {
  try {
    await updateFarm(row.farm_code, { is_active: !!nextActive })
    ElMessage.success(nextActive ? '场站已启用，定时预测将纳入执行' : '场站已停用，定时预测将自动跳过')
    await fetchFarms()
  } catch (error) {
    ElMessage.error('更新场站状态失败')
    console.error(error)
  }
}

async function handleTogglePredict(row) {
  await handleSetActive(row, !row.is_active)
}

async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确认删除场站 ${row.farm_name} (${row.farm_code}) 吗？`,
    '提示',
    { type: 'warning' }
  )
  await deleteFarm(row.farm_code)
  removeExtConfig(row.farm_code)
  ElMessage.success('场站已删除')
  await fetchFarms()
}

function initMapChart() {
  if (!mapChartRef.value || mapChart) return
  mapChart = echarts.init(mapChartRef.value)
}

function renderMapChart() {
  if (mapDisposed || !mapChartRef.value) return
  initMapChart()
  if (!mapChart) return

  const points = coordFarms.value.map((item) => ({
    name: item.farm_name || item.farm_code,
    value: [item.longitude, item.latitude, Number(item.capacity || 0)],
    farmCode: item.farm_code,
    status: item.is_active ? '运行中' : '离线'
  }))

  mapChart.setOption({
    backgroundColor: '#0b1d2d',
    grid: {
      left: 58,
      right: 24,
      top: 45,
      bottom: 52
    },
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const d = params.data || {}
        const v = d.value || []
        return [
          `${d.name} (${d.farmCode || '-'})`,
          `经纬度: ${Number(v[0] || 0).toFixed(4)}, ${Number(v[1] || 0).toFixed(4)}`,
          `装机容量: ${Number(v[2] || 0).toFixed(2)} MW`,
          `状态: ${d.status || '-'}`
        ].join('<br/>')
      }
    },
    xAxis: {
      type: 'value',
      name: '经度',
      min: (value) => value.min - 0.2,
      max: (value) => value.max + 0.2,
      splitLine: { lineStyle: { color: '#eef2f7' } }
    },
    yAxis: {
      type: 'value',
      name: '纬度',
      min: (value) => value.min - 0.2,
      max: (value) => value.max + 0.2,
      splitLine: { lineStyle: { color: '#eef2f7' } }
    },
    series: [
      {
        type: 'scatter',
        data: points,
        symbolSize: (val) => 10 + Math.min(24, Math.sqrt(Number(val[2] || 0))),
        itemStyle: {
          color: (params) => (params.data?.status === '运行中' ? '#19b955' : '#d3415b')
        },
        label: {
          show: true,
          position: 'top',
          formatter: (params) => params.data?.farmCode || '',
          color: '#2f4058',
          fontSize: 11
        }
      }
    ]
  })
}

function handleWindowResize() {
  if (!mapDisposed && mapChart) {
    mapChart.resize()
  }
}

watch(viewMode, (mode) => {
  if (mode === 'map') {
    nextTick(() => renderMapChart())
  }
})

watch(
  () => farms.value,
  () => {
    if (viewMode.value === 'map') {
      nextTick(() => renderMapChart())
    }
  },
  { deep: true }
)

onMounted(async () => {
  await fetchFarms()
  window.addEventListener('resize', handleWindowResize)
})

onBeforeUnmount(() => {
  mapDisposed = true
  window.removeEventListener('resize', handleWindowResize)
  if (mapChart) {
    mapChart.dispose()
    mapChart = null
  }
})
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.title {
  font-size: 18px;
  color: var(--text-primary);
  font-weight: 600;
}

.sub {
  font-size: 12px;
  color: var(--text-secondary);
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.farm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 14px;
}

.farm-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.farm-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.farm-code {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}

.status-pill.active {
  color: #7ef3b7;
  background: rgba(45, 211, 111, 0.15);
  border: 1px solid rgba(45, 211, 111, 0.3);
}

.status-pill.inactive {
  color: #ff8f9f;
  background: rgba(255, 93, 115, 0.15);
  border: 1px solid rgba(255, 93, 115, 0.3);
}

.core-meta {
  margin-top: 12px;
  display: grid;
  gap: 6px;
}

.meta-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.meta-label {
  color: var(--text-secondary);
}

.meta-value {
  color: var(--text-primary);
  font-weight: 500;
}

.biz-status {
  margin-top: 12px;
  background: rgba(10, 25, 38, 0.5);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 10px 12px;
}

.biz-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-secondary);
}

.biz-row + .biz-row {
  margin-top: 8px;
}

.source-status {
  font-weight: 500;
}

.card-footer {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.footer-actions {
  display: flex;
  gap: 6px;
}

.table-status {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.map-view-wrap {
  position: relative;
}

.map-chart {
  width: 100%;
  height: 560px;
  border: 1px solid var(--border-color);
  background: rgba(8, 24, 38, 0.5);
  border-radius: 12px;
}

.map-empty {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  color: #6f7f93;
  font-size: 14px;
  background: rgba(7, 24, 39, 0.58);
  padding: 10px 14px;
  border-radius: 8px;
}

.farm-form {
  padding-right: 8px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
}

.empty-state {
  text-align: center;
  padding: 36px 10px;
  color: var(--text-secondary);
}

.empty-state .el-icon {
  font-size: 42px;
  margin-bottom: 8px;
}

@media (max-width: 1100px) {
  .farm-grid {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
}

@media (max-width: 768px) {
  .header-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .actions {
    width: 100%;
    justify-content: space-between;
  }

  .farm-grid {
    grid-template-columns: 1fr;
  }

  .card-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .footer-actions {
    flex-wrap: wrap;
  }
}
</style>
