<template>
  <DigitalPage>
    <DigitalHero
      eyebrow="WEATHER DATA PIPELINE"
      title="气象预报数据拉取"
      subtitle="配置SSH连接，实现气象预报数据的定时拉取、处理和上传"
      :metrics="heroMetrics"
    >
      <template #meta>
        <span class="digital-status-chip">当前场站：{{ currentWindFarmDisplay }}</span>
      </template>
    </DigitalHero>

    <div class="digital-grid">
      <div class="digital-grid digital-grid--two-column">
        <el-card class="glass-panel" shadow="never">
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
              <el-table-column prop="name" label="连接名称" header-align="center" align="center" />
              <el-table-column prop="host" label="服务器地址" header-align="center" align="center" />
              <el-table-column prop="port" label="端口" max-width="120" header-align="center" align="center" />
              <el-table-column prop="username" label="用户名" header-align="center" align="center" />
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
                  <div class="action-buttons-container">
                    <el-button
                      size="small"
                      type="info"
                      @click="testConnection(scope.row)"
                      :loading="scope.row.testing"
                      class="action-btn-mini"
                    >
                      测试连接
                    </el-button>
                    <el-button
                      size="small"
                      type="primary"
                      @click="editConnection(scope.row)"
                      class="action-btn-mini"
                    >
                      编辑
                    </el-button>
                    <el-button
                      size="small"
                      type="danger"
                      @click="deleteConnection(scope.row)"
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

        <el-card class="glass-panel" shadow="never">
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
      </div>

      <el-card class="glass-panel" shadow="never">
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
            <el-table-column prop="name" label="任务名称" max-width="140" header-align="center" align="center" />
            <el-table-column prop="connection_name" label="连接" max-width="160" header-align="center" align="center" />
            <el-table-column prop="schedule" label="执行频率" max-width="140" header-align="center" align="center">
              <template #default="scope">
                {{ getScheduleDescription(scope.row.schedule) }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" max-width="120" header-align="center" align="center">
              <template #default="scope">
                <el-tag :type="getTaskStatusType(scope.row.status, scope.row.enabled)">
                  {{ getTaskStatusText(scope.row.status, scope.row.enabled) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_run" label="最后执行" max-width="200" header-align="center" align="center" />
            <el-table-column label="操作" max-width="320" fixed="right" header-align="center" align="center">
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
    </div>

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
        <el-form-item label="文件名模式" prop="file_pattern">
          <el-input v-model="taskForm.file_pattern" placeholder="*.csv" />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 文件名匹配模式，例如 "*.csv" 或 "data_*.txt"
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="执行频率" prop="schedule">
          <el-input v-model="taskForm.schedule" placeholder="0 */6 * * *" />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 使用标准的cron表达式，例如 "0 */6 * * *" 表示每6小时执行一次
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="自定义频率" prop="custom_schedule">
          <el-input v-model="taskForm.custom_schedule" placeholder="例如: 0 0 * * *" />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 如果选择"自定义频率"，请在此输入具体的cron表达式
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="处理选项" prop="processing_options">
          <el-checkbox-group v-model="taskForm.processing_options">
            <el-checkbox label="完整性检查" />
            <el-checkbox label="数据清洗" />
            <el-checkbox label="数据转换" />
            <el-checkbox label="数据验证" />
          </el-checkbox-group>
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 选择需要执行的处理步骤
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="去重选项" prop="deduplication_options">
          <el-checkbox-group v-model="taskForm.deduplication_options">
            <el-checkbox label="跳过已存在" />
            <el-checkbox label="覆盖已存在" />
            <el-checkbox label="仅记录差异" />
          </el-checkbox-group>
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 选择数据去重策略
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="保存路径" prop="save_path">
          <el-input v-model="taskForm.save_path" placeholder="D:\\weather_data\\{date}\\" />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 程序会将拉取到的文件保存到此路径，{date} 会替换为实际日期
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="超时时间 (秒)" prop="timeout">
          <el-input-number v-model="taskForm.timeout" :min="1" :max="3600" />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 任务执行超时时间，超过则视为失败
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="重试次数" prop="retry_count">
          <el-input-number v-model="taskForm.retry_count" :min="0" :max="10" />
          <div class="form-tip">
            <el-text type="info" size="small">
              💡 任务执行失败后的重试次数
            </el-text>
          </div>
        </el-form-item>
        <el-form-item label="任务描述" prop="description">
          <el-input type="textarea" v-model="taskForm.description" placeholder="任务的简要描述" />
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
  </DigitalPage>
</template>

<script>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axiosInstance from '../api/axios'
import { useWindFarmStore } from '@/store/windFarm'
import {
  Connection,
  Download,
  Folder,
  Timer
} from '@element-plus/icons-vue'
import DigitalPage from './common/DigitalPage.vue'
import DigitalHero from './common/DigitalHero.vue'

export default {
  name: 'WeatherDataFetcher',
  components: {
    DigitalPage,
    DigitalHero,
    Connection,
    Download,
    Folder,
    Timer
  },
  setup() {
    const { selectedWindFarm, findWindFarmByCode } = useWindFarmStore()
    const currentWindFarmRecord = computed(() => findWindFarmByCode(selectedWindFarm.value))
    const currentWindFarmDisplay = computed(() => {
      const record = currentWindFarmRecord.value
      if (record) {
        return record.farm_name || record.farm_code || selectedWindFarm.value
      }
      return selectedWindFarm.value
    })

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

    const heroMetrics = computed(() => [
      {
        id: 'connections',
        label: '已配置连接',
        value: connections.value.length || 0,
        meta: '活跃 SSH',
      },
      {
        id: 'tasks',
        label: '任务队列',
        value: tasks.value.length || 0,
        meta: '自动编排',
      },
      {
        id: 'scheduler',
        label: '调度器',
        value: schedulerInfo.value.is_running ? 'RUNNING' : 'STOPPED',
        meta: `已调度 ${schedulerInfo.value.total_jobs || 0} 项`,
      },
    ])
    
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
        const response = await axiosInstance.get('/weather-fetch/connections')
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
        const response = await axiosInstance.get('/weather-fetch/tasks')
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
        const response = await axiosInstance.post(`/weather-fetch/connections/${connection.id}/test`)
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
        
        await axiosInstance.delete(`/weather-fetch/connections/${connection.id}`)
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
        
        const url = editingConnection.value 
          ? `/weather-fetch/connections/${connectionForm.id}`
          : '/weather-fetch/connections'
        
        const method = editingConnection.value ? 'put' : 'post'
        
        await axiosInstance[method](url, connectionForm)
        
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
        await axiosInstance.post(`/weather-fetch/tasks/${task.id}/run`)
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
        await axiosInstance.post(`/weather-fetch/tasks/${task.id}/toggle`)
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
        
        await axiosInstance.delete(`/weather-fetch/tasks/${task.id}`)
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
        
        const url = editingTask.value 
          ? `/weather-fetch/tasks/${taskForm.id}`
          : '/weather-fetch/tasks'
        
        const method = editingTask.value ? 'put' : 'post'
        
        // 准备提交数据，确保时间格式正确
        const submitData = { ...taskForm }
        
        // 处理时间范围数据 - 如果不是range策略，删除time_range字段
        if (submitData.time_strategy !== 'range' || !submitData.time_range) {
          delete submitData.time_range
        }
        
        await axiosInstance[method](url, submitData)
        
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
        const response = await axiosInstance.post('/weather-fetch/check-directories', {
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
        const response = await axiosInstance.get(`/weather-fetch/tasks/${currentTaskId.value}/logs`, {
          params: {
            level: logLevel.value || undefined,
            per_page: 100
          }
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
    
    // Cron表达式转换为用户友好的描述
    // 调度器管理方法
    const checkSchedulerStatus = async () => {
      checkingScheduler.value = true
      try {
        const response = await axiosInstance.get('/weather-fetch/scheduler/status')
        schedulerInfo.value = response.data
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
        const response = await axiosInstance.post('/weather-fetch/scheduler/restart')
        schedulerInfo.value = response.data.status
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
      fetchConnections()
      fetchTasks()
      checkSchedulerStatus() // 检查调度器状态
    })

    watch(() => selectedWindFarm.value, () => {
      connections.value = []
      tasks.value = []
      schedulerInfo.value = { is_running: false, jobs: [], total_jobs: 0 }
      fetchConnections()
      fetchTasks()
      checkSchedulerStatus()
      ElMessage.info(`已切换到场站：${currentWindFarmDisplay.value}`)
    })

    return {
      currentWindFarmDisplay,
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
      heroMetrics,
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
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.card-icon {
  font-size: 22px;
  padding: 10px;
  border-radius: 14px;
  background: rgba(56, 196, 255, 0.12);
  color: #38c4ff;
  box-shadow: 0 12px 24px rgba(56, 196, 255, 0.18);
}

.card-title {
  font-weight: 600;
  font-size: 20px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.header-status {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

.scheduler-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.connection-list,
.task-list {
  margin-top: 16px;
}

.action-buttons-container {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: center;
  padding: 4px 0;
}

.action-btn-mini {
  margin: 0 !important;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  min-width: 64px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.04em;
}

.action-btn-mini:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(32, 120, 255, 0.25);
}

.scheduled-jobs {
  background: rgba(12, 46, 86, 0.45);
  border: 1px solid rgba(56, 196, 255, 0.18);
  border-radius: 16px;
  padding: 16px;
  margin-top: 20px;
}

.jobs-title {
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

.jobs-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.job-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(4, 18, 36, 0.72);
  font-size: 13px;
}

.job-name {
  font-weight: 600;
  color: var(--text-primary);
}

.job-next-run {
  color: var(--text-secondary);
  font-family: 'Courier New', monospace;
}

.file-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
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

.form-tip {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(32, 96, 148, 0.18);
  border-left: 3px solid rgba(56, 196, 255, 0.45);
}

.available-dirs {
  margin-top: 8px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(4, 18, 36, 0.76);
  border: 1px solid rgba(56, 196, 255, 0.12);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.more-dirs {
  color: var(--text-secondary);
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid rgba(56, 196, 255, 0.12);
}

.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(56, 196, 255, 0.12);
}

.logs-title {
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-primary);
}

.logs-filters {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logs-content {
  max-height: 600px;
  overflow-y: auto;
  padding-right: 8px;
}

.no-logs {
  text-align: center;
  color: var(--text-secondary);
  padding: 48px 0;
}

.logs-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.log-item {
  padding: 14px 18px;
  border-radius: 12px;
  border-left: 4px solid rgba(56, 196, 255, 0.18);
  background: rgba(4, 18, 36, 0.72);
  box-shadow: 0 10px 20px rgba(3, 13, 30, 0.3);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.log-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(3, 13, 30, 0.35);
}

.log-item.log-success {
  border-left-color: rgba(34, 246, 170, 0.6);
  background: rgba(14, 42, 38, 0.7);
}

.log-item.log-warning {
  border-left-color: rgba(230, 162, 60, 0.6);
  background: rgba(48, 32, 6, 0.7);
}

.log-item.log-error {
  border-left-color: rgba(245, 108, 108, 0.6);
  background: rgba(48, 10, 14, 0.72);
}

.log-item.log-info {
  border-left-color: rgba(56, 196, 255, 0.6);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.log-time {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'Courier New', monospace;
}

.log-message {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.log-details {
  font-size: 12px;
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.18);
  padding: 8px 12px;
  border-radius: 8px;
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

.logs-content::-webkit-scrollbar {
  width: 8px;
}

.logs-content::-webkit-scrollbar-track {
  background: rgba(4, 18, 36, 0.6);
}

.logs-content::-webkit-scrollbar-thumb {
  background: rgba(56, 196, 255, 0.35);
  border-radius: 4px;
}

.logs-content::-webkit-scrollbar-thumb:hover {
  background: rgba(56, 196, 255, 0.5);
}

@media (max-width: 768px) {
  .scheduler-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .action-buttons-container {
    justify-content: flex-start;
  }
}
</style>