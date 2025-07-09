<template>
  <div class="physical-simulation-container">
    <div class="content-wrapper">
      <h1 class="page-title">物理仿真数据展示</h1>
      <p class="page-subtitle">通过双线性插值计算任意工况下的风机表现</p>

      <div class="main-content">
        <!-- 参数设置区域 -->
        <div class="upload-section">
          <div class="upload-card">
            <div class="card-header">
              <h2>选择风电场</h2>
              <div class="step-number">1</div>
            </div>
            <div class="card-content">
              <el-select
                v-model="selectedFarm"
                placeholder="请选择风电场"
                @change="handleFarmSelection"
                :loading="loadingFarms"
                style="width: 100%"
                size="large"
              >
                <el-option
                  v-for="farm in farmNames"
                  :key="farm"
                  :label="farm"
                  :value="farm"
                />
              </el-select>
            </div>
          </div>

          <div class="upload-card">
            <div class="card-header">
              <h2>设置目标风速</h2>
              <div class="step-number">2</div>
            </div>
            <div class="card-content">
              <el-input
                v-model.number="targetWindSpeed"
                placeholder="请输入目标风速 (m/s)"
                type="number"
                :disabled="!selectedFarm"
                size="large"
              >
                <template #suffix>m/s</template>
              </el-input>
            </div>
          </div>

          <div class="upload-card">
            <div class="card-header">
              <h2>设置目标风向</h2>
              <div class="step-number">3</div>
            </div>
            <div class="card-content">
              <el-input
                v-model.number="targetWindDirection"
                placeholder="请输入目标风向 (°)"
                type="number"
                :disabled="!selectedFarm"
                size="large"
              >
                <template #suffix>°</template>
              </el-input>
            </div>
          </div>
        </div>

        <!-- 右侧操作面板 -->
        <div class="right-panel">
          <div class="action-card">
            <div v-if="!isReadyForSimulation" class="empty-action-panel">
              <el-icon class="empty-icon"><InfoFilled /></el-icon>
              <p class="empty-text">请完成参数设置后开始仿真计算</p>
            </div>
            <div v-else class="action-buttons">
              <el-button
                type="primary"
                size="large"
                @click="runSimulation"
                :loading="loadingSimulation"
                class="action-button predict-button"
              >
                {{ loadingSimulation ? '计算中...' : '开始仿真计算' }}
              </el-button>
            </div>
          </div>

          <!-- 仿真参数显示 -->
          <div v-if="selectedFarm" class="status-card">
            <h3>仿真参数</h3>
            <div class="card-content">
              <div class="param-item">
                <span class="param-label">风电场:</span>
                <span class="param-value">{{ selectedFarm }}</span>
              </div>
              <div class="param-item">
                <span class="param-label">目标风速:</span>
                <span class="param-value">{{ targetWindSpeed || '-' }} m/s</span>
              </div>
              <div class="param-item">
                <span class="param-label">目标风向:</span>
                <span class="param-value">{{ targetWindDirection || '-' }}°</span>
              </div>
              <div class="param-item">
                <span class="param-label">风机数量:</span>
                <span class="param-value">{{ farmTurbines.length }} 台</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 仿真结果展示区域 -->
      <div v-if="simulationResults.length > 0" class="visualization-section">
        <div class="visualization-header">
          <h3 class="section-title">仿真结果</h3>
        </div>
        
        <div class="results-container">
          <!-- 可视化图表 -->
          <div class="chart-card">
            <div class="card-header">
              <h3>风电场布局及仿真风速分布</h3>
            </div>
            <div class="chart-container">
              <div ref="plot" style="width: 100%; height: 500px;"></div>
            </div>
          </div>

          <!-- 数据表格 -->
          <div class="table-card">
            <div class="card-header">
              <h3>详细仿真数据</h3>
              <el-button type="primary" size="small" @click="exportResults">
                <el-icon><Download /></el-icon>
                导出数据
              </el-button>
            </div>
            <div class="table-container">
              <el-table
                :data="simulationResults"
                style="width: 100%"
                v-loading="loadingSimulation"
                stripe
                border
                height="452"
                :scroll-with-animation="true"
              >
                <el-table-column prop="turbine_number" label="风机编号" width="120" />
                <el-table-column prop="longitude" label="经度" width="120" />
                <el-table-column prop="latitude" label="纬度" width="120" />
                <el-table-column prop="simulated_wind_speed" label="仿真风速 (m/s)" width="150" />
                <el-table-column prop="simulated_power_output" label="仿真功率 (kW)" width="150" />
              </el-table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import Plotly from 'plotly.js-dist-min';
import { ElMessage } from 'element-plus';
import { InfoFilled, Download } from '@element-plus/icons-vue';

const API_BASE_URL = process.env.VUE_APP_API_BASE_URL || 'http://localhost:5000';

export default {
  name: 'PhysicalSimulation',
  components: {
    InfoFilled,
    Download
  },
  data() {
    return {
      farmNames: [],
      selectedFarm: null,
      targetWindSpeed: null,
      targetWindDirection: null,
      
      loadingFarms: false,
      loadingSimulation: false,
      
      farmConditions: [],
      farmTurbines: [],
      
      simulationResults: [],
    };
  },
  computed: {
    isReadyForSimulation() {
      return this.selectedFarm && 
             this.targetWindSpeed !== null && 
             this.targetWindDirection !== null &&
             this.targetWindSpeed !== '' &&
             this.targetWindDirection !== '';
    }
  },
  mounted() {
    this.fetchFarmNames();
  },
  methods: {
    async fetchFarmNames() {
      this.loadingFarms = true;
      try {
        const response = await axios.get(`${API_BASE_URL}/physical_simulation/conditions`);
        const uniqueFarms = [...new Set(response.data.map(item => item.farm_name))];
        this.farmNames = uniqueFarms;
      } catch (error) {
        console.error('Error fetching farm names:', error);
        ElMessage.error('获取风电场列表失败');
      } finally {
        this.loadingFarms = false;
      }
    },
    
    async handleFarmSelection(farmName) {
      if (!farmName) {
        this.farmConditions = [];
        this.farmTurbines = [];
        return;
      }
      
      this.loadingSimulation = true;
      try {
        const [conditionsRes, turbinesRes] = await Promise.all([
          axios.get(`${API_BASE_URL}/physical_simulation/conditions?farm_name=${farmName}`),
          axios.get(`${API_BASE_URL}/physical_simulation/turbines?farm_name=${farmName}`),
        ]);
        this.farmConditions = conditionsRes.data;
        this.farmTurbines = turbinesRes.data;
        
        ElMessage.success(`已加载 ${this.farmTurbines.length} 台风机数据`);
      } catch (error) {
        console.error(`Error fetching data for farm ${farmName}:`, error);
        ElMessage.error('获取风电场数据失败');
      } finally {
        this.loadingSimulation = false;
      }
    },
    
    findSurroundingConditions() {
      const windSpeeds = [...new Set(this.farmConditions.map(c => c.wind_speed))].sort((a, b) => a - b);
      const windDirections = [...new Set(this.farmConditions.map(c => c.wind_direction))].sort((a, b) => a - b);

      const findBounds = (arr, target) => {
        // 检查是否精确匹配现有数据点
        if (arr.includes(target)) {
          return { lower: target, upper: target, isExact: true };
        }
        
        const upper = arr.find(v => v > target);
        const lower = arr.slice().reverse().find(v => v < target);
        return { lower, upper, isExact: false };
      };

      const wsBounds = findBounds(windSpeeds, this.targetWindSpeed);
      const wdBounds = findBounds(windDirections, this.targetWindDirection);

      if ([wsBounds.lower, wsBounds.upper, wdBounds.lower, wdBounds.upper].some(v => v === undefined)) {
        ElMessage.warning("输入的目标工况超出现有数据范围，无法进行插值");
        return null;
      }

      const getConditionId = (ws, wd) => this.farmConditions.find(c => c.wind_speed === ws && c.wind_direction === wd);
      
      // 处理精确匹配的情况
      if (wsBounds.isExact && wdBounds.isExact) {
        // 两个维度都精确匹配，直接返回该条件
        const exactCondition = getConditionId(wsBounds.lower, wdBounds.lower);
        return { 
          Q11: exactCondition, Q12: exactCondition, Q21: exactCondition, Q22: exactCondition,
          wsBounds, wdBounds, isExactMatch: true 
        };
      } else if (wsBounds.isExact) {
        // 风速精确匹配，只需在风向上插值
        const Q11 = getConditionId(wsBounds.lower, wdBounds.lower);
        const Q12 = getConditionId(wsBounds.lower, wdBounds.upper);
        return { 
          Q11, Q12, Q21: Q11, Q22: Q12,
          wsBounds, wdBounds, isWindSpeedExact: true 
        };
      } else if (wdBounds.isExact) {
        // 风向精确匹配，只需在风速上插值
        const Q11 = getConditionId(wsBounds.lower, wdBounds.lower);
        const Q21 = getConditionId(wsBounds.upper, wdBounds.lower);
        return { 
          Q11, Q12: Q11, Q21, Q22: Q21,
          wsBounds, wdBounds, isWindDirectionExact: true 
        };
      } else {
        // 常规双线性插值情况
        const Q11 = getConditionId(wsBounds.lower, wdBounds.lower);
        const Q12 = getConditionId(wsBounds.lower, wdBounds.upper);
        const Q21 = getConditionId(wsBounds.upper, wdBounds.lower);
        const Q22 = getConditionId(wsBounds.upper, wdBounds.upper);
        
        if (!Q11 || !Q12 || !Q21 || !Q22) {
          ElMessage.warning("数据网格不完整，缺少必要的角点数据，无法进行插值");
          return null;
        }
        
        return { Q11, Q12, Q21, Q22, wsBounds, wdBounds };
      }
    },
    
    linearInterpolate(p1, p2, x) {
      const [x1, y1] = p1;
      const [x2, y2] = p2;
      
      // 处理边界情况，避免除零错误
      if (Math.abs(x2 - x1) < 1e-10) {
        return y1; // 如果两点x坐标相同，返回y1
      }
      
      return y1 + (y2 - y1) * (x - x1) / (x2 - x1);
    },
    
    async runSimulation() {
      this.loadingSimulation = true;
      this.simulationResults = [];

      const surrounding = this.findSurroundingConditions();
      if (!surrounding) {
        this.loadingSimulation = false;
        return;
      }
      
      const { Q11, Q12, Q21, Q22, wsBounds, wdBounds, isExactMatch, isWindSpeedExact, isWindDirectionExact } = surrounding;

      try {
        // 获取所有需要的读数数据
        const uniqueConditions = [...new Set([Q11, Q12, Q21, Q22].map(q => q.condition_id))];
        const readingPromises = uniqueConditions.map(conditionId => 
          axios.get(`${API_BASE_URL}/physical_simulation/readings?condition_id=${conditionId}`)
        );
        const readingResponses = await Promise.all(readingPromises);
        
        // 创建条件ID到读数数据的映射
        const readingsMap = {};
        uniqueConditions.forEach((conditionId, index) => {
          readingsMap[conditionId] = readingResponses[index].data;
        });

        const results = this.farmTurbines.map(turbine => {
          const getReadingForTurbine = (conditionId, turbineId) => 
            readingsMap[conditionId].find(r => r.turbine_id === turbineId);

          const tQ11 = getReadingForTurbine(Q11.condition_id, turbine.turbine_id);
          const tQ12 = getReadingForTurbine(Q12.condition_id, turbine.turbine_id);
          const tQ21 = getReadingForTurbine(Q21.condition_id, turbine.turbine_id);
          const tQ22 = getReadingForTurbine(Q22.condition_id, turbine.turbine_id);

          if (!tQ11 || !tQ12 || !tQ21 || !tQ22) {
            return null;
          }

          let final_ws, final_power;

          if (isExactMatch) {
            // 精确匹配，直接使用数据
            final_ws = tQ11.turbine_wind_speed;
            final_power = tQ11.power_output || 0;
          } else if (isWindSpeedExact) {
            // 只在风向上插值
            final_ws = this.linearInterpolate(
              [wdBounds.lower, tQ11.turbine_wind_speed], 
              [wdBounds.upper, tQ12.turbine_wind_speed], 
              this.targetWindDirection
            );
            final_power = this.linearInterpolate(
              [wdBounds.lower, tQ11.power_output || 0], 
              [wdBounds.upper, tQ12.power_output || 0], 
              this.targetWindDirection
            );
          } else if (isWindDirectionExact) {
            // 只在风速上插值
            final_ws = this.linearInterpolate(
              [wsBounds.lower, tQ11.turbine_wind_speed], 
              [wsBounds.upper, tQ21.turbine_wind_speed], 
              this.targetWindSpeed
            );
            final_power = this.linearInterpolate(
              [wsBounds.lower, tQ11.power_output || 0], 
              [wsBounds.upper, tQ21.power_output || 0], 
              this.targetWindSpeed
            );
          } else {
            // 双线性插值计算风速
            const r1_ws = this.linearInterpolate([wsBounds.lower, tQ11.turbine_wind_speed], [wsBounds.upper, tQ21.turbine_wind_speed], this.targetWindSpeed);
            const r2_ws = this.linearInterpolate([wsBounds.lower, tQ12.turbine_wind_speed], [wsBounds.upper, tQ22.turbine_wind_speed], this.targetWindSpeed);
            final_ws = this.linearInterpolate([wdBounds.lower, r1_ws], [wdBounds.upper, r2_ws], this.targetWindDirection);

            // 双线性插值计算功率
            const r1_power = this.linearInterpolate([wsBounds.lower, tQ11.power_output || 0], [wsBounds.upper, tQ21.power_output || 0], this.targetWindSpeed);
            const r2_power = this.linearInterpolate([wsBounds.lower, tQ12.power_output || 0], [wsBounds.upper, tQ22.power_output || 0], this.targetWindSpeed);
            final_power = this.linearInterpolate([wdBounds.lower, r1_power], [wdBounds.upper, r2_power], this.targetWindDirection);
          }

          return {
            ...turbine,
            simulated_wind_speed: final_ws.toFixed(3),
            simulated_power_output: final_power.toFixed(3),
          };
        }).filter(Boolean);

        this.simulationResults = results;
        this.drawPlot();
        
        ElMessage.success(`仿真计算完成，共计算 ${results.length} 台风机数据`);

      } catch (error) {
        console.error("Error during simulation:", error);
        ElMessage.error("仿真计算过程中发生错误");
      } finally {
        this.loadingSimulation = false;
      }
    },
    
    drawPlot() {
      this.$nextTick(() => {
        this.$nextTick(() => {
          // 确保DOM元素存在
          if (!this.$refs.plot) {
            console.error('Plot element not found');
            // 如果元素不存在，稍后重试
            setTimeout(() => this.drawPlot(), 100);
            return;
          }

          const trace = {
            x: this.simulationResults.map(r => r.longitude),
            y: this.simulationResults.map(r => r.latitude),
            text: this.simulationResults.map(r => `风机: ${r.turbine_number}<br>风速: ${r.simulated_wind_speed} m/s<br>功率: ${r.simulated_power_output} kW`),
            mode: 'markers',
            marker: {
              size: 15,
              color: this.simulationResults.map(r => parseFloat(r.simulated_wind_speed)),
              colorscale: 'Viridis',
              showscale: true,
              colorbar: {
                title: '仿真风速 (m/s)'
              }
            },
            type: 'scatter'
          };

          const layout = {
            title: `${this.selectedFarm} - 仿真结果分布图`,
            xaxis: { title: '经度' },
            yaxis: { title: '纬度', scaleanchor: "x", scaleratio: 1 },
            hovermode: 'closest',
            margin: { t: 50, l: 50, r: 50, b: 50 }
          };

          try {
            Plotly.newPlot(this.$refs.plot, [trace], layout, {responsive: true});
          } catch (error) {
            console.error('Error creating plot:', error);
            ElMessage.error('图表绘制失败');
          }
        });
      });
    },
    
    exportResults() {
      if (this.simulationResults.length === 0) {
        ElMessage.warning('暂无数据可导出');
        return;
      }
      
      // CSV导出功能，添加BOM以解决中文乱码问题
      const headers = ['风机编号', '经度', '纬度', '仿真风速(m/s)', '仿真功率(kW)'];
      const csvContent = [
        headers.join(','),
        ...this.simulationResults.map(row => [
          row.turbine_number,
          row.longitude,
          row.latitude,
          row.simulated_wind_speed,
          row.simulated_power_output
        ].join(','))
      ].join('\n');
      
      // 添加UTF-8 BOM标记以确保中文正确显示
      const BOM = '\uFEFF';
      const csvWithBOM = BOM + csvContent;
      
      const blob = new Blob([csvWithBOM], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${this.selectedFarm}_仿真结果_${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      
      ElMessage.success('数据导出成功');
    }
  },
};
</script>

<style scoped>
.physical-simulation-container {
  min-height: 100vh;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
  position: relative;
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

.content-wrapper {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px 24px;
  position: relative;
  z-index: 1;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: white;
  margin: 0 0 8px 0;
  text-align: center;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.page-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  text-align: center;
  margin-bottom: 40px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 350px;
  gap: 32px;
  margin-bottom: 40px;
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.upload-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  overflow: hidden;
  transition: all 0.3s ease;
}

.upload-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.card-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
}

.card-content {
  padding: 24px;
}

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.action-card, .status-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  overflow: hidden;
}

.empty-action-panel {
  padding: 40px 24px;
  text-align: center;
  color: #666;
}

.empty-icon {
  font-size: 48px;
  color: #ddd;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 14px;
  line-height: 1.5;
  margin: 0;
}

.action-buttons {
  padding: 24px;
}

.action-button {
  width: 100%;
  height: 48px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.predict-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.predict-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
}

.status-card h3 {
  padding: 20px 24px;
  margin: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 16px;
  font-weight: 600;
}

.param-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.param-item:last-child {
  border-bottom: none;
}

.param-label {
  color: #666;
  font-weight: 500;
}

.param-value {
  color: #333;
  font-weight: 600;
}

.visualization-section {
  margin-top: 40px;
}

.visualization-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-title {
  font-size: 24px;
  font-weight: 700;
  color: white;
  margin: 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.results-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.chart-card, .table-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  overflow: hidden;
}

.chart-card .card-header, .table-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.chart-card .card-header h3, .table-card .card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.chart-container, .table-container {
  padding: 24px;
}

.table-container {
  padding: 24px 24px 0 24px; /* 减少底部padding，为表格留出更多空间 */
}

.chart-container {
  height: 548px; /* 500px图表 + 48px padding */
}

.table-container {
  height: 548px; /* 与图表容器保持相同高度 */
  display: flex;
  flex-direction: column;
}

.table-container .el-table {
  flex: 1;
  overflow: hidden;
}

@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  
  .results-container {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .content-wrapper {
    padding: 20px 16px;
  }
  
  .page-title {
    font-size: 24px;
  }
  
  .card-content {
    padding: 16px;
  }
}
</style> 