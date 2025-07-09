<!-- src/components/GetDailyMetrics.vue -->
 <template>
  <div>
    <el-button @click="fetchDailyMetrics" v-if="fileId && !processing && downloadUrl" type ="success">图表展示</el-button>
    <div v-if="chartData && downloadUrl" class="charts-container">
      <div v-for="(chart, index) in chartData" :key="index" class="chart-container">
        <canvas :id="'chart' + index"></canvas>
      </div>
    </div>
  </div>
</template>

<script>
import Papa from 'papaparse';
import axios from 'axios';
import { Chart, CategoryScale, LinearScale, LineElement, PointElement, Title, Tooltip, Legend, LineController } from 'chart.js';
// 注册所需的组件，包括 LineController
Chart.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  LineController  // 注册 LineController
);
export default {
  name: 'GetDailyMetrics',
  data() {
    return {
      dailyMetrics: null,  // 用于存储获取到的日常指标数据
      chartData: null,  // 用于存储可视化的图表数据
    }
  },
  props: {
    fileId: {
      type: String,
      required: true,
    },
    processing: {
      type: Boolean,
      default: false
    },
    downloadUrl: {
      type: String,
      default: ''
    },
    backendBaseUrl: {
      type: String,
    },
  },
  methods:{
    // 获取 daily-metrics.csv 数据
    fetchDailyMetrics() {
      if (!this.fileId) {
        this.$message.error('请先上传文件！');
        return;
      }

      axios
        .get(`${this.backendBaseUrl}/get-daily-metrics?file_id=${this.fileId}`)
        .then(response => {
          console.log('Response data:', response.data);  // 打印返回的数据，查看是否为 CSV 格式
          if (!response.data) {
            this.$message.error('未获取到日常指标数据');
            return;
          }

          Papa.parse(response.data, {
            complete: (result) => {
              console.log('Parsed result:', result); // 查看解析后的数据
              if (result.errors.length > 0) {
                this.$message.error('CSV 解析失败');
                console.error(result.errors);
                return;
              }
              this.processChartData(result.data);
            }
          });
        })
        .catch(error => {
          this.$message.error(`获取日常指标失败：${error.message}`);
          console.error('Error fetching daily metrics:', error);
        });
    },
    
    processChartData(data) {
      if (!data || data.length === 0) {
        this.$message.error('CSV 数据格式错误，请检查文件内容');
        return;
      }

      const labels = [];  // 日期列表
      const maeValues = [];  // MAE 数值列表
      const mseValues = [];  // MSE 数值列表
      const rmseValues = []; // RMSE 数值列表
      const accValues = [];  // ACC 数值列表
      const kValues = [];    // K 数值列表
      const peValues = [];    // pe 数值列表
      const dataRows = data.slice(1); // 跳过标题行，从第二行开始处理

      dataRows.forEach(item => {
        const rawDate = item[0]; // 原始日期字符串
        const date = new Date(rawDate);  // 转换为 Date 对象
        if (isNaN(date.getTime())) {  // 如果日期无效，跳过该行
          console.warn('Skipping invalid date:', rawDate);
          return;
        }

        // 格式化日期为 `YYYYMMDD`
        const formattedDate = date.toISOString().slice(0, 10).replace(/-/g, '/');
        labels.push(formattedDate);

        const mae = parseFloat(item[1]);
        const mse = parseFloat(item[2]);
        const rmse = parseFloat(item[3]);
        const acc = parseFloat(item[4]);
        const k = parseFloat(item[5]);
        const pe = parseFloat(item[6]);
        if (isNaN(mae) || isNaN(mse) || isNaN(rmse) || isNaN(acc) || isNaN(k)|| isNaN(pe)) {
          console.warn('Skipping row with invalid values:', item);
          return;
        }

        maeValues.push(mae);
        mseValues.push(mse);
        rmseValues.push(rmse);
        accValues.push(acc);
        kValues.push(k);
        peValues.push(pe);
      });

      if (labels.length === 0 || maeValues.length === 0) {
        this.$message.error('无效的数据，无法绘制图表');
        return;
      }

      this.chartData = [
        { label: '平均绝对误差 MAE', data: maeValues, borderColor: '#4caf50', backgroundColor: 'rgba(76, 175, 80, 0.2)', fill: true },
        { label: '均方误差 MSE', data: mseValues, borderColor: '#ff5722', backgroundColor: 'rgba(255, 87, 34, 0.2)', fill: true },
        { label: '均方根误差 RMSE', data: rmseValues, borderColor: '#2196f3', backgroundColor: 'rgba(33, 150, 243, 0.2)', fill: true },
        { label: '预测精度 ACC', data: accValues, borderColor: '#ff9800', backgroundColor: 'rgba(255, 152, 0, 0.2)', fill: true },
        { label: '预测精度 K', data: kValues, borderColor: '#9c27b0', backgroundColor: 'rgba(156, 39, 176, 0.2)', fill: true },
        { label: '日均考核电量 Pe', data: peValues, borderColor: '#00bcd4', backgroundColor: 'rgba(0, 188, 212, 0.2)', fill: true },
      ];

      this.renderCharts(labels);
    },
    
    renderCharts(labels) {
      console.log('Rendering charts with labels:', labels);  // 查看传入的 labels

      this.$nextTick(() => {
        this.chartData.forEach((dataset, index) => {
          const canvasId = `chart${index}`;
          const canvasElement = document.getElementById(canvasId);

          if (canvasElement) {
            // 销毁已存在的图表实例
            if (canvasElement.chart) {
              canvasElement.chart.destroy();
            }

            const ctx = canvasElement.getContext('2d');
            console.log('Rendering chart with dataset:', dataset);  // 查看 dataset
            canvasElement.chart = new Chart(ctx, {
              type: 'line',
              data: {
                labels: labels,  // x 轴标签
                datasets: [dataset],  // 数据集
              },
              options: {
                responsive: true,
                scales: {
                  x: {
                    type: 'category',
                    title: {
                      display: false,
                      text: '日期',
                    },
                  },
                  y: {
                    type: 'linear',
                    title: {
                      display: false,
                      text: dataset.label,
                    },
                  },
                },
              },
            });
          } else {
            console.error(`Canvas element with id ${canvasId} not found`);
          }
        });
      });
    }
  },
}
</script>

<style scoped>
.metrics-card {
  border: 4px solid #ebeef5;
  padding: 20px;
  max-height: 300px;
  overflow-y: auto;
}
.metrics-content {
  background-color: #f5f5f5;
  padding: 10px;
  height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  font-family: monospace;
}
.charts-container {
  display: flex;
  justify-content: space-around;
  flex-wrap: wrap;
  gap: 20px;
}
.chart-container {
  width: 45%;
}
</style>