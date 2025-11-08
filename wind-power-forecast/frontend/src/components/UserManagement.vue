<template>
  <DigitalPage>
    <div class="user-management">
      <DigitalHero
        eyebrow="ACCESS CONTROL"
        title="用户管理系统"
        subtitle="集中管理系统用户账号、角色与权限"
        :metrics="heroMetrics"
        :chips="heroChips"
      >
        <template #meta>
          <span class="digital-status-chip">认证状态：{{ authStatusLabel }}</span>
          <span class="digital-status-chip">角色总数：{{ roles.length }}</span>
        </template>
        <template #actions>
          <el-button
            v-if="hasPermission('manage_users')"
            type="primary"
            size="large"
            class="hero-action-button"
            @click="handleAddUser"
          >
            <el-icon><Plus /></el-icon>
            添加用户
          </el-button>
        </template>
      </DigitalHero>

      <section class="user-management__content">
        <div
          :class="[
            'user-management__panel',
            'digital-panel',
            'digital-panel--interactive',
            { 'panel--pulse': tablePulse }
          ]"
        >
          <div class="user-management__panel-header">
            <div class="panel-header__copy">
              <h2>用户列表</h2>
              <p>查看、筛选并维护系统用户的关键信息</p>
            </div>
            <div class="panel-header__chips">
              <span class="digital-status-chip">当前页：{{ currentPage }}</span>
              <span class="digital-status-chip">每页：{{ pageSize }}</span>
            </div>
          </div>

          <div class="user-management__toolbar">
            <el-input
              v-model="searchQuery"
              placeholder="搜索用户名、姓名、邮箱或角色"
              clearable
              class="user-management__search"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <div class="toolbar__actions">
              <el-tooltip content="刷新列表" placement="top">
                <el-button
                  :icon="Refresh"
                  circle
                  :loading="loading"
                  @click="fetchData"
                />
              </el-tooltip>
            </div>
          </div>

          <el-table
            :data="filteredUsers"
            class="user-management__table"
            v-loading="loading"
            border
            stripe
            highlight-current-row
            row-key="id"
            @sort-change="handleSortChange"
            @filter-change="handleFilterChange"
          >
            <el-table-column prop="id" label="ID" width="70" sortable="custom" />
            <el-table-column prop="username" label="用户名" width="120" sortable="custom">
              <template #default="scope">
                <el-text :type="isSuperAdmin() && scope.row.username === 'admin' ? 'danger' : 'primary'">
                  {{ scope.row.username }}
                </el-text>
              </template>
            </el-table-column>
            <el-table-column prop="full_name" label="姓名" width="120" sortable />
            <el-table-column prop="email" label="邮箱" min-width="200" sortable />
            <el-table-column
              prop="role.name"
              label="角色"
              width="140"
              sortable
              :filters="roleFilters"
              :filter-method="filterByRole"
            >
              <template #default="scope">
                <el-tag :type="scope.row.role.name === '系统管理员' ? 'danger' : 'primary'" effect="dark">
                  {{ scope.row.role.name }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="状态"
              width="110"
              :filters="[
                { text: '启用', value: true },
                { text: '禁用', value: false }
              ]"
              :filter-method="filterByStatus"
            >
              <template #default="scope">
                <el-tag :type="scope.row.is_active ? 'success' : 'danger'" effect="dark">
                  {{ scope.row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_login" label="最后登录时间" min-width="180" sortable="custom">
              <template #default="scope">
                {{ formatDate(scope.row.last_login) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" fixed="right" width="210">
              <template #default="scope">
                <el-button-group class="user-management__actions">
                  <el-tooltip content="编辑用户" placement="top">
                    <el-button
                      v-if="hasPermission('manage_users')"
                      type="primary"
                      :icon="Edit"
                      size="small"
                      @click="handleEdit(scope.row)"
                    />
                  </el-tooltip>
                  <el-tooltip :content="scope.row.is_active ? '禁用用户' : '启用用户'" placement="top">
                    <el-button
                      v-if="hasPermission('manage_users')"
                      :type="scope.row.is_active ? 'danger' : 'success'"
                      :icon="scope.row.is_active ? Lock : Unlock"
                      size="small"
                      @click="handleToggleStatus(scope.row)"
                    />
                  </el-tooltip>
                  <el-tooltip content="重置密码" placement="top">
                    <el-button
                      v-if="hasPermission('manage_users')"
                      type="warning"
                      :icon="Key"
                      size="small"
                      @click="handleResetPassword(scope.row)"
                    />
                  </el-tooltip>
                  <el-tooltip content="删除用户" placement="top">
                    <el-button
                      v-if="hasPermission('manage_users')"
                      type="danger"
                      :icon="Delete"
                      size="small"
                      @click="handleDelete(scope.row)"
                    />
                  </el-tooltip>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>

          <div class="user-management__footer">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              :total="users.length"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
              background
            />
          </div>
        </div>
      </section>

      <el-dialog
        v-model="showUserDialog"
        :title="isEdit ? '编辑用户' : '添加用户'"
        width="500px"
        @closed="handleDialogClosed"
        destroy-on-close
      >
        <el-form
          ref="userForm"
          :model="userFormData"
          :rules="userRules"
          label-width="100px"
          label-position="left"
          class="custom-form"
        >
          <el-form-item label="用户名" prop="username" v-if="!isEdit">
            <el-input v-model="userFormData.username" placeholder="请输入用户名" />
          </el-form-item>

          <el-form-item label="密码" prop="password" v-if="!isEdit">
            <el-input
              v-model="userFormData.password"
              type="password"
              placeholder="请输入密码"
              show-password
            />
          </el-form-item>

          <el-form-item label="姓名" prop="full_name">
            <el-input v-model="userFormData.full_name" placeholder="请输入姓名" />
          </el-form-item>

          <el-form-item label="邮箱" prop="email">
            <el-input v-model="userFormData.email" placeholder="请输入邮箱" />
          </el-form-item>

          <el-form-item label="角色" prop="role_id">
            <el-select v-model="userFormData.role_id" placeholder="请选择角色" style="width: 100%">
              <el-option
                v-for="role in roles"
                :key="role.id"
                :label="role.name"
                :value="role.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="状态" prop="is_active">
            <el-switch
              v-model="userFormData.is_active"
              active-text="启用"
              inactive-text="禁用"
              :active-value="true"
              :inactive-value="false"
            />
          </el-form-item>
        </el-form>

        <template #footer>
          <div class="dialog-footer">
            <el-button @click="showUserDialog = false">取消</el-button>
            <el-button type="primary" :loading="submitting" @click="handleSubmitUser">
              确认
            </el-button>
          </div>
        </template>
      </el-dialog>

      <el-dialog
        v-model="showResetPasswordDialog"
        title="重置用户密码"
        width="400px"
        destroy-on-close
      >
        <el-form
          ref="resetPasswordForm"
          :model="resetPasswordFormData"
          :rules="resetPasswordRules"
          label-width="100px"
          label-position="left"
          class="custom-form"
        >
          <el-form-item label="新密码" prop="password">
            <el-input
              v-model="resetPasswordFormData.password"
              type="password"
              placeholder="请输入新密码"
              show-password
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="resetPasswordFormData.confirmPassword"
              type="password"
              placeholder="请再次输入新密码"
              show-password
            />
          </el-form-item>
        </el-form>

        <template #footer>
          <div class="dialog-footer">
            <el-button @click="showResetPasswordDialog = false">取消</el-button>
            <el-button type="primary" :loading="resettingPassword" @click="handleSubmitResetPassword">
              确认
            </el-button>
          </div>
        </template>
      </el-dialog>
    </div>
  </DigitalPage>
</template>

<script>
import { ref, reactive, onMounted, computed, watchEffect, watch, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Edit,
  Refresh,
  Search,
  Delete,
  Lock,
  Unlock,
  Key
} from '@element-plus/icons-vue'
import { getUsers, createUser, updateUser, deleteUser, resetUserPassword, getRoles } from '../api/auth'
import { isAuthReady, isAuthLoading } from '../store/authReady'
import DigitalPage from './common/DigitalPage.vue'
import DigitalHero from './common/DigitalHero.vue'

export default {
  name: 'UserManagement',
  components: {
    DigitalPage,
    DigitalHero,
  },
  setup() {
    // 数据
    const users = ref([])
    const roles = ref([])
    const loading = ref(false)
    const loadingRoles = ref(false)
    const submitting = ref(false)
    const resettingPassword = ref(false)
    const searchQuery = ref('')

    const tablePulse = ref(false)
    const tablePulseTimer = ref(null)
    const lastFetchAt = ref(null)

    const triggerTablePulse = (duration = 900) => {
      if (tablePulseTimer.value) {
        clearTimeout(tablePulseTimer.value)
      }
      tablePulse.value = true
      tablePulseTimer.value = setTimeout(() => {
        tablePulse.value = false
        tablePulseTimer.value = null
      }, duration)
    }
    
    // 分页
    const currentPage = ref(1)
    const pageSize = ref(10)
    
    // 表单引用
    const userForm = ref(null)
    const resetPasswordForm = ref(null)
    
    // 对话框控制
    const showUserDialog = ref(false)
    const showResetPasswordDialog = ref(false)
    const isEdit = ref(false)
    
    // 当前编辑的用户ID
    const currentUserId = ref(null)
    
    // 表单数据
    const userFormData = reactive({
      username: '',
      password: '',
      full_name: '',
      email: '',
      role_id: '',
      is_active: true,
      original_role_id: ''
    })
    
    const resetPasswordFormData = reactive({
      password: '',
      confirmPassword: ''
    })
    
    // 计算角色过滤选项
    const roleFilters = computed(() => {
      if (!roles.value) return []
      return roles.value.map(role => ({
        text: role.name,
        value: role.name
      }))
    })

    const authStatusLabel = computed(() => {
      if (isAuthLoading.value) return '认证检查中'
      return isAuthReady.value ? '认证已通过' : '认证未通过'
    })

    const heroMetrics = computed(() => {
      const total = users.value.length
      const activeCount = users.value.filter(user => user.is_active).length
      const roleCount = roles.value.length
      const activeRate = total ? Math.round((activeCount / Math.max(total, 1)) * 100) : 0

      return [
        {
          id: 'total-users',
          label: '总用户',
          value: total || '—',
          meta: total ? '注册账户' : '等待同步',
        },
        {
          id: 'active-users',
          label: '启用账户',
          value: activeCount || '—',
          meta: total ? `${activeRate}% 活跃` : '暂无数据',
        },
        {
          id: 'role-count',
          label: '角色数量',
          value: roleCount || '—',
          meta: roleCount ? '角色配置可用' : '未创建角色',
        },
      ]
    })

    const lastSyncLabel = computed(() => {
      if (!lastFetchAt.value) {
        return '尚未同步'
      }
      return new Intl.DateTimeFormat('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }).format(lastFetchAt.value)
    })
    
    // 排序相关状态
    const sortProperty = ref('')
    const sortOrder = ref('')
    
    // 计算过滤和排序后的用户列表
    const filteredUsers = computed(() => {
      let result = [...users.value]  // 创建副本避免修改原数组
      
      // 应用搜索过滤
      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase()
        result = result.filter(user => 
          user.username.toLowerCase().includes(query) ||
          user.full_name.toLowerCase().includes(query) ||
          user.email.toLowerCase().includes(query) ||
          (user.role && user.role.name.toLowerCase().includes(query))
        )
      }
      
      // 应用排序
      if (sortProperty.value && sortOrder.value) {
        result.sort((a, b) => {
          let aValue, bValue;
          
          // 处理嵌套属性，如 role.name
          if (sortProperty.value.includes('.')) {
            const props = sortProperty.value.split('.');
            aValue = props.reduce((obj, prop) => obj && obj[prop], a);
            bValue = props.reduce((obj, prop) => obj && obj[prop], b);
          } else {
            aValue = a[sortProperty.value];
            bValue = b[sortProperty.value];
          }
          
          // 特殊处理日期字段
          if (sortProperty.value === 'last_login') {
            // 处理null或undefined值
            if (!aValue) return sortOrder.value === 'ascending' ? -1 : 1;
            if (!bValue) return sortOrder.value === 'ascending' ? 1 : -1;
            
            // 将ISO日期字符串转换为Date对象进行比较
            const aDate = new Date(aValue);
            const bDate = new Date(bValue);
            return sortOrder.value === 'ascending' 
              ? aDate - bDate 
              : bDate - aDate;
          }
          // 字符串使用 localeCompare，数字直接比较
          else if (typeof aValue === 'string') {
            return sortOrder.value === 'ascending' 
              ? aValue.localeCompare(bValue)
              : bValue.localeCompare(aValue);
          } else {
            return sortOrder.value === 'ascending'
              ? aValue - bValue
              : bValue - aValue;
          }
        });
      }
      
      // 分页处理
      const startIndex = (currentPage.value - 1) * pageSize.value
      const endIndex = startIndex + pageSize.value
      return result.slice(startIndex, endIndex)
    })
    
    // 表单验证规则
    const userRules = {
      username: [
        { required: true, message: '请输入用户名', trigger: 'blur' },
        { min: 3, message: '用户名长度不能少于3个字符', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 6, message: '密码长度不能少于6个字符', trigger: 'blur' },
        { 
          validator: (rule, value, callback) => {
            const hasLetter = /[a-zA-Z]/.test(value);
            const hasNumber = /[0-9]/.test(value);
            
            if (!(hasLetter && hasNumber)) {
              callback(new Error('密码必须包含字母和数字'));
            } else {
              callback();
            }
          }, 
          trigger: 'blur' 
        }
      ],
      full_name: [
        { required: true, message: '请输入姓名', trigger: 'blur' }
      ],
      email: [
        { required: true, message: '请输入邮箱', trigger: 'blur' },
        { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
      ],
      role_id: [
        { required: true, message: '请选择角色', trigger: 'change' }
      ]
    }
    
    const resetPasswordRules = {
      password: [
        { required: true, message: '请输入新密码', trigger: 'blur' },
        { min: 6, message: '密码长度不能少于6个字符', trigger: 'blur' }
      ],
      confirmPassword: [
        { required: true, message: '请再次输入新密码', trigger: 'blur' },
        {
          validator: (rule, value, callback) => {
            if (value !== resetPasswordFormData.password) {
              callback(new Error('两次输入的密码不一致'))
            } else {
              callback()
            }
          },
          trigger: 'blur'
        }
      ]
    }
    
    // 获取当前用户信息
    const currentUser = JSON.parse(localStorage.getItem('user') || '{}')
    const currentUsername = currentUser.username || ''
    
    // 检查权限
    const hasPermission = (requiredPermission) => {
      // 这里应该根据实际情况实现权限检查
      if (!currentUser) return false;
      
      // 检查用户的权限列表
      if (currentUser.permissions) {
        // 处理权限可能是数组或嵌套对象的情况
        let permissions = currentUser.permissions;
        
        // 如果权限是对象且有permissions属性
        if (typeof permissions === 'object' && !Array.isArray(permissions) && permissions.permissions) {
          permissions = permissions.permissions;
        }
        
        // 如果权限是数组
        if (Array.isArray(permissions)) {
          // 如果用户权限中包含所需权限，则返回true
          return permissions.includes(requiredPermission);
        }
      }
      
      // 系统管理员拥有所有权限（向下兼容）
      if (currentUser.role === '系统管理员') return true;
      
      // 运行操作人员可以查看用户列表但不能管理用户
      if (currentUser.role === '运行操作人员') {
        return requiredPermission === 'view_users';
      }
      
      // 普通用户没有用户管理相关权限
      return false;
    }

    const canManageUsers = computed(() => hasPermission('manage_users'))
    const heroChips = computed(() => [
      { id: 'sync', label: `上次同步：${lastSyncLabel.value}` },
      { id: 'mode', label: canManageUsers.value ? '管理模式' : '查看模式' },
    ])
    
    // 获取用户和角色数据
    const fetchData = async () => {
      if (!isAuthReady.value) {
        console.warn('认证未就绪，暂不获取用户数据');
        return; // 如果认证未就绪，则不执行获取
      }
      
      loading.value = true;
      console.log('认证已就绪，开始串行获取用户和角色数据...');
      try {
        // 改为串行获取数据，先获取用户，再获取角色
        console.log('第一步: 开始获取用户列表...');
        await fetchUsersInternal();
        
        console.log('第二步: 开始获取角色列表...');
        await fetchRolesInternal();
        
        console.log('用户和角色数据获取完成 (串行)');
        lastFetchAt.value = new Date();
        triggerTablePulse();
      } catch (error) {
        // 错误已在内部函数处理
        console.error('获取用户/角色数据时出错 (串行):', error);
      } finally {
        loading.value = false;
      }
    };
    
    // 内部获取用户函数
    const fetchUsersInternal = async () => {
      try {
        console.log('内部函数: 开始获取用户列表...');
        const data = await getUsers();
        console.log('成功获取用户列表, 数量:', data.length);
        users.value = data;
        currentPage.value = 1;
      } catch (error) {
        console.error('获取用户列表失败 (内部):', error);
        // ElMessage已由Axios拦截器处理401，这里可以处理其他错误
        if (!error.response || error.response.status !== 401) {
          ElMessage.error('获取用户列表失败: ' + (error.response?.data?.message || '未知错误'));
        }
        throw error; // 抛出错误让Promise.all知道失败了
      }
    };
    
    // 内部获取角色函数
    const fetchRolesInternal = async () => {
      try {
        console.log('内部函数: 开始获取角色列表...');
        const data = await getRoles();
        console.log('成功获取角色列表, 数量:', data.length);
        roles.value = data;
        
        // 检查是否获取到角色列表
        if (!data || data.length === 0) {
          ElMessage.warning('未获取到任何角色信息，请先创建角色');
        }
      } catch (error) {
        console.error('获取角色列表失败 (内部):', error);
        if (!error.response || error.response.status !== 401) {
          ElMessage.error('获取角色列表失败: ' + (error.response?.data?.message || '服务器错误'));
        }
        throw error; // 抛出错误
      }
    };
    
    // 使用watchEffect监听认证状态变化
    watchEffect(() => {
      console.log(`watchEffect: isAuthLoading=${isAuthLoading.value}, isAuthReady=${isAuthReady.value}`);
      if (!isAuthLoading.value && isAuthReady.value) {
        fetchData();
      } else if (!isAuthLoading.value && !isAuthReady.value) {
        console.log('认证未通过，不加载用户数据');
        users.value = [];
        roles.value = [];
      }
    });

    watch(searchQuery, () => triggerTablePulse(600))
    watch([pageSize, currentPage], () => triggerTablePulse(600))
    
    // 格式化日期
    const formatDate = (dateStr) => {
      if (!dateStr) return '从未登录'
      
      try {
        // 解析 ISO 格式的 UTC 日期
        const date = new Date(dateStr)
        
        // 检查日期是否有效
        if (isNaN(date.getTime())) {
          console.warn('无效的日期格式:', dateStr)
          return '日期格式错误'
        }
        
        // 添加时区信息
        const options = {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZone: 'Asia/Shanghai', // 明确指定中国时区
          hour12: false // 使用24小时制
        }
        
        return new Intl.DateTimeFormat('zh-CN', options).format(date)
      } catch (error) {
        console.error('日期格式化错误:', error)
        return '日期格式错误'
      }
    }
    
    // 表格筛选方法
    const filterByRole = (value, row) => {
      return row.role && row.role.name === value
    }
    
    const filterByStatus = (value, row) => {
      return row.is_active === value
    }
    
    // 分页相关方法
    const handleSizeChange = (val) => {
      pageSize.value = val
    }
    
    const handleCurrentChange = (val) => {
      currentPage.value = val
    }
    
    // 检查是否是系统管理员角色
    const isAdminRole = (role) => {
      return role && (role.name === '系统管理员' || role.name === 'admin');
    }

    // 检查是否是当前用户
    const isCurrentUser = (user) => {
      return user && user.username === currentUsername;
    }
    
    // 检查当前用户是否是超级管理员
    const isSuperAdmin = () => {
      // 通过用户名判断，假设管理员用户名为'admin'或ID为1的用户是超级管理员
      return currentUsername === 'admin' || (currentUser && currentUser.id === 1);
    }
    
    // 处理编辑用户
    const handleEdit = (user) => {
      // 检查是否试图编辑系统管理员账户
      if (isAdminRole(user.role) && !isCurrentUser(user)) {
        // 如果是管理员且不是自己，检查当前用户是否为超级管理员
        if (!isSuperAdmin()) {
          ElMessage.warning('只有超级管理员才能修改其他系统管理员的信息');
          return;
        }
      }
      
      isEdit.value = true
      currentUserId.value = user.id
      
      // 填充表单数据
      userFormData.username = user.username
      userFormData.full_name = user.full_name
      userFormData.email = user.email
      userFormData.role_id = user.role.id
      userFormData.is_active = user.is_active
      
      // 记录原始角色ID，用于检查是否更改了自己的角色
      userFormData.original_role_id = user.role.id
      
      showUserDialog.value = true
    }
    
    // 处理切换用户状态
    const handleToggleStatus = async (user) => {
      // 不允许禁用系统管理员，除非当前用户是超级管理员
      if (isAdminRole(user.role)) {
        if (!isSuperAdmin()) {
          ElMessage.warning('只有超级管理员才能禁用系统管理员账户');
          return;
        }
      }
      
      // 不允许禁用自己
      if (isCurrentUser(user)) {
        ElMessage.warning('不能禁用当前登录的账户');
        return;
      }
      
      try {
        await ElMessageBox.confirm(
          `确定要${user.is_active ? '禁用' : '启用'}用户 "${user.username}" 吗？`,
          '提示',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        await updateUser(user.id, {
          is_active: !user.is_active
        })
        
        ElMessage.success(`${user.is_active ? '禁用' : '启用'}用户成功`)
        fetchData()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('操作失败:', error)
          ElMessage.error('操作失败: ' + (error.response?.data?.message || '服务器错误'))
        }
      }
    }
    
    // 处理重置密码
    const handleResetPassword = (user) => {
      // 检查是否试图重置系统管理员密码
      if (isAdminRole(user.role) && !isCurrentUser(user)) {
        // 如果是管理员且不是自己，检查当前用户是否为超级管理员
        if (!isSuperAdmin()) {
          ElMessage.warning('只有超级管理员才能重置其他系统管理员的密码');
          return;
        }
      }
      
      currentUserId.value = user.id
      resetPasswordFormData.password = ''
      resetPasswordFormData.confirmPassword = ''
      showResetPasswordDialog.value = true
    }
    
    // 提交用户表单
    const handleSubmitUser = async () => {
      if (!userForm.value) return
      
      await userForm.value.validate(async (valid) => {
        if (!valid) return
        
        // 如果是编辑模式，并且当前用户是管理员，不允许更改自己的角色
        if (isEdit.value && isCurrentUser({username: userFormData.username})) {
          if (userFormData.role_id !== userFormData.original_role_id) {
            ElMessage.warning('不能更改自己的角色')
            return
          }
          
          // 不允许禁用自己
          if (!userFormData.is_active) {
            ElMessage.warning('不能禁用当前登录的账户')
            return
          }
        }
        
        // 检查是否选择了角色
        if (!userFormData.role_id) {
          ElMessage.warning('请选择一个角色')
          return
        }
        
        submitting.value = true
        
        try {
          if (isEdit.value) {
            // 更新用户
            await updateUser(currentUserId.value, {
              full_name: userFormData.full_name,
              email: userFormData.email,
              role_id: userFormData.role_id,
              is_active: userFormData.is_active
            })
            
            ElMessage.success('更新用户成功')
          } else {
            // 创建用户
            await createUser({
              username: userFormData.username,
              password: userFormData.password,
              full_name: userFormData.full_name,
              email: userFormData.email,
              role_id: userFormData.role_id,
              is_active: userFormData.is_active
            })
            
            ElMessage.success('创建用户成功')
          }
          
          showUserDialog.value = false
          fetchData()
        } catch (error) {
          console.error('提交用户表单失败:', error)
          
          // 显示更详细的错误信息
          let errorMessage = '操作失败'
          if (error.response && error.response.data) {
            if (error.response.data.message) {
              errorMessage += ': ' + error.response.data.message
            } else if (error.response.status === 403) {
              errorMessage += ': 权限不足'
            } else if (error.response.status === 400) {
              errorMessage += ': 请求数据无效'
            } else if (error.response.status === 500) {
              errorMessage += ': 服务器内部错误'
            }
          } else {
            errorMessage += ': ' + (error.message || '未知错误')
          }
          
          ElMessage.error(errorMessage)
        } finally {
          submitting.value = false
        }
      })
    }
    
    // 提交重置密码表单
    const handleSubmitResetPassword = async () => {
      if (!resetPasswordForm.value) return
      
      await resetPasswordForm.value.validate(async (valid) => {
        if (!valid) return
        
        resettingPassword.value = true
        
        try {
          await resetUserPassword(currentUserId.value, resetPasswordFormData.password)
          
          ElMessage.success('重置密码成功')
          showResetPasswordDialog.value = false
        } catch (error) {
          console.error('重置密码失败:', error)
          ElMessage.error('重置密码失败: ' + (error.response?.data?.message || '服务器错误'))
        } finally {
          resettingPassword.value = false
        }
      })
    }
    
    // 处理删除用户
    const handleDelete = async (user) => {
      // 不允许删除系统管理员，除非当前用户是超级管理员
      if (isAdminRole(user.role)) {
        if (!isSuperAdmin()) {
          ElMessage.warning('只有超级管理员才能删除系统管理员账户');
          return;
        }
      }
      
      // 不允许删除自己
      if (isCurrentUser(user)) {
        ElMessage.warning('不能删除当前登录的账户');
        return;
      }
      
      try {
        await ElMessageBox.confirm(
          `确定要删除用户 "${user.username}" 吗？此操作不可恢复！`,
          '警告',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        await deleteUser(user.id)
        
        ElMessage.success('删除用户成功')
        fetchData()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除用户失败:', error)
          ElMessage.error('删除用户失败: ' + (error.response?.data?.message || '服务器错误'))
        }
      }
    }
    
    // 处理添加用户
    const handleAddUser = () => {
      // 检查是否有角色可选
      if (!roles.value || roles.value.length === 0) {
        ElMessage.warning('请先创建角色后再添加用户')
        return
      }
      
      isEdit.value = false
      currentUserId.value = null
      
      // 重置表单数据
      userFormData.username = ''
      userFormData.password = ''
      userFormData.full_name = ''
      userFormData.email = ''
      userFormData.role_id = ''
      userFormData.is_active = true
      
      // 显示对话框
      showUserDialog.value = true
    }
    
    // 处理对话框关闭
    const handleDialogClosed = () => {
      // 重置表单验证
      if (userForm.value) {
        userForm.value.resetFields()
      }
      
      // 如果是添加用户，清空表单数据
      if (!isEdit.value) {
        userFormData.username = ''
        userFormData.password = ''
        userFormData.full_name = ''
        userFormData.email = ''
        userFormData.role_id = ''
        userFormData.is_active = true
      }
    }
    
    // 处理表格排序变化
    const handleSortChange = ({ prop, order }) => {
      console.log('排序变化:', prop, order)
      sortProperty.value = prop
      sortOrder.value = order
      
      if (prop === 'last_login') {
        console.log('处理日期排序，排序方向:', order)
        if (users.value && users.value.length > 0) {
          const sampleDate = users.value[0].last_login
          console.log('样本日期格式:', sampleDate, typeof sampleDate)
        }
      }
      triggerTablePulse(500)
    }

    const handleFilterChange = () => {
      triggerTablePulse(500)
    }
    
    // 生命周期钩子
    onMounted(() => {
      console.log('UserManagement组件已挂载，等待认证状态就绪...');
    })

    onUnmounted(() => {
      if (tablePulseTimer.value) {
        clearTimeout(tablePulseTimer.value)
        tablePulseTimer.value = null
      }
    })
    
    return {
      users,
      roles,
      loading,
      loadingRoles,
      submitting,
      resettingPassword,
      searchQuery,
      currentPage,
      pageSize,
      filteredUsers,
      roleFilters,
      userForm,
      resetPasswordForm,
      showUserDialog,
      showResetPasswordDialog,
      isEdit,
      userFormData,
      resetPasswordFormData,
      userRules,
      resetPasswordRules,
      formatDate,
      handleEdit,
      handleToggleStatus,
      handleResetPassword,
      handleSubmitUser,
      handleSubmitResetPassword,
      handleDelete,
      handleAddUser,
      hasPermission,
      handleDialogClosed,
      isSuperAdmin,
      handleSortChange,
      handleFilterChange,
      filterByRole,
      filterByStatus,
      handleSizeChange,
      handleCurrentChange,
      heroMetrics,
      heroChips,
      authStatusLabel,
      tablePulse,
      // 图标
      Plus,
      Edit,
      Refresh,
      Search,
      Delete,
      Lock,
      Unlock,
      Key
    }
  }
}
</script>

<style scoped>
.user-management {
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 0 12px 36px;
}

.hero-action-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  letter-spacing: 0.08em;
}

.user-management__content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.user-management__panel {
  position: relative;
  padding: 26px 28px;
  border-radius: 22px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow: hidden;
}

.panel--pulse {
  border-color: rgba(66, 195, 255, 0.32) !important;
  box-shadow: 0 24px 60px rgba(34, 246, 170, 0.25);
  animation: panelPulse 0.9s ease;
}

.panel--pulse::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background: radial-gradient(circle at 20% 20%, rgba(66, 195, 255, 0.26), transparent 65%);
  opacity: 0.45;
}

@keyframes panelPulse {
  0% {
    box-shadow: 0 0 0 rgba(34, 246, 170, 0.28);
  }
  50% {
    box-shadow: 0 26px 70px rgba(34, 246, 170, 0.45);
  }
  100% {
    box-shadow: 0 0 0 rgba(34, 246, 170, 0.18);
  }
}

.user-management__panel-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.panel-header__copy h2 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.08em;
  color: var(--text-primary);
}

.panel-header__copy p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
}

.panel-header__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.user-management__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
}

.user-management__search {
  flex: 1 1 280px;
  max-width: 520px;
}

.toolbar__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-management__table {
  border-radius: 18px;
  overflow: hidden;
}

:deep(.user-management__table .el-table) {
  background: transparent;
  color: var(--text-primary);
  --el-table-border-color: rgba(66, 195, 255, 0.12);
}

:deep(.user-management__table .el-table__header th) {
  background: rgba(66, 195, 255, 0.08);
  color: var(--text-secondary);
  letter-spacing: 0.08em;
}

:deep(.user-management__table .el-table__row) {
  background: rgba(6, 22, 44, 0.72);
  transition: background 0.3s ease, transform 0.3s ease;
}

:deep(.user-management__table .el-table__row:hover) {
  background: rgba(66, 195, 255, 0.12);
  transform: translateY(-1px);
}

:deep(.user-management__table .cell) {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 10px 12px;
  gap: 6px;
}

:deep(.user-management__table td.is-center .cell),
:deep(.user-management__table th.is-center .cell) {
  justify-content: center;
}

:deep(.user-management__table td.is-right .cell),
:deep(.user-management__table th.is-right .cell) {
  justify-content: flex-end;
}

.user-management__actions {
  display: flex !important;
  gap: 4px !important;
}

.user-management__footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}

:deep(.el-pagination.is-background .el-pager li.is-active) {
  background: rgba(66, 195, 255, 0.28);
  color: var(--text-primary);
}

:deep(.el-pagination.is-background .el-pager li:not(.is-active)) {
  background: rgba(6, 22, 44, 0.5);
  color: var(--text-secondary);
}

:deep(.el-input__wrapper) {
  background: rgba(6, 22, 44, 0.6);
  border: 1px solid rgba(66, 195, 255, 0.18);
  box-shadow: none;
}

:deep(.el-input__inner) {
  color: var(--text-primary);
}

:deep(.el-dialog) {
  background: rgba(7, 24, 46, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(66, 195, 255, 0.18);
}

:deep(.el-dialog__title) {
  color: var(--text-primary);
  letter-spacing: 0.08em;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 1200px) {
  .user-management__panel {
    padding: 22px 20px;
  }

  .user-management__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar__actions {
    align-self: flex-end;
  }
}
</style> 