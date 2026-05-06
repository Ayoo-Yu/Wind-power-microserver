# 首页大屏 UI 重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构首页大屏布局为经典仪表盘风格：顶部 4 个 KPI 卡片横排，下方趋势图(2/3) + 气象/矩阵(1/3)，增强趋势图交互，优化视觉对齐和层次。

**Architecture:** 纯前端重构，不新增后端接口。KPI 的新增指标（总功率、发电量、开机率）从现有的 `getDashboardOverview` 已获取的 `compareList` 数据中计算得出，无需额外 API 调用。趋势图时间范围切换也基于现有 `getDashboardTrend` 的 `start/end` 参数。

**Tech Stack:** Vue 3 Composition API, CSS Grid/Flexbox, ECharts 5, Element Plus

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/components/HomePage.vue` | MODIFY | 重构布局：header + KPI行 + 主体三行 |
| `frontend/src/components/dashboard/KpiCards.vue` | REWRITE | 4 卡片横排，主题色卡片样式 |
| `frontend/src/components/dashboard/PowerTrendChart.vue` | MODIFY | 增加时间范围按钮组，增强 tooltip |
| `frontend/src/components/dashboard/FleetMap.vue` | MODIFY | 表头样式优化，图例水平排列 |
| `frontend/src/services/dashboardService.js` | MODIFY | 扩展 cards 返回更多 KPI 数据 |

---

### Task 1: 扩展 dashboardService 返回更多 KPI 数据

**Files:**
- Modify: `frontend/src/services/dashboardService.js:286-338` (getDashboardOverview 函数)

**Goal:** 在 `getDashboardOverview` 的返回值中增加总功率、装机容量、日发电量和开机率数据，全部从已有的 `compareList` 和 `farms` 数据计算，不需要新增 API 调用。

- [ ] **Step 1: 修改 getDashboardOverview 返回更多 cards**

在 `getDashboardOverview` 函数中，`compareList` 已经有了每个农场的 `latestActual` 和 `online` 状态。`farms` 已经有 `capacity`。需要在 `return` 语句之前计算汇总指标，并扩展 `cards` 数组。

找到 `getDashboardOverview` 函数中 `return { cards: [...]` 的位置（约第 325 行），将整个 return 块替换为：

```javascript
  const totalCurrentPower = compareList.reduce((sum, item) => sum + safeNumber(item.latestActual, 0), 0)
  const totalCapacity = selectedFarms.reduce((sum, farm) => sum + safeNumber(farm.capacity, 0), 0)
  const loadRate = totalCapacity > 0 ? (totalCurrentPower / totalCapacity) * 100 : 0

  const onlineFarms = compareList.filter(item => item.online).length
  const totalFarms = compareList.length

  const estimatedDailyEnergy = totalCurrentPower * (new Date().getHours() + new Date().getMinutes() / 60)

  return {
    cards: [
      {
        key: 'accuracy',
        type: 'accuracy-split',
        label: '综合预测准确率',
        theme: 'cyan',
        value: {
          shortTerm: Number(shortAcc.toFixed(1)),
          ultraShort: Number(ultraAcc.toFixed(1))
        }
      },
      {
        key: 'total-power',
        type: 'value-unit',
        label: '当前总功率',
        theme: 'green',
        value: Number(totalCurrentPower.toFixed(1)),
        unit: 'MW',
        sub: [
          { label: '装机容量', value: `${Number(totalCapacity.toFixed(0))} MW` },
          { label: '负荷率', value: `${Number(loadRate.toFixed(1))}%`, highlight: true }
        ]
      },
      {
        key: 'daily-energy',
        type: 'value-unit',
        label: '今日发电量(估)',
        theme: 'yellow',
        value: Number(estimatedDailyEnergy.toFixed(0)),
        unit: 'MWh',
        sub: []
      },
      {
        key: 'farm-online',
        type: 'value-unit',
        label: '场站在线率',
        theme: 'purple',
        value: totalFarms > 0 ? Number(((onlineFarms / totalFarms) * 100).toFixed(1)) : 0,
        unit: '%',
        sub: [
          { label: '在线', value: `${onlineFarms} / ${totalFarms}` }
        ]
      }
    ],
    topology: buildTaskMatrix(selectedFarms, logs, commMap)
  }
```

- [ ] **Step 2: 验证前端可以正常获取数据**

启动前端 dev server，打开浏览器控制台 Network 面板，确认 `getDashboardOverview` 返回的 `cards` 数组包含 4 个元素。每个 card 有 `key`, `type`, `label`, `theme`, `value` 等字段。

Run: `cd wind-power-forecast/frontend && npm run serve`

Expected: 页面正常加载，控制台无报错（KpiCards 暂时会渲染不正确，这是预期的，后续 Task 2 会修复）。

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend/src/services/dashboardService.js
git commit -m "feat: extend dashboard overview with total power, daily energy, and farm online KPIs"
```

---

### Task 2: 重写 KpiCards.vue 支持 4 卡片横排

**Files:**
- Rewrite: `frontend/src/components/dashboard/KpiCards.vue`

**Goal:** 将 KpiCards 组件从单列纵向堆叠改为 4 卡片等宽等高横排，每张卡片有独立主题色。

- [ ] **Step 1: 完整重写 KpiCards.vue**

将 `frontend/src/components/dashboard/KpiCards.vue` 整个文件替换为以下内容：

```vue
<template>
  <div class="kpi-row">
    <div
      v-for="item in items"
      :key="item.key"
      class="kpi-card"
      :class="`kpi-${item.theme || 'cyan'}`"
    >
      <div class="kpi-deco"></div>
      <div class="kpi-label">{{ item.label }}</div>

      <div v-if="item.type === 'accuracy-split'" class="kpi-main">
        <span class="kpi-number">{{ ((item.value?.shortTerm || 0) + (item.value?.ultraShort || 0)) / 2 > 0
          ? ((item.value?.shortTerm || 0) + (item.value?.ultraShort || 0)) / 2
          : '--' }}</span>
        <span class="kpi-unit">%</span>
      </div>
      <div v-else class="kpi-main">
        <span class="kpi-number">{{ formatValue(item.value) }}</span>
        <span v-if="item.unit" class="kpi-unit">{{ item.unit }}</span>
      </div>

      <div v-if="item.type === 'accuracy-split'" class="kpi-sub-row">
        <span class="sub-label" style="color:#60a5fa">短期</span>
        <span class="sub-value" style="color:#60a5fa">{{ item.value?.shortTerm ?? '--' }}%</span>
        <span class="sub-sep"></span>
        <span class="sub-label" style="color:#fbbf24">超短期</span>
        <span class="sub-value" style="color:#fbbf24">{{ item.value?.ultraShort ?? '--' }}%</span>
      </div>
      <div v-else-if="item.sub?.length" class="kpi-sub-row">
        <template v-for="(s, i) in item.sub" :key="i">
          <span class="sub-label">{{ s.label }}</span>
          <span class="sub-value" :class="{ 'sub-highlight': s.highlight }">{{ s.value }}</span>
          <span v-if="i < item.sub.length - 1" class="sub-sep"></span>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

function formatValue(val) {
  if (val == null) return '--'
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  return n % 1 === 0 ? String(n) : n.toFixed(1)
}
</script>

<style scoped>
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-card {
  position: relative;
  padding: 14px 16px;
  border-radius: 10px;
  overflow: hidden;
  min-height: 90px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.kpi-deco {
  position: absolute;
  top: 0;
  right: 0;
  width: 64px;
  height: 64px;
  pointer-events: none;
}

.kpi-label {
  font-size: 11px;
  color: #8fb2ca;
  margin-bottom: 4px;
}

.kpi-main {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.kpi-number {
  font-size: 26px;
  font-weight: 700;
  font-family: Consolas, Menlo, Monaco, monospace;
  line-height: 1.2;
}

.kpi-unit {
  font-size: 12px;
  margin-left: 1px;
}

.kpi-sub-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-wrap: wrap;
}

.sub-label {
  font-size: 10px;
  color: #7a96aa;
}

.sub-value {
  font-size: 12px;
  font-weight: 600;
  color: #9fc4df;
}

.sub-highlight {
  color: #2dd36f;
}

.sub-sep {
  width: 1px;
  height: 12px;
  background: rgba(136, 186, 217, 0.15);
}

/* Theme variants */
.kpi-cyan {
  background: linear-gradient(135deg, rgba(18, 215, 255, 0.08), rgba(18, 215, 255, 0.02));
  border: 1px solid rgba(18, 215, 255, 0.18);
}
.kpi-cyan .kpi-number, .kpi-cyan .kpi-unit { color: #12d7ff; }
.kpi-cyan .kpi-deco { background: radial-gradient(circle at top right, rgba(18, 215, 255, 0.12), transparent); }

.kpi-green {
  background: linear-gradient(135deg, rgba(45, 211, 111, 0.08), rgba(45, 211, 111, 0.02));
  border: 1px solid rgba(45, 211, 111, 0.18);
}
.kpi-green .kpi-number, .kpi-green .kpi-unit { color: #2dd36f; }
.kpi-green .kpi-deco { background: radial-gradient(circle at top right, rgba(45, 211, 111, 0.12), transparent); }

.kpi-yellow {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.08), rgba(251, 191, 36, 0.02));
  border: 1px solid rgba(251, 191, 36, 0.18);
}
.kpi-yellow .kpi-number, .kpi-yellow .kpi-unit { color: #fbbf24; }
.kpi-yellow .kpi-deco { background: radial-gradient(circle at top right, rgba(251, 191, 36, 0.12), transparent); }

.kpi-purple {
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.08), rgba(167, 139, 250, 0.02));
  border: 1px solid rgba(167, 139, 250, 0.18);
}
.kpi-purple .kpi-number, .kpi-purple .kpi-unit { color: #a78bfa; }
.kpi-purple .kpi-deco { background: radial-gradient(circle at top right, rgba(167, 139, 250, 0.12), transparent); }

@media (max-width: 720px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
```

- [ ] **Step 2: 验证 KPI 卡片渲染**

刷新页面，确认：
- 4 张卡片等宽等高横排
- 每张卡片有对应主题色（青/绿/黄/紫）
- 准确率卡片底部显示短期/超短期拆分
- 总功率卡片底部显示装机容量和负荷率
- 场站在线率卡片底部显示在线数/总数

Run: 刷新浏览器

Expected: 4 张卡片整齐横排，颜色和内容正确。

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend/src/components/dashboard/KpiCards.vue
git commit -m "feat: rewrite KpiCards as 4-column horizontal row with theme colors"
```

---

### Task 3: 重构 HomePage.vue 布局为三行结构

**Files:**
- Modify: `frontend/src/components/HomePage.vue`

**Goal:** 将 HomePage 从当前的两栏布局（左: KPI+矩阵, 右: 趋势+气象）改为三行布局（header / KPI行 / 主体: 左趋势+右气象矩阵）。

- [ ] **Step 1: 重写 HomePage.vue 模板和样式**

将 `frontend/src/components/HomePage.vue` 的 `<template>` 和 `<style scoped>` 部分替换。`<script setup>` 部分保持不变。

**模板部分**（替换整个 `<template>` 块）：

```html
<template>
  <div class="page-shell home-dashboard">
    <div class="dashboard-head panel-card">
      <div class="title-wrap">
        <h1>风电预测业务总览</h1>
        <div class="title-meta">
          <span class="title-dot"></span>
          <span class="title-time">更新时间: {{ updatedAt }}</span>
        </div>
      </div>
      <el-button class="refresh-btn" :loading="loading" @click="loadData">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <div class="kpi-section">
      <KpiCards :items="cards" />
    </div>

    <div class="dashboard-body">
      <div class="panel-card panel-trend">
        <div class="panel-title trend-legend">
          日功率预测
          <span class="legend-line" style="background:#2dd4bf"></span>实绩
          <span class="legend-line ll-dash" style="background:#60a5fa"></span>短期
          <span class="legend-line ll-dot" style="background:#fbbf24"></span>超短期
          <span class="legend-line" style="background:#a78bfa"></span>容量
        </div>
        <PowerTrendChart v-if="trendPoints.length" :points="trendPoints" />
        <div v-else-if="!loading" class="empty-state">暂无功率预测数据</div>
      </div>

      <div class="col-right">
        <div class="panel-card panel-weather">
          <div class="panel-title">
            气象概览
            <span v-if="weatherUpdateTime" class="weather-update-hint">NWP更新: {{ weatherUpdateTime.slice(11, 16) }}</span>
          </div>

          <div v-if="weatherMetrics.length" class="weather-metrics-grid">
            <div v-for="item in weatherMetrics" :key="item.label" class="weather-metric-item">
              <div class="metric-icon" :class="`metric-${item.icon}`">
                <i v-if="item.icon === 'wind'" class="wind-icon-sm"></i>
                <i v-else-if="item.icon === 'compass'" class="compass-icon-sm"></i>
                <i v-else-if="item.icon === 'temp'" class="temp-icon-sm"></i>
                <i v-else class="drop-icon-sm"></i>
              </div>
              <div class="metric-info">
                <div class="metric-label">{{ item.label }}</div>
                <div class="metric-value">{{ item.value }} <small>{{ item.unit }}</small></div>
              </div>
            </div>
          </div>
          <div v-else-if="!loading" class="empty-state">暂无气象数据</div>
        </div>

        <div class="panel-card panel-matrix">
          <div class="panel-title">多场站预测任务监控矩阵</div>
          <FleetMap v-if="topologyPoints.length" :points="topologyPoints" />
          <div v-else-if="!loading" class="empty-state">暂无监控数据</div>
        </div>
      </div>
    </div>
  </div>
</template>
```

**样式部分**（替换整个 `<style scoped>` 块）：

```css
<style scoped>
.home-dashboard {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  overflow: hidden;
}

/* ---- header ---- */
.dashboard-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  flex-shrink: 0;
}

.dashboard-head h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.title-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2dd36f;
  box-shadow: 0 0 8px rgba(45, 211, 111, 0.6);
}

.title-time {
  font-size: 12px;
  color: var(--text-muted);
}

.refresh-btn {
  border: 1px solid rgba(146, 186, 220, 0.3) !important;
  background: transparent !important;
  color: var(--text-secondary) !important;
  border-radius: 8px !important;
  padding: 8px !important;
  transition: all 0.2s ease;
}

.refresh-btn:hover {
  border-color: rgba(18, 215, 255, 0.5) !important;
  color: var(--accent) !important;
  background: rgba(18, 215, 255, 0.06) !important;
}

/* ---- KPI section ---- */
.kpi-section {
  flex-shrink: 0;
  padding: 0 0 2px 0;
}

/* ---- main body: trend (left) + right sidebar ---- */
.dashboard-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
}

.col-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.panel-trend {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.panel-weather {
  flex: 2;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-matrix {
  flex: 3;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ---- panel-card base ---- */
.panel-card {
  position: relative;
  padding: 14px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
}

.panel-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(18, 215, 255, 0.15), transparent);
  pointer-events: none;
}

.panel-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
  flex-shrink: 0;
}

/* ---- trend legend ---- */
.legend-line {
  display: inline-block;
  width: 16px;
  height: 2px;
  vertical-align: middle;
  margin: 0 3px 0 6px;
  border-radius: 1px;
}

.ll-dash {
  background: repeating-linear-gradient(90deg, currentColor 0 4px, transparent 4px 7px) !important;
}

.ll-dot {
  background: repeating-linear-gradient(90deg, currentColor 0 2px, transparent 2px 4px) !important;
}

/* ---- weather ---- */
.weather-update-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #7ca8c4;
}

.weather-metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  flex: 1;
  align-content: start;
}

.weather-metric-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid rgba(136, 186, 217, 0.12);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.025);
  overflow: hidden;
}

.weather-metric-item:last-child:nth-child(odd) {
  grid-column: 1 / -1;
  max-width: 50%;
  justify-self: center;
}

.metric-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.metric-wind { background: rgba(18, 215, 255, 0.12); }
.metric-compass { background: rgba(45, 211, 111, 0.12); }
.metric-temp { background: rgba(255, 125, 69, 0.12); }
.metric-drop { background: rgba(100, 160, 255, 0.12); }

.wind-icon-sm {
  width: 14px;
  height: 14px;
  display: inline-block;
  position: relative;
}
.wind-icon-sm::before,
.wind-icon-sm::after {
  content: '';
  position: absolute;
  background: #5de0ff;
  border-radius: 1px;
}
.wind-icon-sm::before { width: 2px; height: 14px; left: 6px; top: 0; }
.wind-icon-sm::after { width: 10px; height: 2px; left: 2px; top: 4px; }

.compass-icon-sm {
  width: 12px;
  height: 12px;
  border: 2px solid #2dd36f;
  border-radius: 50%;
  display: inline-block;
  position: relative;
}
.compass-icon-sm::after {
  content: '';
  position: absolute;
  top: 1px;
  left: 3px;
  width: 0;
  height: 0;
  border-left: 3px solid transparent;
  border-right: 3px solid transparent;
  border-bottom: 5px solid #2dd36f;
}

.temp-icon-sm, .drop-icon-sm {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}
.temp-icon-sm { background: #ff7d45; }
.drop-icon-sm {
  display: inline-block !important;
  width: 12px !important;
  height: 12px !important;
  background: radial-gradient(circle at 40% 35%, #8ec5ff, #5a9ef5);
  border-radius: 50%;
}

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.metric-label { font-size: 11px; color: #9fc4df; white-space: nowrap; }
.metric-value {
  font-size: 16px;
  font-family: Consolas, Menlo, Monaco, monospace;
  color: #dff3ff;
  white-space: nowrap;
}
.metric-value small { font-size: 11px; color: #8fb2ca; margin-left: 2px; }

/* ---- empty & animation ---- */
.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 20px 16px;
  font-size: 13px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* ---- responsive ---- */
@media (max-width: 1280px) {
  .dashboard-body {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }
  .panel-trend {
    flex: none;
    height: 320px;
  }
  .home-dashboard {
    height: auto;
    overflow: auto;
  }
}

@media (max-width: 720px) {
  .weather-metrics-grid {
    grid-template-columns: 1fr;
  }
  .weather-metric-item:last-child:nth-child(odd) {
    max-width: 100%;
  }
}
</style>
```

- [ ] **Step 2: 验证新布局**

刷新页面，确认：
- Header 在顶部
- 4 个 KPI 卡片在第二行横排
- 趋势图占左侧约 2/3
- 右侧气象（上）和任务矩阵（下）纵向堆叠
- 所有面板对齐，无溢出

Expected: 三行布局正确渲染，趋势图面积明显大于旧版。

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend/src/components/HomePage.vue
git commit -m "refactor: restructure dashboard to header + KPI row + 2-column body layout"
```

---

### Task 4: 增强 PowerTrendChart 交互

**Files:**
- Modify: `frontend/src/components/dashboard/PowerTrendChart.vue`

**Goal:** 在趋势图标题栏增加时间范围按钮组（1D/3D/7D），通过 emit 通知父组件切换时间范围。

- [ ] **Step 1: 重写 PowerTrendChart.vue**

将 `frontend/src/components/dashboard/PowerTrendChart.vue` 整个文件替换为以下内容：

```vue
<template>
  <div class="chart-host">
    <div v-if="showRangeButtons" class="range-bar">
      <button
        v-for="opt in rangeOptions"
        :key="opt.value"
        class="range-btn"
        :class="{ active: currentRange === opt.value }"
        @click="selectRange(opt.value)"
      >{{ opt.label }}</button>
    </div>
    <div ref="chartRef" class="chart-canvas" />
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  },
  showRangeButtons: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['range-change'])

const rangeOptions = [
  { label: '1D', value: '1d' },
  { label: '3D', value: '3d' },
  { label: '7D', value: '7d' }
]

const currentRange = ref('1d')
const chartRef = ref(null)
let chart = null
let disposed = false

function selectRange(range) {
  currentRange.value = range
  emit('range-change', range)
}

function resolveNowIndex(labels) {
  const now = new Date()
  const nowMinutes = now.getHours() * 60 + now.getMinutes()
  let best = 0
  let bestDelta = Number.POSITIVE_INFINITY

  labels.forEach((label, idx) => {
    const m = String(label).match(/^(\d{2}):(\d{2})$/)
    if (!m) return
    const minutes = Number(m[1]) * 60 + Number(m[2])
    const delta = Math.abs(minutes - nowMinutes)
    if (delta < bestDelta) {
      bestDelta = delta
      best = idx
    }
  })
  return best
}

function render() {
  if (!chart || disposed) return
  if (!props.points?.length) return

  const labels = props.points.map(item => item.label || item.time)
  const actual = props.points.map(item => item.actual)
  const shortTerm = props.points.map(item => item.shortTerm)
  const ultraShort = props.points.map(item => item.ultraShort)
  const availableCap = props.points.map(item => item.availableCap)
  const nowIndex = resolveNowIndex(labels)

  const tickInterval = Math.max(0, Math.floor(labels.length / 12))

  chart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(10, 22, 40, 0.92)',
        borderColor: 'rgba(18, 215, 255, 0.2)',
        borderWidth: 1,
        textStyle: { color: '#dff3ff', fontSize: 12 },
        formatter: (params) => {
          if (!params?.length) return ''
          const time = params[0].axisValue
          let html = `<div style="font-size:12px;color:#9fc4df;margin-bottom:4px">${time}</div>`
          params.forEach(p => {
            const val = p.value != null ? Number(p.value).toFixed(1) + ' MW' : '--'
            html += `<div style="display:flex;justify-content:space-between;gap:16px;font-size:12px"><span>${p.marker} ${p.seriesName}</span><span style="font-weight:600;color:#dff3ff">${val}</span></div>`
          })
          return html
        }
      },
      legend: {
        data: [
          { name: '实绩功率', icon: 'path://M0,4L12,4', itemStyle: { color: '#2dd4bf' } },
          { name: '短期预测', icon: 'path://M0,4L4,4L6,1L8,7L10,4L12,4', itemStyle: { color: '#60a5fa' } },
          { name: '超短期预测', icon: 'path://M0,4L3,4L4,1L5,7L6,4L9,4L10,1L11,7L12,4', itemStyle: { color: '#fbbf24' } },
          { name: '可用容量上限', icon: 'path://M0,4L12,4', itemStyle: { color: '#a78bfa' } }
        ],
        top: 0,
        left: 'center',
        itemWidth: 16,
        itemHeight: 8,
        textStyle: { color: '#9fc4df', fontSize: 11 }
      },
      grid: { top: 34, right: 28, bottom: 38, left: 52 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: {
          color: '#7a96aa',
          fontSize: 11,
          interval: tickInterval,
          formatter: (val) => {
            const m = String(val).match(/^(\d{2}):00$/)
            return m ? val : ''
          }
        },
        axisLine: { lineStyle: { color: 'rgba(159,182,204,.18)' } },
        splitLine: { show: false }
      },
      yAxis: {
        type: 'value',
        name: 'MW',
        nameTextStyle: { color: '#7a96aa', fontSize: 11 },
        axisLabel: { color: '#7a96aa', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(159,182,204,.08)', type: 'dashed' } }
      },
      dataZoom: [
        { type: 'inside' },
        {
          type: 'slider',
          height: 14,
          bottom: 6,
          borderColor: 'rgba(159,182,204,.2)',
          backgroundColor: 'rgba(9,20,32,.6)',
          fillerColor: 'rgba(18,215,255,.15)'
        }
      ],
      series: [
        {
          name: '实绩功率',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.2, color: '#2dd4bf', type: 'solid' },
          data: actual
        },
        {
          name: '短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#60a5fa', type: 'dashed' },
          data: shortTerm
        },
        {
          name: '超短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#fbbf24', type: [8, 4, 2, 4] },
          data: ultraShort,
          markLine: {
            symbol: 'none',
            lineStyle: { color: 'rgba(220,235,250,0.45)', width: 1.5, type: 'dashed' },
            label: {
              show: true,
              position: 'start',
              rotate: 0,
              formatter: () => {
                const d = new Date()
                const hh = String(d.getHours()).padStart(2, '0')
                const mm = String(d.getMinutes()).padStart(2, '0')
                return `当前 ${hh}:${mm}`
              },
              color: '#c8dce8',
              fontSize: 11,
              backgroundColor: 'rgba(18,24,39,0.85)',
              padding: [3, 8, 3, 8],
              borderRadius: 3
            },
            data: [{ xAxis: nowIndex }]
          }
        },
        {
          name: '可用容量上限',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.5, color: '#a78bfa', type: 'solid' },
          areaStyle: { color: 'rgba(167,139,250,0.06)' },
          data: availableCap
        }
      ]
    },
    true
  )
}

const handleResize = () => { if (!disposed && chart) chart.resize() }

onMounted(() => {
  chart = echarts.init(chartRef.value)
  render()
  window.addEventListener('resize', handleResize)
})

watch(() => props.points, render, { deep: true })

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.chart-host {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.range-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
  flex-shrink: 0;
}

.range-btn {
  padding: 2px 10px;
  font-size: 11px;
  color: #7a96aa;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(136, 186, 217, 0.15);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.range-btn:hover {
  color: #9fc4df;
  border-color: rgba(18, 215, 255, 0.3);
}

.range-btn.active {
  color: #12d7ff;
  background: rgba(18, 215, 255, 0.1);
  border-color: rgba(18, 215, 255, 0.4);
}

.chart-canvas {
  flex: 1;
  min-height: 180px;
}
</style>
```

- [ ] **Step 2: 在 HomePage 中接收 range-change 事件**

在 `HomePage.vue` 中修改 `<PowerTrendChart>` 标签，增加事件处理：

找到 HomePage.vue 模板中的：
```html
<PowerTrendChart v-if="trendPoints.length" :points="trendPoints" />
```

替换为：
```html
<PowerTrendChart v-if="trendPoints.length" :points="trendPoints" @range-change="onRangeChange" />
```

然后在 `<script setup>` 中增加 `onRangeChange` 函数。找到 `async function loadData()` 函数定义之前，添加：

```javascript
const activeRange = ref('1d')

function getRangeDates(range) {
  const now = new Date()
  const end = new Date(now)
  end.setHours(23, 59, 59, 999)
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  if (range === '3d') start.setDate(start.getDate() - 2)
  if (range === '7d') start.setDate(start.getDate() - 6)

  const fmt = (d) => {
    const y = d.getFullYear()
    const m = `${d.getMonth() + 1}`.padStart(2, '0')
    const day = `${d.getDate()}`.padStart(2, '0')
    const hh = `${d.getHours()}`.padStart(2, '0')
    const mm = `${d.getMinutes()}`.padStart(2, '0')
    const ss = `${d.getSeconds()}`.padStart(2, '0')
    return `${y}-${m}-${day} ${hh}:${mm}:${ss}`
  }
  return { start: fmt(start), end: fmt(end) }
}

async function onRangeChange(range) {
  activeRange.value = range
  loading.value = true
  const farmCode = farmService.getCurrentFarm()
  const rangeDates = getRangeDates(range)
  try {
    const trend = await getDashboardTrend({
      farmCode,
      start: rangeDates.start,
      end: rangeDates.end
    })
    trendPoints.value = trend || []
  } catch (error) {
    console.warn('趋势数据加载失败:', error?.message || error)
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 3: 验证趋势图交互**

刷新页面，确认：
- 趋势图左上角出现 1D / 3D / 7D 按钮组
- 点击 3D 按钮后图表数据刷新为 3 天范围
- 点击 1D 恢复为当天视图
- tooltip 样式优化（深色背景，青色边框）

Expected: 时间范围按钮可交互，图表数据随范围切换更新。

- [ ] **Step 4: Commit**

```bash
git add wind-power-forecast/frontend/src/components/dashboard/PowerTrendChart.vue wind-power-forecast/frontend/src/components/HomePage.vue
git commit -m "feat: add time range selector (1D/3D/7D) to power trend chart"
```

---

### Task 5: 优化 FleetMap 表格样式

**Files:**
- Modify: `frontend/src/components/dashboard/FleetMap.vue`

**Goal:** 表头增加背景色区分，图例改为水平排列紧凑化。

- [ ] **Step 1: 修改 FleetMap.vue 样式**

在 `frontend/src/components/dashboard/FleetMap.vue` 的 `<style scoped>` 中，修改以下 CSS 规则：

找到：
```css
.status-matrix th {
  font-size: 12px;
  color: #9fc4df;
  background: rgba(7, 24, 39, 0.5);
}
```

替换为：
```css
.status-matrix th {
  font-size: 12px;
  color: #9fc4df;
  background: rgba(18, 215, 255, 0.06);
  border-bottom: 1px solid rgba(18, 215, 255, 0.12);
}
```

找到：
```css
.legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #7ca0b8;
}
```

替换为：
```css
.legend {
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: #7ca0b8;
  padding-top: 6px;
  border-top: 1px solid rgba(136, 186, 217, 0.08);
  margin-top: 4px;
}
```

- [ ] **Step 2: 验证矩阵样式**

刷新页面，确认：
- 表头行有淡青色背景，与数据行有明显区分
- 图例上方有细分割线，视觉上与数据区域分离

Expected: 表头更醒目，图例更紧凑。

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend/src/components/dashboard/FleetMap.vue
git commit -m "style: improve FleetMap table header and legend styling"
```

---

### Task 6: 最终验证和调整

**Goal:** 整体验证所有改动的视觉效果和交互功能。

- [ ] **Step 1: 启动前端，全面验证**

Run: `cd wind-power-forecast/frontend && npm run serve`

验证清单：
- [ ] 三行布局正确：header → KPI → 主体
- [ ] 4 个 KPI 卡片等宽等高，颜色区分明显
- [ ] 趋势图占左侧约 2/3 面积
- [ ] 气象概览 2 列网格，指标可读
- [ ] 任务矩阵表头有背景色区分
- [ ] 1D/3D/7D 按钮交互正常
- [ ] 刷新按钮功能正常
- [ ] 农场切换器切换后数据刷新
- [ ] 窗口缩小到 1280px 以下时自动变为单列
- [ ] 控制台无报错

- [ ] **Step 2: 修复发现的任何视觉问题**

如果发现对齐偏差或样式不一致，微调 CSS。

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "style: final dashboard layout polish and alignment fixes"
```
