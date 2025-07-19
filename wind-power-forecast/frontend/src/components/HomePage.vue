<!-- src/views/Home.vue -->
<template>
  <div class="home-container">
    <div class="content-container">
      <!-- 头部区域 -->
      <div class="hero-section">
        <h1>中国三峡集团风电功率预测平台</h1>
        <p class="subtitle">智能 · 高效 · 精准</p>
      </div>

      <!-- 功能卡片区域 -->
      <div class="features-section">
        <!-- 模型训练 -->
        <div class="feature-card">
          <div class="card-content">
            <div class="icon-wrapper">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <h3>功率预测模型训练</h3>
            <p>通过先进的算法进行高效的模型训练，提升预测准确度。</p>
            <el-button 
              v-if="hasPermission('train_models')"
              type="primary" 
              class="learn-more-btn"
              @click="urljump('http://localhost:8080/modeltrain')"
            >
              了解更多
              <el-icon class="arrow-icon"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- 功率预测 -->
        <div class="feature-card">
          <div class="card-content">
            <div class="icon-wrapper">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <h3>风电功率预测</h3>
            <p>通过精确的算法进行未来功率的预测，助力决策制定。</p>
            <el-button 
              v-if="hasPermission('run_predictions')"
              type="primary" 
              class="learn-more-btn"
              @click="urljump('http://localhost:8080/powerpredict')"
            >
              了解更多
              <el-icon class="arrow-icon"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- 数据可视化 -->
        <div class="feature-card">
          <div class="card-content">
            <div class="icon-wrapper">
              <el-icon><PieChart /></el-icon>
            </div>
            <h3>功率自动化预测</h3>
            <p>实现三类风电功率每日预测，包括超短期、短期、中期预测。</p>
            <el-button 
              v-if="hasPermission('run_predictions')"
              type="primary" 
              class="learn-more-btn"
              @click="urljump('http://localhost:8080/autopredict')"
            >
              了解更多
              <el-icon class="arrow-icon"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- 功率对比 -->
        <div class="feature-card">
          <div class="card-content">
            <div class="icon-wrapper">
              <el-icon><Histogram /></el-icon>
            </div>
            <h3>数据可视化</h3>
            <p>对比不同时间段的预测数据，开展数据可视化与分析。</p>
            <el-button 
              v-if="hasPermission('view_all_data')"
              type="primary" 
              class="learn-more-btn"
              @click="urljump('http://localhost:8080/powercompare')"
            >
              了解更多
              <el-icon class="arrow-icon"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 图表展示区域 -->
      <!-- <div class="chart-section">
        <div class="section-header">
          <h2>风电功率月度变化</h2>
          <p class="section-subtitle">实时监控风电场发电情况</p>
        </div>
        <div class="chart-container">
          <canvas id="powerChart"></canvas>
        </div>
      </div> -->

      <!-- 底部区域 -->
      <footer class="footer">
        <p>&copy; 2025 中国三峡集团. 版权所有.</p>
      </footer>
    </div>
  </div>
</template>

<script>
import { onMounted, ref, computed, inject } from 'vue'
import { ElMessage } from 'element-plus'
// import Chart from 'chart.js/auto'
// Import BarChart if it's a specific component and not globally registered
// import { BarChart } from '@element-plus/icons-vue' // Example import

export default {
  name: 'HomePage',
  methods: {
    urljump(url) {
      window.location.href = url;
    },
  },

  setup() {
    const activeMenu = ref('1')
    const hasPermission = inject('hasPermission')

    const viewDetails = () => {
      ElMessage.info('更多详情即将推出！')
    }

    // 计算背景内联样式
    const backgroundStyle = computed(() => ({
      position: 'absolute',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      background: 'linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab)',
      backgroundSize: '400% 400%',
      animation: 'gradient 15s ease infinite',
      zIndex: -1,
    }))

    onMounted(() => {
      // const ctx = document.getElementById('powerChart').getContext('2d')
      // new Chart(ctx, {
      //   type: 'line',
      //   data: {
      //     labels: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'],
      //     datasets: [{
      //       label: '风电功率 (MW)',
      //       data: [12, 19, 3, 5, 2, 3, 6, 8, 13, 20, 18, 22],
      //       backgroundColor: 'rgba(54, 162, 235, 0.2)',
      //       borderColor:'rgba(54, 162, 235, 1)',
      //       borderWidth: 2,
      //       fill: true,
      //       tension: 0.5
      //     }]
      //   },
      //   options: {
      //     responsive: true,
      //     plugins: {
      //       legend: {
      //         position: 'top',
      //       },
      //       title: {
      //         display: true,
      //       }
      //     },
      //     scales: {
      //       y: { 
      //         beginAtZero: true,
      //         title: {
      //           display: true,
      //           text: '功率 (MW)'
      //         }
      //       },
      //       x: {
      //         title: {
      //           display: true,
      //           text: '月份'
      //         }
      //       }
      //     }
      //   }
      // })
    })

    return {
      activeMenu,
      viewDetails,
      backgroundStyle,
      hasPermission,
    }
  }
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
}

@keyframes gradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.content-container {
  flex: 1;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(5px);
  padding: 40px;
  border-radius: 30px;
  margin: 40px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.hero-section {
  text-align: center;
  padding: 120px 20px;
  position: relative;
}

.hero-section::before {
  content: "✨";
  position: absolute;
  top: 60px;
  left: 20%;
  font-size: 24px;
  opacity: 0.5;
}

.hero-section::after {
  content: "✨";
  position: absolute;
  bottom: 60px;
  right: 20%;
  font-size: 24px;
  opacity: 0.5;
}

.hero-section h1 {
  font-size: 64px;
  font-weight: 600;
  color: white;
  margin-bottom: 20px;
  letter-spacing: -0.015em;
  line-height: 1.1;
  background: none;
  -webkit-text-fill-color: white;
}

.subtitle {
  font-size: 24px;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 40px;
  letter-spacing: 0.1em;
}

.features-section {
  display: grid;
  /* Updated to handle 4 cards in a 1x4 layout on larger screens */
  grid-template-columns: repeat(4, 1fr); 
  gap: 40px;
  padding: 0 40px;
  max-width: 1440px;
  margin: 0 auto 80px;
}

.feature-card {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 30px;
  padding: 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.04);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  border: none;
  position: relative;
}

.feature-card:nth-child(1) .icon-wrapper {
  background: linear-gradient(135deg, #0077ED 0%, #00A2FF 100%);
}

.feature-card:nth-child(1)::before {
  color: #0077ED;
}

.feature-card:nth-child(1) .learn-more-btn {
  color: #0077ED;
}

.feature-card:nth-child(1) .learn-more-btn:hover {
  color: #0062CC;
}

.feature-card:nth-child(2) .icon-wrapper {
  background: linear-gradient(135deg, #34C759 0%, #30B753 100%);
}

.feature-card:nth-child(2)::before {
  color: #34C759;
}

.feature-card:nth-child(2) .learn-more-btn {
  color: #34C759;
}

.feature-card:nth-child(2) .learn-more-btn:hover {
  color: #2CB14A;
}

.feature-card:nth-child(3) .icon-wrapper {
  background: linear-gradient(135deg, #AF52DE 0%, #9F44D3 100%);
}

.feature-card:nth-child(3)::before {
  color: #AF52DE;
}

.feature-card:nth-child(3) .learn-more-btn {
  color: #AF52DE;
}

.feature-card:nth-child(3) .learn-more-btn:hover {
  color: #9941C8;
}

/* Styling for the new 4th card - using a new color scheme */
.feature-card:nth-child(4) .icon-wrapper {
  background: linear-gradient(135deg, #FF9500 0%, #FFB340 100%); /* Orange gradient */
}

.feature-card:nth-child(4)::before {
  color: #FF9500; /* Orange color for pseudo-element */
}

.feature-card:nth-child(4) .learn-more-btn {
  color: #FF9500; /* Orange color for button text */
}

.feature-card:nth-child(4) .learn-more-btn:hover {
  color: #E68600; /* Darker orange on hover */
}

.feature-card:nth-child(1):hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 48px rgba(0, 119, 237, 0.12);
}

.feature-card:nth-child(2):hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 48px rgba(52, 199, 89, 0.12);
}

.feature-card:nth-child(3):hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 48px rgba(175, 82, 222, 0.12);
}

.feature-card:nth-child(4):hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 48px rgba(255, 149, 0, 0.12); /* Shadow color for the 4th card */
}

.icon-wrapper {
  width: 60px;
  height: 60px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.icon-wrapper .el-icon {
  font-size: 30px;
  color: #ffffff;
}

.card-content h3 {
  font-size: 24px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 16px;
  letter-spacing: -0.003em;
}

.card-content p {
  font-size: 16px;
  color: #86868b;
  line-height: 1.5;
  margin-bottom: 24px;
}

.learn-more-btn {
  background: none;
  border: none;
  font-size: 17px;
  font-weight: 500;
  padding: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.learn-more-btn:hover {
  color: #0062CC;
  transform: translateX(4px);
}

.arrow-icon {
  transition: transform 0.3s ease;
}

.learn-more-btn:hover .arrow-icon {
  transform: translateX(4px);
}

/* .chart-section {
  background: none;
  padding: 60px;
  border-radius: 30px;
}

.section-header {
  text-align: center;
  margin-bottom: 40px;
}

.section-header h2 {
  font-size: 40px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
  letter-spacing: -0.003em;
}

.section-subtitle {
  font-size: 20px;
  color: #86868b;
}

.chart-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 30px;
  border: none;
} */

.footer {
  text-align: center;
  padding: 20px;
  background: none;
  backdrop-filter: none;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .features-section {
    grid-template-columns: repeat(2, 1fr); /* Stays 2x2 for medium screens */
  }
}

@media (max-width: 768px) {
  .hero-section h1 {
    font-size: 40px;
  }

  .features-section {
    grid-template-columns: 1fr;
  }

  .feature-card {
    padding: 30px;
  }
}
</style>
