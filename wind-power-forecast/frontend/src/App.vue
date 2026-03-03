<template>
  <div class="app-container">
    <router-view />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { ensureFormControlsTextColor } from './utils/styleCheck'

onMounted(() => {
  ensureFormControlsTextColor()
})
</script>

<style>
.app-container {
  min-height: 100vh;
  background: transparent;
}
</style>
