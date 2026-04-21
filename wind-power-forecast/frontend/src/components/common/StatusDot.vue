<template>
  <span class="status-dot" :class="statusClass" />
</template>

<script setup>
/* global defineProps */
import { computed } from 'vue'

const props = defineProps({
  active: {
    type: Boolean,
    default: false
  }
})

const statusClass = computed(() => (props.active ? 'active' : 'inactive'))
</script>

<style scoped>
.status-dot {
  width: 10px;
  height: 10px;
  display: inline-block;
  border-radius: 999px;
}

.active {
  background: var(--accent-2);
  box-shadow: 0 0 0 0 rgba(45, 211, 111, 0.6), 0 0 6px rgba(45, 211, 111, 0.3);
  animation: pulse 1.8s infinite;
}

.inactive {
  background: var(--text-muted);
}

@keyframes pulse {
  70% { box-shadow: 0 0 0 8px rgba(45, 211, 111, 0); }
  100% { box-shadow: 0 0 0 0 rgba(45, 211, 111, 0); }
}
</style>
