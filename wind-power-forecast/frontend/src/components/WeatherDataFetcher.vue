<template>
  <div class="weather-data-fetcher page-shell">
    <!-- 动态渐变背景 -->
    <div class="gradient-background"></div>
    
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">气象预报数据拉取</h1>
      <p class="page-description">配置SSH连接，实现气象预报数据的定时拉取、处理和上传</p>
    </div>
    <div class="meta-updated">调度器更新时间：{{ schedulerCheckedAt || '--' }}</div>

    <el-card class="flow-card" shadow="hover">
      <div class="flow-title">数据流程</div>
      <div class="flow-steps">
        <div
          v-for="(step, index) in pipelineSteps"
          :key="step.key"
          class="flow-step"
          :class="`is-${step.status}`"
        >
          <div class="flow-dot"></div>
          <div class="flow-name">{{ step.name }}</div>
          <div class="flow-state">{{ step.text }}</div>
          <div v-if="index < pipelineSteps.length - 1" class="flow-link"></div>
        </div>
      </div>
    </el-card>

    <!-- SSH连接配置卡片 -->
    <el-card class="config-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon class="card-icon"><Connection /></el-icon>
          <span class="card-title">SSH连接配置</span>
          <el-button 
            type="primary" 
            size="small" 
            @click="showConnectionDialog = true"
          >
            添加连接
          </el-button>
        </div>
      </template>
      
      <div class="connection-list">
        <el-table 
          :data="connections" 
          style="width: 100%"
          v-loading="loadingConnections"
        >
          <el-table-column prop="name" label="连接名称" header-align="center" align="center"/>
          <el-table-column prop="host" label="服务器地址" header-align="center" align="center"/>
          <el-table-column prop="port" label="端口" max-width="120" header-align="center" align="center"/>
          <el-table-column prop="username" label="用户名" header-align="center" align="center"/>
          <el-table-column prop="auth_type" label="认证方式" max-width="120" header-align="center" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.auth_type === 'password' ? 'primary' : 'success'">
                {{ scope.row.auth_type === 'password' ? '密码' : '密钥' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" max-width="120" header-align="center" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.status === 'connected' ? 'success' : 'danger'">
                {{ scope.row.status === 'connected' ? '已连接' : '断开' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" max-width="280" header-align="center" align="center">
            <template #default="scope">
              <div class="button-group">
                <el-button 
                  size="small" 
                  type="info"
                  @click="testConnection(scope.row)"
                  :loading="scope.row.testing"
                >
                  测试连接
                </el-button>
                <el-button 
                  size="small" 
                  type="primary" 
                  @click="editConnection(scope.row)"
                >
                  编辑
                </el-button>
                <el-button 
                  size="small" 
                  type="danger" 
                  @click="deleteConnection(scope.row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- 调度器状态卡片 -->
    <el-card class="scheduler-card" shadow="hover" style="margin-top: 20px;">
      <template #header>
                          <div class="card-header">
           <div class="header-left">
             <el-icon class="card-icon"><Timer /></el-icon>
             <span class="card-title">调度器状态</span>
             <div class="header-status">
               <div class="status-item">
                 <span class="status-label">运行状态:</span>
                 <el-tag :type="schedulerInfo.is_running ? 'success' : 'danger'" size="small">
                   {{ schedulerInfo.is_running ? '运行中' : '已停止' }}
                 </el-tag>
               </div>
               <div class="status-item">
                 <span class="status-label">已调度任务:</span>
                 <el-tag type="primary" size="small">{{ schedulerInfo.total_jobs || 0 }} 个</el-tag>
               </div>
               <div class="status-item">
                 <span class="status-label">下次执行:</span>
                 <el-tag :type="nextRunCountdown === '--' ? 'info' : 'success'" size="small">
                   {{ nextRunCountdown }}
                 </el-tag>
               </div>
             </div>
           </div>
           <div class="scheduler-actions">
             <el-button 
               type="info" 
               size="small" 
               @click="checkSchedulerStatus"
               :loading="checkingScheduler"
             >
               检查状态
             </el-button>
             <el-button 
               type="warning" 
               size="small" 
               @click="restartScheduler"
               :loading="restartingScheduler"
             >
               重启调度器
             </el-button>
           </div>
         </div>
       </template>
       
              <div v-if="schedulerInfo.jobs && schedulerInfo.jobs.length > 0" class="scheduled-jobs">
         <div class="jobs-title">已调度的任务:</div>
         <div class="jobs-list">
           <div v-for="job in schedulerInfo.jobs" :key="job.id" class="job-item">
             <span class="job-name">{{ job.name }}</span>
             <span class="job-next-run">下次执行: {{ formatNextRunTime(job.next_run_time) }}</span>
           </div>
         </div>
       </div>
    </el-card>

    <!-- 数据拉取任务卡片 -->
    <el-card class="task-card" shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <el-icon class="card-icon"><Download /></el-icon>
          <span class="card-title">数据拉取任务</span>
          <el-button 
            type="primary" 
            size="small" 
            @click="showTaskDialog = true"
          >
            创建任务
          </el-button>
        </div>
      </template>
      
      <div class="task-list">
        <el-table 
          :data="tasks" 
          style="width: 100%"
          v-loading="loadingTasks"
        >
          <el-table-column prop="name" label="任务名称" max-width="70" header-align="center" align="center"/>
          <el-table-column prop="connection_name" label="连接" max-width="70" header-align="center" align="center"/>
          <el-table-column prop="schedule" label="执行频率" max-width="70" header-align="center" align="center">
            <template #default="scope">
              {{ getScheduleDescription(scope.row.schedule) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" max-width="70" header-align="center" align="center">
            <template #default="scope">
              <el-tag :type="getTaskStatusType(scope.row.status, scope.row.enabled)">
                {{ getTaskStatusText(scope.row.status, scope.row.enabled) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_run" label="最后执行" max-width="120" header-align="center" align="center"/>
          <el-table-column label="操作" max-width="280" fixed="right" header-align="center" align="center">
            <template #default="scope">
              <div class="action-buttons-container">
                <el-button 
                  size="mini" 
                  type="info"
                  @click="runTask(scope.row)"
                  :loading="scope.row.running"
                  class="action-btn-mini"
                >
                  立即执行
                </el-button>
                <el-button 
                  size="mini" 
                  type="primary"
                  @click="viewTaskLogs(scope.row)"
                  class="action-btn-mini"
                >
                  查看日志
                </el-button>
                <el-button 
                  size="mini" 
                  :type="scope.row.enabled ? 'warning' : 'success'"
                  @click="toggleTask(scope.row)"
                  class="action-btn-mini"
                >
                  {{ scope.row.enabled ? '停用' : '启用' }}
                </el-button>
                <el-button 
                  size="mini" 
                  type="primary" 
                  @click="editTask(scope.row)"
                  class="action-btn-mini"
                >
                  编辑
                </el-button>
                <el-button 
                  size="mini" 
                  type="danger" 
                  @click="deleteTask(scope.row)"
                  class="action-btn-mini"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- SSH连接配置对话框 -->
    <el-dialog 
      v-model="showConnectionDialog" 
      :title="editingConnection ? '编辑SSH连接' : '添加SSH连接'"
      width="600px"
    >
      <el-form 
        :model="connectionForm" 
        :rules="connectionRules"
        ref="connectionFormRef"
        label-width="120px"
      >
        <el-form-item label="连接名称" prop="name">
          <el-input v-model="connectionForm.name" placeholder="给连接起个名字" />
        </el-form-item>
        <el-form-item label="服务器地址" prop="host">
          <el-input v-model="connectionForm.host" placeholder="IP地址或域名" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="connectionForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="connectionForm.username" placeholder="SSH用户名" />
        </el-form-item>
        <el-form-item label="认证方式" prop="auth_type">
          <el-radio-group v-model="connectionForm.auth_type">
            <el-radio value="password">密码认证</el-radio>
            <el-radio value="key">密钥认证</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item 
          v-if="connectionForm.auth_type === 'password'" 
          label="密码" 
          prop="password"
        >
          <el-input 
            v-model="connectionForm.password" 
            type="password" 
            show-password 
            placeholder="SSH密码"
          />
        </el-form-item>
        <el-form-item 
          v-if="connectionForm.auth_type === 'key'" 
          label="私钥路径" 
          prop="private_key_path"
        >
          <div class="file-input-group">
            <el-input 
              v-model="connectionForm.private_key_path" 
              placeholder="服务器上的私钥文件路径，或点击右侧按钮选择本地文件"
            />
            <el-button type="primary" @click="selectPrivateKeyFile">
              <el-icon><Folder /></el-icon>
              选择文件
            </el-button>
            <input 
              ref="fileInput"
              type="file" 
              style="display: none"
              accept=".pem,.key,.ppk,*"
              @change="handleFileSelect"
            />
          </div>
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 可输入服务器上的私钥文件绝对路径（如：/home/user/.ssh/id_rsa），或选择本地私钥文件上传
            </el-text>
          </div>
        </el-form-item>
        <el-form-item 
          v-if="connectionForm.auth_type === 'key'" 
          label="私钥密码" 
          prop="key_passphrase"
        >
          <el-input 
            v-model="connectionForm.key_passphrase" 
            type="password" 
            show-password 
            placeholder="私钥密码（如有）"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showConnectionDialog = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="saveConnection"
            :loading="savingConnection"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 数据拉取任务配置对话框 -->
    <el-dialog 
      v-model="showTaskDialog" 
      :title="editingTask ? '编辑拉取任务' : '创建拉取任务'"
      width="800px"
    >
      <el-form 
        :model="taskForm" 
        :rules="taskRules"
        ref="taskFormRef"
        label-width="140px"
      >
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="taskForm.name" placeholder="任务名称" />
        </el-form-item>
        <el-form-item label="SSH连接" prop="connection_id">
          <el-select v-model="taskForm.connection_id" placeholder="选择SSH连接">
            <el-option 
              v-for="conn in connections" 
              :key="conn.id"
              :label="conn.name"
              :value="conn.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="远程路径" prop="remote_path">
          <el-input v-model="taskForm.remote_path" placeholder="/ECMWF/processed_csv/" />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 基础路径，程序会自动搜索其下的时间文件夹
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="路径模式" prop="path_pattern">
          <el-select v-model="taskForm.path_pattern" placeholder="选择时间文件夹模式">
            <el-option label="YYYY_MMDDHHNN (如: 2025_07011800)" value="YYYY_MMDDHHNN" />
            <el-option label="YYYY-MM-DD/HH (如: 2025-07-01/18)" value="YYYY-MM-DD/HH" />
            <el-option label="YYYYMMDDHH (如: 2025070118)" value="YYYYMMDDHH" />
            <el-option label="YYYY/MM/DD/HH (如: 2025/07/01/18)" value="YYYY/MM/DD/HH" />
            <el-option label="自定义模式" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item 
          v-if="taskForm.path_pattern === 'custom'" 
          label="自定义模式" 
          prop="custom_path_pattern"
        >
          <el-input 
            v-model="taskForm.custom_path_pattern" 
            placeholder="YYYY_MMDDHHNN"
          />
          <div class="form-tip">
            <el-text type="info" size="small">
              📝 支持变量: YYYY(年) MM(月) DD(日) HH(时) NN(分) SS(秒)
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="时间选择策略" prop="time_strategy">
          <el-radio-group v-model="taskForm.time_strategy">
            <el-radio value="latest">最新数据</el-radio>
            <el-radio value="specific">指定时间</el-radio>
            <el-radio value="range">时间范围</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item 
          v-if="taskForm.time_strategy === 'specific'" 
          label="指定时间" 
          prop="specific_time"
        >
          <el-date-picker
            v-model="taskForm.specific_time"
            type="datetime"
            placeholder="选择具体时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item 
          v-if="taskForm.time_strategy === 'range'" 
          label="时间范围" 
          prop="time_range"
        >
          <el-date-picker
            v-model="taskForm.time_range"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="可用时间目录">
          <el-button 
            type="info" 
            size="small" 
            @click="checkAvailableDirectories"
            :loading="checkingDirectories"
            :disabled="!taskForm.connection_id || !taskForm.remote_path"
          >
            检查可用目录
          </el-button>
          <div v-if="availableDirectories.length > 0" class="available-dirs">
            <el-tag 
              v-for="dir in showAllDirectories ? availableDirectories : availableDirectories.slice(0, 4)" 
              :key="dir.name"
              size="small"
              style="margin: 2px;"
            >
              {{ dir.name }}
            </el-tag>
            <span v-if="availableDirectories.length > 4" class="more-dirs">
              <el-button 
                v-if="!showAllDirectories"
                type="primary" 
                link 
                size="small"
                @click="showAllDirectories = true"
              >
                ...等{{ availableDirectories.length - 4 }}个 (点击展开)
              </el-button>
              <el-button 
                v-else
                type="primary" 
                link 
                size="small"
                @click="showAllDirectories = false"
              >
                收起
              </el-button>
            </span>
          </div>
        </el-form-item>
        <el-form-item label="文件名模式" prop="file_pattern">
          <el-input v-model="taskForm.file_pattern" placeholder="*.nc, *.grib, *.txt等" />
        </el-form-item>
        <el-form-item label="执行频率" prop="schedule">
          <el-select v-model="taskForm.schedule" placeholder="选择执行频率">
            <el-option label="每小时" value="0 * * * *" />
            <el-option label="每6小时" value="0 */6 * * *" />
            <el-option label="每12小时" value="0 */12 * * *" />
            <el-option label="每天" value="0 0 * * *" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item 
          v-if="taskForm.schedule === 'custom'" 
          label="Cron表达式" 
          prop="custom_schedule"
        >
          <el-input v-model="taskForm.custom_schedule" placeholder="0 0 * * *" />
        </el-form-item>
        <el-form-item label="数据处理">
          <el-checkbox-group v-model="taskForm.processing_options">
            <el-checkbox value="integrity_check">数据完整性校验</el-checkbox>
            <el-checkbox value="interpolation">数据订正</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="去重设置">
          <el-checkbox-group v-model="taskForm.deduplication_options">
            <el-checkbox value="skip_existing" checked>跳过已存在文件</el-checkbox>
            <el-checkbox value="check_size">验证文件大小</el-checkbox>
            <el-checkbox value="check_mtime">检查修改时间</el-checkbox>
            <el-checkbox value="force_reprocess">强制重新处理</el-checkbox>
          </el-checkbox-group>
          <div class="form-tip">
            <el-text type="info" size="small">
              🔄 智能去重：避免重复下载相同文件，提高拉取效率
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="保存路径" prop="save_path">
          <el-input 
            v-model="taskForm.save_path" 
            placeholder="气象数据本地保存路径"
          />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 Windows示例: D:\weather_data\  Linux示例: /data/weather/  
              支持变量: {date} 自动替换为日期
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="超时时间(秒)" prop="timeout">
          <el-input-number v-model="taskForm.timeout" :min="30" :max="3600" />
        </el-form-item>
        <el-form-item label="重试次数" prop="retry_count">
          <el-input-number v-model="taskForm.retry_count" :min="0" :max="5" />
        </el-form-item>
        <el-form-item label="任务描述" prop="description">
          <el-input 
            v-model="taskForm.description" 
            type="textarea" 
            :rows="3"
            placeholder="任务说明"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showTaskDialog = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="saveTask"
            :loading="savingTask"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 任务日志查看对话框 -->
    <el-dialog 
      v-model="showLogsDialog" 
      title="任务执行日志"
      width="1000px"
      :close-on-click-modal="false"
    >
      <div class="logs-header">
        <div class="logs-title">
          <strong>{{ currentTaskName }}</strong> 的执行日志
        </div>
        <div class="logs-filters">
          <el-select v-model="logLevel" @change="fetchTaskLogs" size="small" style="width: 120px;">
            <el-option label="全部" value="" />
            <el-option label="信息" value="info" />
            <el-option label="成功" value="success" />
            <el-option label="警告" value="warning" />
            <el-option label="错误" value="error" />
          </el-select>
          <el-button 
            size="small" 
            type="primary" 
            @click="fetchTaskLogs"
            :loading="loadingLogs"
          >
            刷新
          </el-button>
        </div>
      </div>
      
      <div class="logs-content" v-loading="loadingLogs">
        <div v-if="taskLogs.length === 0" class="no-logs">
          <el-empty description="暂无日志记录" />
        </div>
        <div v-else class="logs-list">
          <div 
            v-for="log in taskLogs" 
            :key="log.id"
            :class="['log-item', `log-${log.level}`]"
          >
            <div class="log-header">
              <el-tag 
                :type="getLogLevelType(log.level)" 
                size="small"
              >
                {{ getLogLevelText(log.level) }}
              </el-tag>
              <span class="log-time">{{ formatLogTime(log.created_at) }}</span>
            </div>
            <div class="log-message">{{ log.message }}</div>
            <div v-if="log.details" class="log-details">{{ log.details }}</div>
          </div>
        </div>
      </div>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showLogsDialog = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getWeatherConnections,
  getWeatherTasks,
  createWeatherConnection,
  updateWeatherConnection,
  testWeatherConnection,
  deleteWeatherConnection,
  runWeatherTask,
  toggleWeatherTask,
  createWeatherTask,
  updateWeatherTask,
  deleteWeatherTask,
  checkWeatherDirectories,
  getWeatherTaskLogs,
  getWeatherSchedulerStatus,
  restartWeatherScheduler
} from '../api/weatherFetchApi'
import {
  Connection,
  Download,
  Folder,
  Timer
} from '@element-plus/icons-vue'

export default {
  name: 'WeatherDataFetcher',
  components: {
    Connection,
    Download,
    Folder,
    Timer
  },
  setup() {
    // 响应式数据
    const connections = ref([])
    const tasks = ref([])
    const availableDirectories = ref([])
    const showAllDirectories = ref(false)
    const taskLogs = ref([])
    const currentTaskId = ref(null)
    const currentTaskName = ref('')
    const logLevel = ref('')
    const schedulerInfo = ref({
      is_running: false,
      jobs: [],
      total_jobs: 0
    })
    const schedulerCheckedAt = ref('')
    const nowTs = ref(Date.now())
    let countdownTimer = null

    const pipelineSteps = computed(() => {
      const hasConnection = connections.value.length > 0
      const connected = connections.value.some(item => item.status === 'connected')
      const schedulerRunning = !!schedulerInfo.value?.is_running
      const enabledTasks = tasks.value.filter(item => item.enabled)
      const runningTask = tasks.value.some(item => item.running || item.status === 'running')

      return [
        {
          key: 'source',
          name: '气象数据源',
          status: hasConnection ? 'ready' : 'idle',
          text: hasConnection ? '已配置' : '待配置'
        },
        {
          key: 'connection',
          name: 'SSH 通道',
          status: connected ? 'ready' : (hasConnection ? 'warning' : 'idle'),
          text: connected ? '已连接' : (hasConnection ? '已断开' : '待配置')
        },
        {
          key: 'scheduler',
          name: '调度器',
          status: schedulerRunning ? 'ready' : 'warning',
          text: schedulerRunning ? '运行中' : '已停止'
        },
        {
          key: 'execution',
          name: '任务执行',
          status: runningTask ? 'ready' : (enabledTasks.length > 0 ? 'warning' : 'idle'),
          text: runningTask ? '运行中' : (enabledTasks.length > 0 ? '等待中' : '无任务')
        }
      ]
    })

    const nextRunTargetTs = computed(() => {
      const jobs = Array.isArray(schedulerInfo.value?.jobs) ? schedulerInfo.value.jobs : []
      const timestamps = jobs
        .map(job => new Date(job.next_run_time).getTime())
        .filter(ts => Number.isFinite(ts) && ts > nowTs.value)
      if (!timestamps.length) return null
      return Math.min(...timestamps)
    })

    const nextRunCountdown = computed(() => {
      if (!nextRunTargetTs.value) return '--'
      const diff = nextRunTargetTs.value - nowTs.value
      if (diff <= 0) return '00:00'
      const totalSeconds = Math.floor(diff / 1000)
      const hours = Math.floor(totalSeconds / 3600)
      const minutes = Math.floor((totalSeconds % 3600) / 60)
      const seconds = totalSeconds % 60
      return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    })
    
    // 加载状态
    const loadingConnections = ref(false)
    const loadingTasks = ref(false)
    const savingConnection = ref(false)
    const savingTask = ref(false)
    const checkingDirectories = ref(false)
    const loadingLogs = ref(false)
    const checkingScheduler = ref(false)
    const restartingScheduler = ref(false)
    
    // 对话框状态
    const showConnectionDialog = ref(false)
    const showTaskDialog = ref(false)
    const showLogsDialog = ref(false)
    const editingConnection = ref(false)
    const editingTask = ref(false)
    
    // 表单引用
    const connectionFormRef = ref(null)
    const taskFormRef = ref(null)
    const fileInput = ref(null)
    
    // 连接表单
    const connectionForm = reactive({
      id: null,
      name: '',
      host: '',
      port: 22,
      username: '',
      auth_type: 'password',
      password: '',
      private_key_path: '',
      private_key_content: '', // 存储私钥文件内容
      key_passphrase: ''
    })
    
    // 任务表单
    const taskForm = reactive({
      id: null,
      name: '',
      connection_id: '',
      remote_path: '/ECMWF/processed_csv/',
      path_pattern: 'YYYY_MMDDHHNN',
      custom_path_pattern: '',
      time_strategy: 'latest',
      specific_time: null,
      time_range: null,
      file_pattern: '*.csv',
      schedule: '0 */6 * * *',
      custom_schedule: '',
      processing_options: ['integrity_check'],
      deduplication_options: ['skip_existing'],
      save_path: navigator.userAgent.includes('Windows') ? 'D:\\weather_data\\{date}\\' : '/data/weather/{date}/',
      timeout: 300,
      retry_count: 3,
      description: ''
    })
    
    // 表单验证规则
    const connectionRules = {
      name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
      host: [{ required: true, message: '请输入服务器地址', trigger: 'blur' }],
      port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }]
    }
    
    const taskRules = {
      name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
      connection_id: [{ required: true, message: '请选择SSH连接', trigger: 'change' }],
      remote_path: [{ required: true, message: '请输入远程路径', trigger: 'blur' }],
      path_pattern: [{ required: true, message: '请选择路径模式', trigger: 'change' }],
      file_pattern: [{ required: true, message: '请输入文件名模式', trigger: 'blur' }],
      save_path: [{ required: true, message: '请输入保存路径', trigger: 'blur' }],
      specific_time: [
        { 
          validator: (rule, value, callback) => {
            if (taskForm.time_strategy === 'specific' && !value) {
              callback(new Error('请选择指定时间'))
            } else {
              callback()
            }
          }, 
          trigger: 'change' 
        }
      ],
      time_range: [
        { 
          validator: (rule, value, callback) => {
            if (taskForm.time_strategy === 'range' && (!value || !value[0] || !value[1])) {
              callback(new Error('请选择时间范围'))
            } else {
              callback()
            }
          }, 
          trigger: 'change' 
        }
      ]
    }
    
    // API方法
    const fetchConnections = async () => {
      loadingConnections.value = true
      try {
        const response = await getWeatherConnections()
        connections.value = response.data
      } catch (error) {
        console.error('获取连接列表失败:', error)
        ElMessage.error('获取连接列表失败')
      } finally {
        loadingConnections.value = false
      }
    }
    
    const fetchTasks = async () => {
      loadingTasks.value = true
      try {
        const response = await getWeatherTasks()
        tasks.value = response.data
      } catch (error) {
        console.error('获取任务列表失败:', error)
        ElMessage.error('获取任务列表失败')
      } finally {
        loadingTasks.value = false
      }
    }
    
    // 连接操作
    const testConnection = async (connection) => {
      connection.testing = true
      try {
        const response = await testWeatherConnection(connection.id)
        if (response.data.success) {
          ElMessage.success('连接测试成功')
          connection.status = 'connected'
        } else {
          ElMessage.error('连接测试失败')
          connection.status = 'disconnected'
        }
      } catch (error) {
        console.error('测试连接失败:', error)
        ElMessage.error('测试连接失败')
        connection.status = 'disconnected'
      } finally {
        connection.testing = false
      }
    }
    
    const editConnection = (connection) => {
      editingConnection.value = true
      Object.assign(connectionForm, {
        ...connection,
        private_key_content: '' // 编辑时清空本地文件内容，需要重新选择
      })
      showConnectionDialog.value = true
    }
    
    const deleteConnection = async (connection) => {
      try {
        await ElMessageBox.confirm('确定要删除这个SSH连接吗？', '确认删除', {
          type: 'warning'
        })
        
        await deleteWeatherConnection(connection.id)
        ElMessage.success('连接删除成功')
        fetchConnections()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除连接失败:', error)
          ElMessage.error('删除连接失败')
        }
      }
    }
    
    const saveConnection = async () => {
      if (!connectionFormRef.value) return
      
      try {
        await connectionFormRef.value.validate()
        savingConnection.value = true
        
        if (editingConnection.value) {
          await updateWeatherConnection(connectionForm.id, connectionForm)
        } else {
          await createWeatherConnection(connectionForm)
        }
        
        ElMessage.success(editingConnection.value ? '连接更新成功' : '连接添加成功')
        showConnectionDialog.value = false
        resetConnectionForm()
        fetchConnections()
      } catch (error) {
        console.error('保存连接失败:', error)
        ElMessage.error('保存连接失败')
      } finally {
        savingConnection.value = false
      }
    }
    
    const resetConnectionForm = () => {
      Object.assign(connectionForm, {
        id: null,
        name: '',
        host: '',
        port: 22,
        username: '',
        auth_type: 'password',
        password: '',
        private_key_path: '',
        private_key_content: '',
        key_passphrase: ''
      })
      editingConnection.value = false
    }
    
    // 任务操作
    const runTask = async (task) => {
      task.running = true
      try {
        await runWeatherTask(task.id)
        ElMessage.success('任务执行已启动')
        fetchTasks()
      } catch (error) {
        console.error('执行任务失败:', error)
        ElMessage.error('执行任务失败')
      } finally {
        task.running = false
      }
    }
    
    const toggleTask = async (task) => {
      try {
        await toggleWeatherTask(task.id)
        ElMessage.success(task.enabled ? '任务已停用' : '任务已启用')
        fetchTasks()
      } catch (error) {
        console.error('切换任务状态失败:', error)
        ElMessage.error('切换任务状态失败')
      }
    }
    
    const editTask = (task) => {
      editingTask.value = true
      
      // 处理时间范围字段
      let timeRange = null
      if (task.time_range_start && task.time_range_end) {
        timeRange = [task.time_range_start, task.time_range_end]
      }
      
      Object.assign(taskForm, {
        id: task.id,
        name: task.name,
        connection_id: task.connection_id,
        remote_path: task.remote_path,
        path_pattern: task.path_pattern || 'YYYY_MMDDHHNN',
        custom_path_pattern: task.custom_path_pattern || '',
        time_strategy: task.time_strategy || 'latest',
        specific_time: task.specific_time || null,
        time_range: timeRange,
        file_pattern: task.file_pattern,
        schedule: task.schedule,
        custom_schedule: task.schedule === 'custom' ? task.schedule : '',
        processing_options: task.processing_options || ['integrity_check'],
        deduplication_options: task.deduplication_options || ['skip_existing'],
        save_path: task.save_path || (navigator.userAgent.includes('Windows') ? 'D:\\weather_data\\{date}\\' : '/data/weather/{date}/'),
        timeout: task.timeout,
        retry_count: task.retry_count,
        description: task.description || ''
      })
      showTaskDialog.value = true
    }
    
    const deleteTask = async (task) => {
      try {
        await ElMessageBox.confirm('确定要删除这个拉取任务吗？', '确认删除', {
          type: 'warning'
        })
        
        await deleteWeatherTask(task.id)
        ElMessage.success('任务删除成功')
        fetchTasks()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除任务失败:', error)
          ElMessage.error('删除任务失败')
        }
      }
    }
    
    const saveTask = async () => {
      if (!taskFormRef.value) return
      
      try {
        await taskFormRef.value.validate()
        savingTask.value = true
        
        // 准备提交数据，确保时间格式正确
        const submitData = { ...taskForm }
        
        // 处理时间范围数据 - 如果不是range策略，删除time_range字段
        if (submitData.time_strategy !== 'range' || !submitData.time_range) {
          delete submitData.time_range
        }
        
        if (editingTask.value) {
          await updateWeatherTask(taskForm.id, submitData)
        } else {
          await createWeatherTask(submitData)
        }
        
        ElMessage.success(editingTask.value ? '任务更新成功' : '任务创建成功')
        showTaskDialog.value = false
        resetTaskForm()
        fetchTasks()
      } catch (error) {
        console.error('保存任务失败:', error)
        ElMessage.error('保存任务失败')
      } finally {
        savingTask.value = false
      }
    }
    
    const resetTaskForm = () => {
      // 根据操作系统设置默认保存路径
      const defaultSavePath = navigator.userAgent.includes('Windows') 
        ? 'D:\\weather_data\\{date}\\' 
        : '/data/weather/{date}/'
      
      Object.assign(taskForm, {
        id: null,
        name: '',
        connection_id: '',
        remote_path: '/ECMWF/processed_csv/',
        path_pattern: 'YYYY_MMDDHHNN',
        custom_path_pattern: '',
        time_strategy: 'latest',
        specific_time: null,
        time_range: null,
        file_pattern: '*.csv',
        schedule: '0 */6 * * *',
        custom_schedule: '',
        processing_options: ['integrity_check'],
        deduplication_options: ['skip_existing'],
        save_path: defaultSavePath,
        timeout: 300,
        retry_count: 3,
        description: ''
      })
      editingTask.value = false
    }
    
    // 辅助方法
    const getTaskStatusType = (status, enabled = true) => {
      const typeMap = {
        running: 'warning',
        success: 'success',
        error: 'danger',
        idle: enabled ? 'success' : 'info'  // 启用时的idle显示为success绿色
      }
      return typeMap[status] || 'info'
    }
    
    const getTaskStatusText = (status, enabled = true) => {
      const textMap = {
        running: '运行中',
        success: '成功',
        error: '失败',
        idle: enabled ? '等待中' : '已停用'  // 启用时显示"等待中"，未启用时显示"已停用"
      }
      return textMap[status] || status
    }
    
    // 检查可用时间目录
    const checkAvailableDirectories = async () => {
      if (!taskForm.connection_id || !taskForm.remote_path) {
        ElMessage.warning('请先选择SSH连接和设置远程路径')
        return
      }
      
      try {
        checkingDirectories.value = true
        const response = await checkWeatherDirectories({
          connection_id: taskForm.connection_id,
          base_path: taskForm.remote_path,
          path_pattern: taskForm.path_pattern || 'YYYY_MMDDHHNN',
          time_strategy: taskForm.time_strategy,
          specific_time: taskForm.specific_time,
          time_range_start: taskForm.time_range ? taskForm.time_range[0] : null,
          time_range_end: taskForm.time_range ? taskForm.time_range[1] : null,
          limit: 100  // 获取更多历史目录
        })
        
        availableDirectories.value = response.data.directories || []
        showAllDirectories.value = false // 重置展开状态
        
        if (availableDirectories.value.length > 0) {
          const strategyText = {
            'latest': '最新数据',
            'specific': '指定时间',
            'range': '时间范围'
          }[taskForm.time_strategy] || '时间策略'
          ElMessage.success(`根据${strategyText}筛选，找到 ${availableDirectories.value.length} 个时间目录`)
        } else {
          ElMessage.info('未找到匹配的时间目录，请检查时间设置或路径配置')
        }
        
      } catch (error) {
        console.error('检查目录失败:', error)
        ElMessage.error('检查目录失败')
        availableDirectories.value = []
      } finally {
        checkingDirectories.value = false
      }
    }
    
    // 文件选择方法
    const selectPrivateKeyFile = () => {
      if (fileInput.value) {
        fileInput.value.click()
      }
    }
    
    const handleFileSelect = (event) => {
      const file = event.target.files[0]
      if (file) {
        const reader = new FileReader()
        reader.onload = (e) => {
          // 将文件内容存储到表单中，而不是路径
          connectionForm.private_key_content = e.target.result
          connectionForm.private_key_path = file.name // 仅用于显示
          ElMessage.success(`已选择私钥文件: ${file.name}`)
        }
        reader.onerror = () => {
          ElMessage.error('文件读取失败')
        }
        reader.readAsText(file)
      }
      // 清空文件输入，允许重新选择同一文件
      event.target.value = ''
    }
    
    // 日志查看方法
    const viewTaskLogs = (task) => {
      currentTaskId.value = task.id
      currentTaskName.value = task.name
      showLogsDialog.value = true
      fetchTaskLogs()
    }
    
    const fetchTaskLogs = async () => {
      if (!currentTaskId.value) return
      
      loadingLogs.value = true
      try {
        const response = await getWeatherTaskLogs(currentTaskId.value, {
          level: logLevel.value || undefined,
          per_page: 100
        })
        taskLogs.value = response.data.logs || []
      } catch (error) {
        console.error('获取日志失败:', error)
        ElMessage.error('获取日志失败')
        taskLogs.value = []
      } finally {
        loadingLogs.value = false
      }
    }
    
    const getLogLevelType = (level) => {
      switch (level) {
        case 'success':
          return 'success'
        case 'warning':
          return 'warning'
        case 'error':
          return 'danger'
        case 'info':
        default:
          return 'info'
      }
    }
    
    const getLogLevelText = (level) => {
      switch (level) {
        case 'success':
          return '成功'
        case 'warning':
          return '警告'
        case 'error':
          return '错误'
        case 'info':
        default:
          return '信息'
      }
    }
    
    const formatLogTime = (timeStr) => {
      if (!timeStr) return ''
      try {
        const date = new Date(timeStr)
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })
      } catch {
        return timeStr
      }
    }

    const formatNow = () => {
      const now = new Date()
      const y = now.getFullYear()
      const m = String(now.getMonth() + 1).padStart(2, '0')
      const d = String(now.getDate()).padStart(2, '0')
      const hh = String(now.getHours()).padStart(2, '0')
      const mm = String(now.getMinutes()).padStart(2, '0')
      const ss = String(now.getSeconds()).padStart(2, '0')
      return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
    }
    
    // Cron表达式转换为用户友好的描述
    // 调度器管理方法
    const checkSchedulerStatus = async () => {
      checkingScheduler.value = true
      try {
        const response = await getWeatherSchedulerStatus()
        schedulerInfo.value = response.data
        schedulerCheckedAt.value = formatNow()
        ElMessage.success('调度器状态更新成功')
      } catch (error) {
        console.error('获取调度器状态失败:', error)
        ElMessage.error('获取调度器状态失败')
        schedulerInfo.value = {
          is_running: false,
          jobs: [],
          total_jobs: 0
        }
      } finally {
        checkingScheduler.value = false
      }
    }
    
    const restartScheduler = async () => {
      try {
        await ElMessageBox.confirm('确定要重启调度器吗？这将重新加载所有定时任务。', '确认重启', {
          type: 'warning'
        })
        
        restartingScheduler.value = true
        const response = await restartWeatherScheduler()
        schedulerInfo.value = response.data.status
        schedulerCheckedAt.value = formatNow()
        ElMessage.success('调度器重启成功')
        
        // 刷新任务列表
        fetchTasks()
        
      } catch (error) {
        if (error !== 'cancel') {
          console.error('重启调度器失败:', error)
          ElMessage.error('重启调度器失败')
        }
      } finally {
        restartingScheduler.value = false
      }
    }
    
    const formatNextRunTime = (timeStr) => {
      if (!timeStr) return '未知'
      try {
        const date = new Date(timeStr)
        return date.toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        })
      } catch {
        return timeStr
      }
    }

    const getScheduleDescription = (cronExpression) => {
      if (!cronExpression) return '-'
      
      // 常见的cron表达式映射
      const cronPatterns = {
        '0 * * * *': '每小时',        // 每小时的第0分钟
        '0 */6 * * *': '每6小时',
        '0 */4 * * *': '每4小时',
        '0 */3 * * *': '每3小时',
        '0 */2 * * *': '每2小时',
        '0 */1 * * *': '每小时',      // 另一种每小时的写法
        '*/30 * * * *': '每30分钟',
        '*/15 * * * *': '每15分钟',
        '*/10 * * * *': '每10分钟',
        '*/5 * * * *': '每5分钟',
        '0 0 * * *': '每天0点',
        '0 6 * * *': '每天6点',
        '0 12 * * *': '每天12点',
        '0 18 * * *': '每天18点',
        '0 0 */3 * *': '每3天',
        '0 0 * * 0': '每周日',
        '0 0 1 * *': '每月1号'
      }
      
      // 直接匹配
      if (cronPatterns[cronExpression]) {
        return cronPatterns[cronExpression]
      }
      
              // 简单解析cron表达式
        const parts = cronExpression.split(' ')
        if (parts.length >= 5) {
          const [minute, hour, day, month, dayOfWeek] = parts
          
          // 每X分钟
          if (minute.startsWith('*/') && hour === '*') {
            const interval = minute.slice(2)
            return `每${interval}分钟`
          }
          
          // 每小时（各种形式）
          if ((minute === '0' || minute.match(/^\d+$/)) && hour === '*' && day === '*' && month === '*' && dayOfWeek === '*') {
            if (minute === '0') {
              return '每小时'
            } else {
              return `每小时${minute}分`
            }
          }
          
          // 每X小时
          if (minute === '0' && hour.startsWith('*/')) {
            const interval = hour.slice(2)
            return `每${interval}小时`
          }
          
          // 每天固定时间
          if (hour !== '*' && minute !== '*' && day === '*' && month === '*' && dayOfWeek === '*') {
            return `每天${hour}:${minute.padStart(2, '0')}`
          }
        }
      
      // 无法解析时返回原表达式
      return cronExpression
    }

    // 生命周期
    onMounted(() => {
      countdownTimer = setInterval(() => {
        nowTs.value = Date.now()
      }, 1000)
      fetchConnections()
      fetchTasks()
      checkSchedulerStatus() // 检查调度器状态
    })

    onUnmounted(() => {
      if (countdownTimer) {
        clearInterval(countdownTimer)
        countdownTimer = null
      }
    })

    return {
      // 数据
      connections,
      tasks,
      availableDirectories,
      showAllDirectories,
      taskLogs,
      currentTaskId,
      currentTaskName,
      logLevel,
      schedulerInfo,
      schedulerCheckedAt,
      pipelineSteps,
      nextRunCountdown,
      // 加载状态
      loadingConnections,
      loadingTasks,
      savingConnection,
      savingTask,
      checkingDirectories,
      loadingLogs,
      checkingScheduler,
      restartingScheduler,
      // 对话框状态
      showConnectionDialog,
      showTaskDialog,
      showLogsDialog,
      editingConnection,
      editingTask,
      // 表单
      connectionForm,
      taskForm,
      connectionFormRef,
      taskFormRef,
      fileInput,
      connectionRules,
      taskRules,
      // 方法
      testConnection,
      editConnection,
      deleteConnection,
      saveConnection,
      resetConnectionForm,
      runTask,
      toggleTask,
      editTask,
      deleteTask,
      saveTask,
      resetTaskForm,
      getTaskStatusType,
      getTaskStatusText,
      checkAvailableDirectories,
      selectPrivateKeyFile,
      handleFileSelect,
      viewTaskLogs,
      fetchTaskLogs,
      getLogLevelType,
      getLogLevelText,
      formatLogTime,
      getScheduleDescription,
      // 调度器相关
      checkSchedulerStatus,
      restartScheduler,
      formatNextRunTime
    }
  }
}
</script>

<style scoped>
.weather-data-fetcher {
  position: relative;
  min-height: 100vh;
  padding: 20px;
  overflow: hidden;
}

/* 动态渐变背景 */
.gradient-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradientShift 15s ease infinite;
  z-index: -1;
}

@keyframes gradientShift {
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

/* 页面标题 */
.page-header {
  text-align: center;
  margin-bottom: 30px;
  color: white;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
  position: relative;
  z-index: 1;
}

.page-title {
  font-size: 42px;
  font-weight: 600;
  margin-bottom: 10px;
  letter-spacing: -0.003em;
  color: white;
  margin: 0 0 10px 0;
}

.page-description {
  font-size: 18px;
  opacity: 0.9;
  margin: 0;
  color: white;
}

.meta-updated {
  margin-bottom: 12px;
  color: var(--text-secondary);
  font-size: 12px;
  font-family: "Consolas", "Roboto Mono", monospace;
}

.flow-card {
  margin-bottom: 20px;
}

.flow-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.flow-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.flow-step {
  position: relative;
  border: 1px solid rgba(146, 186, 220, 0.25);
  border-radius: 12px;
  background: rgba(8, 24, 38, 0.58);
  min-height: 76px;
  padding: 10px 10px 10px 12px;
}

.flow-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-bottom: 8px;
}

.flow-name {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.flow-state {
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 4px;
}

.flow-link {
  position: absolute;
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 8px;
  height: 1px;
  background: rgba(146, 186, 220, 0.4);
}

.flow-step.is-ready .flow-dot {
  background: var(--accent-2);
  box-shadow: 0 0 8px rgba(45, 211, 111, 0.7);
}

.flow-step.is-warning .flow-dot {
  background: var(--warning);
  box-shadow: 0 0 8px rgba(246, 183, 60, 0.7);
}

.flow-step.is-idle .flow-dot {
  background: #7d90a5;
}

/* 卡片样式 */
:deep(.el-card) {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(15px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;
  transition: all 0.3s ease;
  position: relative;
  z-index: 1;
}

:deep(.el-card):hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
  background: rgba(255, 255, 255, 0.98);
}

:deep(.el-card__header) {
  padding: 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 20px 20px 0 0;
}

:deep(.el-card__body) {
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  min-height: 40px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  flex-wrap: wrap;
}

.card-icon {
  font-size: 20px;
  color: #409eff;
  padding: 8px;
  background: rgba(64, 158, 255, 0.1);
  border-radius: 8px;
}

.card-title {
  font-weight: 600;
  color: #2c3e50;
  font-size: 18px;
}

.header-status {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-left: 20px;
  flex-wrap: wrap;
}

/* 表格样式 */
:deep(.el-table) {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  background: rgba(255, 255, 255, 0.9);
  font-size: 14px;
}

:deep(.el-table__header) {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

:deep(.el-table th) {
  background: transparent;
  color: #2c3e50;
  font-weight: 600;
  border-bottom: 2px solid #dee2e6;
}

:deep(.el-table .el-table__row:hover) {
  background: rgba(64, 158, 255, 0.05);
}

/* 标签样式 */
:deep(.el-tag) {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  border: none;
}

:deep(.el-tag--primary) {
  background: linear-gradient(135deg, #409eff, #66b3ff);
  color: white;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3);
}

:deep(.el-tag--success) {
  background: linear-gradient(135deg, #67c23a, #85ce61);
  color: white;
  box-shadow: 0 2px 8px rgba(103, 194, 58, 0.3);
}

:deep(.el-tag--danger) {
  background: linear-gradient(135deg, #f56c6c, #f78989);
  color: white;
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.3);
}

:deep(.el-tag--warning) {
  background: linear-gradient(135deg, #e6a23c, #ebb563);
  color: white;
  box-shadow: 0 2px 8px rgba(230, 162, 60, 0.3);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 2px 8px rgba(230, 162, 60, 0.3);
  }
  50% {
    box-shadow: 0 4px 16px rgba(230, 162, 60, 0.5);
  }
  100% {
    box-shadow: 0 2px 8px rgba(230, 162, 60, 0.3);
  }
}

/* 按钮样式 */
:deep(.el-button) {
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.3s ease;
  border: none;
}

:deep(.el-button:hover) {
  transform: translateY(-1px);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #409eff, #66b3ff);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #3a8ee6, #5daaff);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
}

:deep(.el-button--success) {
  background: linear-gradient(135deg, #67c23a, #85ce61);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

:deep(.el-button--warning) {
  background: linear-gradient(135deg, #e6a23c, #ebb563);
  box-shadow: 0 4px 12px rgba(230, 162, 60, 0.3);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, #f56c6c, #f78989);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.3);
}

:deep(.el-button--info) {
  background: linear-gradient(135deg, #909399, #b1b3b8);
  color: white;
  box-shadow: 0 4px 12px rgba(144, 147, 153, 0.3);
  border: none;
}

:deep(.el-button--info:hover) {
  background: linear-gradient(135deg, #82848a, #a6a9ad);
  box-shadow: 0 6px 16px rgba(144, 147, 153, 0.4);
}

/* 对话框样式 */
:deep(.el-dialog) {
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(20px);
}

:deep(.el-dialog__header) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
  margin: 0;
  border: none;
}

:deep(.el-dialog__title) {
  font-size: 20px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

:deep(.el-dialog__body) {
  padding: 24px;
  background: rgba(255, 255, 255, 0.95);
}

/* 表单样式 */
:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #2c3e50;
  font-size: 14px;
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
  border: 1px solid #e1e8f0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
  transition: all 0.3s ease;
}

:deep(.el-input__wrapper:hover) {
  border-color: #409eff;
  box-shadow: 0 4px 8px rgba(64, 158, 255, 0.1);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
}

:deep(.el-textarea__inner) {
  border-radius: 8px;
  border: 1px solid #e1e8f0;
  transition: all 0.3s ease;
}

:deep(.el-textarea__inner:hover) {
  border-color: #409eff;
}

:deep(.el-textarea__inner:focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
}

.connection-list,
.task-list {
  margin-top: 16px;
}

/* 对话框底部按钮 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

/* 文件输入组样式 */
.file-input-group {
  display: flex;
  gap: 8px;
  align-items: center;
}

.file-input-group .el-input {
  flex: 1;
}

.file-input-group .el-button {
  flex-shrink: 0;
  height: 32px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 表单提示样式 */
.form-tip {
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(64, 158, 255, 0.05);
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

/* 按钮组样式 */
.button-group {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.button-group .el-button {
  margin: 0;
}

/* 操作按钮容器样式 - 防止分行 */
.action-buttons-container {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: nowrap;
  justify-content: center;
  padding: 4px 0;
}

.action-btn-mini {
  margin: 0 !important;
  padding: 4px 8px;
  border-radius: 3px;
  font-size: 11px;
  min-width: 50px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  line-height: 1;
  box-sizing: border-box;
}

.action-btn-mini:hover {
  transform: translateY(-1px);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
}

/* 可用目录样式 */
.available-dirs {
  margin-top: 8px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  backdrop-filter: blur(10px);
}

.more-dirs {
  color: #909399;
  font-size: 12px;
  margin-left: 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .weather-data-fetcher {
    padding: 16px;
  }
  
  .page-title {
    font-size: 32px;
  }
  
  .page-description {
    font-size: 16px;
  }
  
  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .header-status {
    margin-left: 0;
    gap: 12px;
    width: 100%;
    justify-content: flex-start;
  }
  
  :deep(.el-table) {
    font-size: 12px;
  }
  
  :deep(.el-button) {
    font-size: 12px;
    padding: 6px 12px;
  }
}

/* 日志查看样式 */
.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e1e8f0;
}

.logs-title {
  font-size: 16px;
  color: #2c3e50;
}

.logs-filters {
  display: flex;
  gap: 8px;
  align-items: center;
}

.logs-content {
  max-height: 600px;
  overflow-y: auto;
  padding: 4px;
}

.no-logs {
  text-align: center;
  padding: 40px 0;
  color: #909399;
}

.logs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-item {
  padding: 12px 16px;
  border-radius: 8px;
  border-left: 4px solid #e1e8f0;
  background: rgba(255, 255, 255, 0.8);
  transition: all 0.2s ease;
}

.log-item:hover {
  background: rgba(255, 255, 255, 1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.log-item.log-success {
  border-left-color: #67c23a;
  background: rgba(103, 194, 58, 0.05);
}

.log-item.log-warning {
  border-left-color: #e6a23c;
  background: rgba(230, 162, 60, 0.05);
}

.log-item.log-error {
  border-left-color: #f56c6c;
  background: rgba(245, 108, 108, 0.05);
}

.log-item.log-info {
  border-left-color: #409eff;
  background: rgba(64, 158, 255, 0.05);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.log-time {
  font-size: 12px;
  color: #909399;
  font-family: 'Courier New', monospace;
}

.log-message {
  font-size: 14px;
  color: #2c3e50;
  font-weight: 500;
  margin-bottom: 4px;
}

.log-details {
  font-size: 12px;
  color: #606266;
  background: rgba(0, 0, 0, 0.02);
  padding: 8px 12px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 调度器状态样式 */

.scheduler-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}



.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.status-label {
  font-weight: 600;
  color: #2c3e50;
  font-size: 13px;
}

.scheduled-jobs {
  background: rgba(64, 158, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid rgba(64, 158, 255, 0.1);
  margin-top: 12px;
}

.jobs-title {
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 8px;
  font-size: 14px;
}

.jobs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.job-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  font-size: 12px;
}

.job-name {
  font-weight: 500;
  color: #2c3e50;
  flex: 1;
}

.job-next-run {
  color: #909399;
  font-family: 'Courier New', monospace;
}

/* 滚动条样式 */
.logs-content::-webkit-scrollbar {
  width: 8px;
}

.logs-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.logs-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.logs-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.weather-data-fetcher .page-header {
  margin-bottom: 14px;
}

.weather-data-fetcher .page-title {
  margin-bottom: 6px;
  color: var(--text-primary);
}

.weather-data-fetcher .page-description {
  color: var(--text-secondary);
}

.weather-data-fetcher .card-header {
  min-height: 44px;
}

.weather-data-fetcher .status-label {
  color: var(--text-secondary);
}

.weather-data-fetcher .job-item {
  background: rgba(8, 24, 38, 0.65);
  border: 1px solid rgba(146, 186, 220, 0.2);
}

.weather-data-fetcher .job-name {
  color: var(--text-primary);
}

.weather-data-fetcher .job-next-run {
  color: var(--text-secondary);
  font-family: "Consolas", "Roboto Mono", monospace;
}

.weather-data-fetcher .logs-header {
  border-bottom-color: rgba(146, 186, 220, 0.2);
}

.weather-data-fetcher .log-item {
  background: rgba(8, 24, 38, 0.65);
}

@media (max-width: 1200px) {
  .flow-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .flow-steps {
    grid-template-columns: 1fr;
  }

  .flow-link {
    display: none;
  }
}
</style> 
