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
import { ref, computed, onMounted, watch } from 'vue'
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

    // 可用的风场列表
    const availableFarms = ref(farmService.getAvailableFarms())

    // 计算当前风场名称
    const currentFarmName = computed(() => {
      const farm = availableFarms.value.find(f => f.code === currentFarm.value)
      return farm ? farm.name : '未知风场'
    })

    // 处理风场切换
    const handleFarmChange = (farmCode) => {
      if (farmCode !== currentFarm.value) {
        // 使用farmService设置当前场站
        farmService.setCurrentFarm(farmCode)
        currentFarm.value = farmCode

        // 发送事件通知父组件
        emit('farm-changed', farmCode)

        ElMessage.success(`已切换到 ${currentFarmName.value}`)
      }
    }

    // 监听farmService中的风场变化
    const handleFarmServiceChange = (farmCode) => {
      currentFarm.value = farmCode
      emit('farm-changed', farmCode)
    }

    // 监听风场变化，可以在这里添加额外的逻辑
    watch(currentFarm, (newFarm, oldFarm) => {
      console.log(`风场已从 ${oldFarm} 切换到 ${newFarm}`)
    })

    // 组件挂载时，添加监听器
    onMounted(async () => {
      // 拉取最新场站列表（失败时farmService内部自动回退）
      await farmService.loadAvailableFarms()
      availableFarms.value = farmService.getAvailableFarms()

      // 确保localStorage中有值
      if (!localStorage.getItem('selectedFarm')) {
        farmService.resetToDefault()
        currentFarm.value = farmService.getCurrentFarm()
      }

      // 当前场站如果已不在列表中，切到默认/首个可用场站
      const exists = availableFarms.value.some(f => f.code === currentFarm.value)
      if (!exists && availableFarms.value.length > 0) {
        farmService.setCurrentFarm(availableFarms.value[0].code)
        currentFarm.value = farmService.getCurrentFarm()
      }

      // 监听farmService的变化
      farmService.addListener(handleFarmServiceChange)
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
  color: var(--text-primary);
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
  color: var(--text-primary);
}

.farm-code {
  font-size: 12px;
  color: var(--text-secondary);
}

.check-icon {
  color: #34C759;
  font-size: 16px;
}

/* 激活状态的下拉项 */
.el-dropdown-item.is-active {
  background: linear-gradient(90deg, rgba(52, 199, 89, 0.1), transparent);
  color: #34C759;
}

.el-dropdown-item {
  padding: 8px 16px;
}

.el-dropdown-item:hover {
  background: rgba(255, 255, 255, 0.05);
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
