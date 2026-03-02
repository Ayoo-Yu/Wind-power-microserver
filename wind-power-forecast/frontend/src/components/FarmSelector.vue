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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
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
    // 褰撳墠閫変腑鐨勯鍦?
    const currentFarm = ref(farmService.getCurrentFarm())

    // 鍙敤鐨勯鍦哄垪琛?
    const availableFarms = ref(farmService.getAvailableFarms())

    // 璁＄畻褰撳墠椋庡満鍚嶇О
    const currentFarmName = computed(() => {
      const farm = availableFarms.value.find(f => f.code === currentFarm.value)
      return farm ? farm.name : '鏈煡椋庡満'
    })

    // 澶勭悊椋庡満鍒囨崲
    const handleFarmChange = (farmCode) => {
      if (farmCode !== currentFarm.value) {
        // 浣跨敤farmService璁剧疆褰撳墠鍦虹珯
        farmService.setCurrentFarm(farmCode)
        currentFarm.value = farmCode

        // 鍙戦€佷簨浠堕€氱煡鐖剁粍浠?
        emit('farm-changed', farmCode)

        ElMessage.success(`宸插垏鎹㈠埌 ${currentFarmName.value}`)
      }
    }

    // 鐩戝惉farmService涓殑椋庡満鍙樺寲
    const handleFarmServiceChange = (farmCode) => {
      currentFarm.value = farmCode
      emit('farm-changed', farmCode)
    }

    // 鐩戝惉椋庡満鍙樺寲锛屽彲浠ュ湪杩欓噷娣诲姞棰濆鐨勯€昏緫
    watch(currentFarm, (newFarm, oldFarm) => {
      console.log(`椋庡満宸蹭粠 ${oldFarm} 鍒囨崲鍒?${newFarm}`)
    })

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
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #111827;
  min-width: 140px;
  justify-content: space-between;
}

.farm-selector-trigger:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
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
}

.farm-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.farm-name {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
}

.farm-code {
  font-size: 12px;
  color: #6b7280;
}

.check-icon {
  color: #34C759;
  font-size: 16px;
}

/* 下拉项样式（Element Plus 实际类名为 el-dropdown-menu__item） */
:deep(.el-dropdown-menu__item) {
  color: #111827 !important;
  padding: 8px 16px !important;
  background: #ffffff !important;
}

:deep(.el-dropdown-menu__item:hover) {
  background: #f3f4f6 !important;
  color: #111827 !important;
}

:deep(.el-dropdown-menu__item.is-active) {
  background: #ecfdf3 !important;
  color: #047857 !important;
}

:deep(.el-dropdown-menu__item.is-active .farm-name) {
  color: #047857 !important;
}

:deep(.el-dropdown-menu__item.is-active .farm-code) {
  color: #065f46 !important;
}

/* 鍝嶅簲寮忚璁?*/
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

