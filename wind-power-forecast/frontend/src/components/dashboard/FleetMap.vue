<template>
  <div class="matrix-wrap">
    <table class="status-matrix">
      <thead>
        <tr>
          <th>场站</th>
          <th v-for="task in taskHeaders" :key="task.key">{{ task.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in points" :key="row.code">
          <td class="farm-name">{{ row.name }}</td>
          <td v-for="task in taskHeaders" :key="`${row.code}-${task.key}`">
            <span class="status-chip" :class="`status-${row.tasks?.[task.key] || 'warn'}`">
              {{ statusSymbol(row.tasks?.[task.key]) }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
    <div class="legend">
      <span><i class="dot ok">●</i> 正常 ✅</span>
      <span><i class="dot warn">●</i> 延迟 ⚠️</span>
      <span><i class="dot error">●</i> 失败 ❌</span>
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
  if (status === 'ok') return '✅'
  if (status === 'error') return '❌'
  return '⚠️'
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

.status-matrix th,
.status-matrix td {
  border: 1px solid rgba(136, 186, 217, 0.18);
  padding: 8px 6px;
  text-align: center;
}

.status-matrix th {
  font-size: 12px;
  color: #9fc4df;
  background: rgba(7, 24, 39, 0.7);
}

.farm-name {
  color: #d8ebff;
  font-size: 13px;
  text-align: left !important;
  padding-left: 10px !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 24px;
  border-radius: 7px;
  font-size: 14px;
}

.status-ok {
  background: rgba(45, 211, 111, 0.2);
}

.status-warn {
  background: rgba(246, 183, 60, 0.2);
}

.status-error {
  background: rgba(255, 93, 115, 0.2);
  animation: blink 1.2s ease-in-out infinite;
}

.legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #9fc4df;
}

.dot {
  font-style: normal;
  margin-right: 4px;
}

.dot.ok {
  color: #2dd36f;
}

.dot.warn {
  color: #f6b73c;
}

.dot.error {
  color: #ff5d73;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

@media (max-width: 860px) {
  .status-matrix {
    font-size: 12px;
  }
}
</style>
