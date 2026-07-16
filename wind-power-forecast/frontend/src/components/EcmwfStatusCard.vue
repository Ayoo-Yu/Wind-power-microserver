<template>
  <el-card class="ecmwf-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span class="card-title">ECMWF 气象数据库状态</span>
        <el-button type="info" size="small" :loading="loading" @click="$emit('refresh')">刷新</el-button>
      </div>
    </template>
    <div v-if="status" class="ecmwf-grid">
      <div v-for="(info, dtype) in status.availability" :key="dtype" class="ecmwf-item">
        <el-tag :type="info.count > 0 ? 'success' : 'info'" size="large">
          {{ dataTypeLabel(dtype) }}
        </el-tag>
        <span class="ecmwf-stat">{{ info.count }} 条</span>
        <span class="ecmwf-range" v-if="info.min_timestamp">
          {{ info.min_timestamp?.slice(0, 16) }} ~ {{ info.max_timestamp?.slice(0, 16) }}
        </span>
        <span class="ecmwf-range" v-else>无数据</span>
      </div>
      <div class="ecmwf-item">
        <el-tag type="warning" size="large">最新入库</el-tag>
        <span class="ecmwf-stat">{{ status.latest_timestamp || '暂无' }}</span>
      </div>
    </div>
    <div v-else style="color:var(--text-muted);text-align:center;padding:16px">加载中...</div>
  </el-card>
</template>

<script>
export default {
  name: 'EcmwfStatusCard',
  props: {
    status: { type: Object, default: null },
    loading: { type: Boolean, default: false },
  },
  emits: ['refresh'],
  methods: {
    dataTypeLabel(dtype) {
      const labels = { DQ: '短期', CDQ: '超短期', QXYC: '气象' }
      return labels[dtype] || dtype
    },
  },
}
</script>

<style scoped>
.ecmwf-card { margin-bottom: 20px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; }
.card-title { color: var(--text-primary); font-size: 16px; font-weight: 600; }
.ecmwf-grid { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
.ecmwf-item { display: flex; align-items: center; gap: 8px; }
.ecmwf-stat { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.ecmwf-range { font-size: 12px; color: var(--text-secondary); }
</style>
