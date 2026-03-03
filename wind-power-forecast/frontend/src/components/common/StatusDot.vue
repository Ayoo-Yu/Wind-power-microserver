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
  background: #2dd36f;
  box-shadow: 0 0 0 0 rgba(45, 211, 111, .6);
  animation: pulse 1.8s infinite;
}

.inactive {
  background: #7f8fa3;
}

@keyframes pulse {
  70% { box-shadow: 0 0 0 8px rgba(45, 211, 111, 0); }
  100% { box-shadow: 0 0 0 0 rgba(45, 211, 111, 0); }
}
</style>
