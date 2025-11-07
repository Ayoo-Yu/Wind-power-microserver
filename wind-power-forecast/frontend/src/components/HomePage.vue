<!-- src/views/Home.vue -->
<template>
  <div class="home-container">
    <div class="page-shell">
      <section class="hero-panel glass-panel fade-in-up">
        <div class="hero-grid">
          <div class="hero-info">
            <p class="hero-eyebrow">WIND POWER INTELLIGENCE</p>
            <h1>中国三峡集团风电功率预测平台</h1>
            <p class="hero-subtitle">融合气象数据、机组状态与AI建模的全链路预测中枢，为场站调度提供毫秒级支撑。</p>
            <div class="hero-chips">
              <span class="chip primary">AI预测引擎</span>
              <span class="chip">多时段预测</span>
              <span class="chip success">稳定运行</span>
            </div>
          </div>
          <div class="hero-stats metric-grid">
            <div class="metric-card">
              <span class="metric-label">覆盖场站</span>
              <span class="metric-value">42</span>
              <span class="metric-meta">数据实时同步</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">今日预测功率</span>
              <span class="metric-value">1.32GW</span>
              <span class="metric-meta trend-up">+8.4% 较昨日</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">模型稳定性</span>
              <span class="metric-value">99.2%</span>
              <span class="metric-meta">误差持续优化</span>
            </div>
          </div>
        </div>
      </section>

      <section class="features-section fade-in-up">
        <div class="section-header">
          <h2 class="section-title">核心功能矩阵</h2>
          <p class="section-subtitle">CORE MODULES</p>
        </div>
        <div class="features-grid">
          <article class="feature-card glass-panel feature-card--train">
            <div class="feature-icon">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <h3>功率预测模型训练</h3>
            <p>融合历史功率、气象因子与现场状态，自动完成参数寻优与版本管理。</p>
            <div class="feature-meta">
              <span>自动评估</span>
              <span>模型追踪</span>
            </div>
            <el-button
              v-if="hasPermission('train_models')"
              type="primary"
              @click="navigate('/modeltrain')"
            >
              进入模块
            </el-button>
          </article>

          <article class="feature-card glass-panel feature-card--forecast">
            <div class="feature-icon">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <h3>风电功率预测</h3>
            <p>秒级输出超短期、短期预测曲线，支持多场站并行决策，精准驱动调度。</p>
            <div class="feature-meta">
              <span>多模型融合</span>
              <span>误差诊断</span>
            </div>
            <el-button
              v-if="hasPermission('run_predictions')"
              type="primary"
              @click="navigate('/powerpredict')"
            >
              进入模块
            </el-button>
          </article>

          <article class="feature-card glass-panel feature-card--auto">
            <div class="feature-icon">
              <el-icon><PieChart /></el-icon>
            </div>
            <h3>功率自动化预测</h3>
            <p>自动调度每日批量预测任务，输出规范化报表并推送至业务系统。</p>
            <div class="feature-meta">
              <span>任务编排</span>
              <span>智能上报</span>
            </div>
            <el-button
              v-if="hasPermission('run_predictions')"
              type="primary"
              @click="navigate('/autopredict')"
            >
              进入模块
            </el-button>
          </article>

          <article class="feature-card glass-panel feature-card--compare">
            <div class="feature-icon">
              <el-icon><Histogram /></el-icon>
            </div>
            <h3>数据对比与洞察</h3>
            <p>多维度交互式可视化，快速识别预测偏差与实际运行差异。</p>
            <div class="feature-meta">
              <span>指标分析</span>
              <span>自定义看板</span>
            </div>
            <el-button
              v-if="hasPermission('view_all_data')"
              type="primary"
              @click="navigate('/powercompare')"
            >
              进入模块
            </el-button>
          </article>
        </div>
      </section>

      <section class="system-overview glass-panel fade-in-up">
        <div class="overview-header">
          <h2>系统运行概览</h2>
          <p>核心模块统一调度，实时监控数据链路状态与模型健康。</p>
        </div>
        <div class="overview-grid">
          <div class="overview-item">
            <span class="label">数据刷新频率</span>
            <span class="value">15s</span>
          </div>
          <div class="overview-item">
            <span class="label">任务自动化覆盖</span>
            <span class="value">98%</span>
          </div>
          <div class="overview-item">
            <span class="label">异常告警响应</span>
            <span class="value">&lt; 3min</span>
          </div>
          <div class="overview-item">
            <span class="label">历史数据资产</span>
            <span class="value">12TB</span>
          </div>
        </div>
      </section>

      <footer class="footer fade-in-up">
        <p>&copy; 2025 中国三峡集团 · 风电功率预测平台</p>
      </footer>
    </div>
  </div>
</template>

<script>
import { inject } from 'vue'
import { useRouter } from 'vue-router'

export default {
  name: 'HomePage',
  setup() {
    const hasPermission = inject('hasPermission', () => true)
    const router = useRouter()

    const navigate = (path) => {
      if (path) {
        router.push(path)
      }
    }

    return {
      hasPermission,
      navigate,
    }
  },
}
</script>

<style scoped>
.home-container {
  position: relative;
  z-index: 1;
  color: var(--text-primary);
}

.hero-panel {
  margin-bottom: var(--section-gap);
  overflow: hidden;
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 36px;
  align-items: stretch;
}

.hero-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hero-eyebrow {
  font-size: 13px;
  letter-spacing: 0.48em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0;
}

.hero-info h1 {
  margin: 0;
  font-size: 48px;
  font-weight: 600;
  letter-spacing: 0.12em;
  line-height: 1.18;
  text-transform: uppercase;
}

.hero-subtitle {
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
  color: var(--text-secondary);
  letter-spacing: 0.08em;
}

.hero-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.hero-stats {
  align-content: start;
}

.metric-card {
  position: relative;
}

.metric-meta {
  font-size: 13px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-secondary);
  display: inline-block;
  margin-top: 12px;
}

.metric-meta.trend-up {
  color: var(--accent-secondary);
}

.features-section {
  margin-bottom: var(--section-gap);
}

.section-header {
  text-align: center;
  margin-bottom: 28px;
}

.section-subtitle {
  margin-top: 8px;
  letter-spacing: 0.28em;
}

.features-grid {
  display: grid;
  gap: 28px;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.feature-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 28px;
}

.feature-card::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(160deg, rgba(56, 196, 255, 0.22), transparent 65%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.feature-card:hover::after {
  opacity: 0.6;
}

.feature-icon {
  width: 60px;
  height: 60px;
  border-radius: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #031320;
  box-shadow: 0 18px 36px rgba(4, 20, 40, 0.35);
}

.feature-card h3 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.feature-card p {
  margin: 0;
  font-size: 15px;
  line-height: 1.65;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  flex: 1;
}

.feature-meta {
  display: inline-flex;
  gap: 10px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.feature-card--train .feature-icon {
  background: linear-gradient(135deg, #3AA4FF, #5BE4FF);
}

.feature-card--forecast .feature-icon {
  background: linear-gradient(135deg, #22F6AA, #4AE8D0);
}

.feature-card--auto .feature-icon {
  background: linear-gradient(135deg, #776BFF, #9A9EFF);
}

.feature-card--compare .feature-icon {
  background: linear-gradient(135deg, #FFB34F, #FF8B2F);
}

.feature-card :deep(.el-button) {
  align-self: flex-start;
  margin-top: 12px;
}

.system-overview {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.overview-header h2 {
  margin: 0;
  font-size: 24px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.overview-header p {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--text-secondary);
  letter-spacing: 0.08em;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 18px;
}

.overview-item {
  padding: 18px 20px;
  border-radius: 14px;
  background: rgba(5, 16, 34, 0.8);
  border: 1px solid rgba(56, 196, 255, 0.18);
  box-shadow: 0 14px 32px rgba(3, 13, 30, 0.5);
}

.overview-item .label {
  display: block;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.overview-item .value {
  font-size: 26px;
  font-weight: 600;
  letter-spacing: 0.24em;
  text-transform: uppercase;
}

.footer {
  text-align: center;
  padding: 32px 0 8px;
  font-size: 12px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--text-muted);
}

@media (max-width: 1280px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }

  .hero-stats {
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  }
}

@media (max-width: 768px) {
  .hero-info h1 {
    font-size: 32px;
  }

  .hero-panel {
    padding: 24px;
  }

  .features-grid {
    grid-template-columns: 1fr;
  }

  .feature-card {
    padding: 24px;
  }
}
</style>
