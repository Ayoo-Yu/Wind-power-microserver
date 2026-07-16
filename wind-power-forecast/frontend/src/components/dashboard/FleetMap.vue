<template>
  <div class="matrix-wrap">
    <table class="status-matrix">
      <thead>
        <tr>
          <th class="farm-col-h">场站</th>
          <th v-for="task in taskHeaders" :key="task.key" class="task-col-h">{{ task.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in points" :key="row.code">
          <td class="farm-name">{{ row.name }}</td>
          <td v-for="task in taskHeaders" :key="`${row.code}-${task.key}`">
            <span v-if="row.tasks?.[task.key] === 'ok'" class="status-dot status-ok"></span>
            <span v-else class="status-chip" :class="`status-${row.tasks?.[task.key] || 'warn'}`">
              {{ statusSymbol(row.tasks?.[task.key]) }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
    <div class="legend">
      <span><i class="dot ok"></i> 正常</span>
      <span><i class="dot warn">●</i> 延迟</span>
      <span><i class="dot error">●</i> 失败</span>
    </div>
  </div>
</template>

<script setup>
/* global defineProps */
import { TASK_KEYS } from '@/services/dashboardService'

defineProps({
  points: {
    type: Array,
    default: () => []
  }
})

const taskHeaders = TASK_KEYS

function statusSymbol(status) {
  if (status === 'error') return '×'
  return '!'
}
</script>

<style scoped>
.matrix-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-matrix {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.status-matrix col.farm-col {
  width: 120px;
}

.status-matrix col.task-col {
  width: 56px;
}

.status-matrix th,
.status-matrix td {
  border: 1px solid var(--border-light);
  padding: 8px 6px;
  text-align: center;
}

.status-matrix th {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-soft);
  border-bottom: 1px solid var(--border-color);
}

.farm-name {
  color: var(--text-primary);
  font-size: 12px;
  text-align: left !important;
  padding-left: 8px !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.task-col-h {
  font-size: 11px !important;
  padding: 4px 2px !important;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--success);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 22px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
}

.status-warn {
  background: var(--warning-soft);
  color: var(--warning);
}

.status-error {
  background: var(--danger-soft);
  color: var(--danger);
}

.legend {
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: var(--text-muted);
  padding-top: 6px;
  border-top: 1px solid var(--border-light);
  margin-top: 4px;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}

.dot.ok {
  width: 8px;
  height: 8px;
  background: var(--success);
}

.dot.warn {
  color: var(--warning);
}

.dot.error {
  color: var(--danger);
}

@media (max-width: 860px) {
  .status-matrix {
    font-size: 12px;
  }
}
</style>
