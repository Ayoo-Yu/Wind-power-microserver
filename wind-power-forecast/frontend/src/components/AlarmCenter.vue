<template>
  <div class="alarm-center page-shell">
    <div class="page-header">
      <h2>统一告警中心</h2>
      <p>集中监控红色致命告警与黄色预警，支持告警声与短信网关策略</p>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-switch v-model="enableSound" active-text="红色告警播放警报声" />
        <el-switch v-model="enableSms" active-text="红色告警触发短信网关" />
        <el-button @click="refresh">刷新</el-button>
      </div>

      <div class="stats">
        <div class="stat danger">
          <div class="label">致命告警</div>
          <div class="value">{{ dangerCount }}</div>
        </div>
        <div class="stat warning">
          <div class="label">预警</div>
          <div class="value">{{ warningCount }}</div>
        </div>
      </div>

      <el-table :data="alerts" border stripe>
        <el-table-column prop="time" label="告警时间" min-width="170" />
        <el-table-column prop="station" label="场站" min-width="130" />
        <el-table-column label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="row.level === '红色' ? 'danger' : 'warning'" effect="dark">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="所属模块" min-width="130" />
        <el-table-column prop="message" label="告警内容" min-width="360" />
        <el-table-column label="通知策略" min-width="180">
          <template #default="{ row }">
            <span v-if="row.level === '红色'">
              {{ enableSound ? '页面警报声 ' : '' }}{{ enableSms ? '短信网关' : '' || '未配置' }}
            </span>
            <span v-else>无</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { computed, ref } from 'vue'

export default {
  name: 'AlarmCenter',
  setup() {
    const enableSound = ref(true)
    const enableSms = ref(false)
    const alerts = ref([
      { time: '2026-03-05 13:22:10', station: '大青山风电场', level: '红色', module: '上报调度', message: '场站上报失败，连续 3 次重试超时' },
      { time: '2026-03-05 13:19:42', station: '全站', level: '红色', module: '系统底座', message: '数据库连接池异常，连接失败率升高' },
      { time: '2026-03-05 13:16:30', station: '乌兰风电场', level: '黄色', module: '气象拉取', message: 'NWP 文件延迟超过 20 分钟' },
      { time: '2026-03-05 13:11:15', station: '海西风电场', level: '黄色', module: '预测评估', message: '超短期预测误差超过 20%' }
    ])

    const dangerCount = computed(() => alerts.value.filter(item => item.level === '红色').length)
    const warningCount = computed(() => alerts.value.filter(item => item.level === '黄色').length)

    const playBeep = () => {
      if (!enableSound.value || dangerCount.value === 0) return
      try {
        const ctx = new window.AudioContext()
        const oscillator = ctx.createOscillator()
        const gain = ctx.createGain()
        oscillator.type = 'square'
        oscillator.frequency.value = 880
        gain.gain.value = 0.04
        oscillator.connect(gain)
        gain.connect(ctx.destination)
        oscillator.start()
        oscillator.stop(ctx.currentTime + 0.2)
      } catch (error) {
        return
      }
    }

    const refresh = () => {
      playBeep()
    }

    return {
      enableSound,
      enableSms,
      alerts,
      dangerCount,
      warningCount,
      refresh
    }
  }
}
</script>

<style scoped>
.alarm-center {
  min-height: 100%;
  padding: 20px;
}
.page-header h2 { margin: 0; color: var(--text-primary); }
.page-header p { margin: 8px 0 14px; color: var(--text-secondary); }
.card-shell { background: rgba(6, 21, 34, 0.86); border: 1px solid rgba(130, 178, 212, 0.2); }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
.stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.stat { border-radius: 10px; padding: 12px; border: 1px solid rgba(130, 178, 212, 0.2); }
.stat .label { color: var(--text-secondary); font-size: 12px; }
.stat .value { color: var(--text-primary); font-size: 24px; margin-top: 4px; font-weight: 700; }
.stat.danger { background: rgba(160, 32, 32, 0.22); }
.stat.warning { background: rgba(165, 115, 30, 0.2); }
</style>
