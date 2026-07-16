<!-- src/components/FarmSelector.vue -->
<template>
  <div class="farm-selector">
    <el-dropdown @command="handleFarmChange" trigger="click">
      <div class="farm-selector-trigger">
        <el-icon><Location /></el-icon>
        <span class="current-farm">{{ currentFarmName }}</span>
        <el-icon class="arrow-icon"><ArrowDown /></el-icon>
      </div>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="farm in availableFarms"
            :key="farm.code"
            :command="farm.code"
            :class="{ 'is-active': farm.code === currentFarm }"
          >
            <div class="farm-item">

              <div class="farm-info">
                <div class="farm-name">{{ farm.name }}</div>
                <div class="farm-code">{{ farm.code }}</div>
              </div>
              <el-icon v-if="farm.code === currentFarm" class="check-icon">
                <Check />
              </el-icon>
            </div>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Location, ArrowDown, Check } from '@element-plus/icons-vue'
import farmService from '../utils/farmService'

export default {
  name: 'FarmSelector',
  components: {
    Location,
    ArrowDown,
    Check
  },
  emits: ['farm-changed'],
  setup(props, { emit }) {
    // 当前选中的风场
    const currentFarm = ref(farmService.getCurrentFarm())

    // 可用风场列表
    const availableFarms = ref(farmService.getAvailableFarms())

    // 计算当前风场名称
    const currentFarmName = computed(() => {
      const farm = availableFarms.value.find(f => f.code === currentFarm.value)
      return farm ? farm.name : '未知风场'
    })

    // 处理风场切换
    const handleFarmChange = (farmCode) => {
      if (farmCode !== currentFarm.value) {
        // 使用 farmService 设置当前场站
        farmService.setCurrentFarm(farmCode)
        currentFarm.value = farmCode

        // 发送事件通知父组件
        emit('farm-changed', farmCode)

        ElMessage.success(`已切换到 ${currentFarmName.value}`)
      }
    }

    // 监听 farmService 中的风场变化
    const handleFarmServiceChange = (farmCode) => {
      currentFarm.value = farmCode
      emit('farm-changed', farmCode)
    }

    // 组件挂载时，初始化场站列表并同步当前选择
    onMounted(async () => {
      await farmService.loadAvailableFarms()
      availableFarms.value = farmService.getAvailableFarms()

      if (!localStorage.getItem('selectedFarm')) {
        farmService.resetToDefault()
        currentFarm.value = farmService.getCurrentFarm()
      }

      const exists = availableFarms.value.some(f => f.code === currentFarm.value)
      if (!exists && availableFarms.value.length > 0) {
        farmService.setCurrentFarm(availableFarms.value[0].code)
        currentFarm.value = farmService.getCurrentFarm()
      }

      farmService.addListener(handleFarmServiceChange)
    })

    onUnmounted(() => {
      farmService.removeListener(handleFarmServiceChange)
    })

    return {
      currentFarm,
      availableFarms,
      currentFarmName,
      handleFarmChange
    }
  }
}
</script>

<style scoped>
.farm-selector {
  display: inline-block;
}

.farm-selector-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  cursor: pointer;
  transition: all var(--transition-normal);
  color: var(--text-primary);
  min-width: 140px;
  justify-content: space-between;
}

.farm-selector-trigger:hover {
  background: var(--surface-soft);
  border-color: rgba(36, 122, 82, 0.4);
}

.current-farm {
  font-size: 14px;
  font-weight: 500;
  flex: 1;
  text-align: center;
}

.arrow-icon {
  font-size: 12px;
  transition: transform 0.3s ease;
}

.farm-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  min-width: 180px;
  gap: 8px;
}

.farm-item-icon {
  color: var(--primary);
  font-size: 16px;
  flex-shrink: 0;
}

.farm-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.farm-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.farm-code {
  font-size: 12px;
  color: var(--text-muted);
}

.check-icon {
  color: var(--primary);
  font-size: 16px;
}

/* 下拉项样式（Element Plus 实际类名为 el-dropdown-menu__item） */
:deep(.el-dropdown-menu__item) {
  color: var(--text-primary) !important;
  padding: 8px 16px !important;
  background: var(--surface) !important;
}

:deep(.el-dropdown-menu__item:hover) {
  background: var(--surface-soft) !important;
  color: var(--text-primary) !important;
}

:deep(.el-dropdown-menu__item.is-active) {
  background: var(--primary-soft) !important;
  color: var(--primary) !important;
}

:deep(.el-dropdown-menu__item.is-active .farm-name) {
  color: var(--primary) !important;
}

:deep(.el-dropdown-menu__item.is-active .farm-code) {
  color: var(--primary) !important;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .farm-selector-trigger {
    padding: 6px 12px;
    min-width: 120px;
  }

  .current-farm {
    font-size: 12px;
  }

  .farm-item {
    min-width: 160px;
  }
}
</style>

