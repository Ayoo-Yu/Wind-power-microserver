<template>
  <div class="user-management page-shell" :class="{ embedded }">
    <div v-if="!embedded" class="page-header">
      <h2>账号管理</h2>
      <p>管理用户基础信息、角色与数据权限（管辖场站）</p>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-input
          v-model="searchQuery"
          placeholder="搜索用户名/姓名/手机号/角色"
          clearable
          class="search-input"
        >
          <template #prefix><el-icon><SearchIcon /></el-icon></template>
        </el-input>
        <div class="toolbar-actions">
          <el-button :icon="Refresh" :loading="loading" @click="fetchData">刷新</el-button>
          <el-button v-if="canManageUsers" type="primary" :icon="Plus" @click="openCreateDialog">添加用户</el-button>
        </div>
      </div>

      <el-table :data="pagedUsers" v-loading="loading" border stripe class="data-table">
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="username" label="用户名" min-width="130" />
        <el-table-column prop="full_name" label="姓名" min-width="120" />
        <el-table-column prop="role.name" label="角色" min-width="130">
          <template #default="{ row }">
            <el-tag :type="isAdminRole(row.role?.name) ? 'danger' : 'info'" effect="plain">
              {{ row.role?.name || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="联系电话" min-width="150" />
        <el-table-column label="管辖场站" min-width="200">
          <template #default="{ row }">
            <span v-if="isAllStations(row.stations)">全部场站</span>
            <span v-else-if="row.stations.length <= 2">{{ row.stations.join('、') || '-' }}</span>
            <el-tooltip v-else placement="top" :content="row.stations.join('、')">
              <span>{{ row.stations.length }}个场站（悬浮查看）</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" effect="plain">
              {{ row.is_active ? '启用' : '冻结' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" min-width="180">
          <template #default="{ row }">{{ formatDate(row.last_login) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="194" fixed="right">
          <template #default="{ row }">
            <el-button-group v-if="canManageUsers">
              <el-tooltip content="编辑">
                <el-button size="small" type="primary" :icon="Edit" @click="openEditDialog(row)" />
              </el-tooltip>
              <el-tooltip :content="row.is_active ? '冻结账号' : '解冻账号'">
                <el-button
                  size="small"
                  type="warning"
                  :icon="Lock"
                  @click="toggleStatus(row)"
                />
              </el-tooltip>
              <el-tooltip content="重置密码">
                <el-button size="small" type="info" :icon="Key" @click="openResetDialog(row)" />
              </el-tooltip>
              <el-tooltip content="删除">
                <el-button size="small" type="danger" :icon="Delete" @click="removeUser(row)" />
              </el-tooltip>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="filteredUsers.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>

    <el-dialog
      v-model="showUserDialog"
      :title="isEdit ? '编辑用户' : '添加用户'"
      width="620px"
      destroy-on-close
    >
      <el-form ref="userFormRef" :model="userForm" :rules="rules" label-width="108px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model.trim="userForm.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name">
          <el-input v-model.trim="userForm.full_name" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model.trim="userForm.phone" maxlength="20" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model.trim="userForm.email" />
        </el-form-item>
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="userForm.role_id" style="width: 100%" filterable>
            <el-option v-for="item in roles" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="管辖场站" prop="stations">
          <el-select
            v-model="userForm.stations"
            style="width: 100%"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            @change="normalizeStationSelection"
          >
            <el-option label="全部场站" value="__ALL__" />
            <el-option v-for="farm in farmOptions" :key="farm.code" :label="farm.name" :value="farm.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号状态" prop="is_active">
          <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="冻结" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUserDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitUser">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showResetDialog" title="重置密码" width="420px" destroy-on-close>
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="96px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="resetForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="resetForm.confirmPassword" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResetDialog = false">取消</el-button>
        <el-button type="primary" :loading="resetting" @click="submitResetPassword">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Key, Lock, Plus, Refresh, Search as SearchIcon } from '@element-plus/icons-vue'
import {
  createUser,
  deleteUser,
  deleteUserMeta,
  getRoles,
  getUsers,
  getUsersMeta,
  resetUserPassword,
  updateUserMeta,
  updateUser
} from '../api/auth'
import farmService from '../utils/farmService'
import { appendAuditLog } from '../utils/auditLogStore'
import { getStoredUser, hasPermission } from '../utils/permission'

const EMPTY_USER_FORM = () => ({
  id: null,
  username: '',
  password: '',
  full_name: '',
  phone: '',
  email: '',
  role_id: undefined,
  stations: ['__ALL__'],
  is_active: true
})

export default {
  name: 'UserManagement',
  components: { SearchIcon },
  props: {
    embedded: {
      type: Boolean,
      default: false
    }
  },
  setup() {
    const loading = ref(false)
    const submitting = ref(false)
    const resetting = ref(false)
    const users = ref([])
    const roles = ref([])
    const farmOptions = ref([])
    const searchQuery = ref('')
    const currentPage = ref(1)
    const pageSize = ref(10)

    const showUserDialog = ref(false)
    const showResetDialog = ref(false)
    const isEdit = ref(false)
    const currentUserId = ref(null)
    const userFormRef = ref(null)
    const resetFormRef = ref(null)

    const userForm = reactive(EMPTY_USER_FORM())
    const resetForm = reactive({
      password: '',
      confirmPassword: ''
    })

    const currentUser = computed(() => getStoredUser() || {})
    const canManageUsers = computed(() => hasPermission(currentUser.value, 'manage_users'))

    const rules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 8, message: '密码至少 8 位', trigger: 'blur' }
      ],
      full_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
      phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
      email: [
        { required: true, message: '请输入邮箱', trigger: 'blur' },
        { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
      ],
      role_id: [{ required: true, message: '请选择角色', trigger: 'change' }],
      stations: [{ required: true, type: 'array', min: 1, message: '请选择管辖场站', trigger: 'change' }]
    }

    const resetRules = {
      password: [
        { required: true, message: '请输入新密码', trigger: 'blur' },
        { min: 8, message: '密码至少 8 位', trigger: 'blur' }
      ],
      confirmPassword: [
        { required: true, message: '请确认密码', trigger: 'blur' },
        {
          validator: (rule, value, callback) => {
            if (value !== resetForm.password) {
              callback(new Error('两次密码输入不一致'))
              return
            }
            callback()
          },
          trigger: 'blur'
        }
      ]
    }

    const filteredUsers = computed(() => {
      const q = searchQuery.value.trim().toLowerCase()
      if (!q) return users.value
      return users.value.filter(item => {
        return [
          item.username,
          item.full_name,
          item.phone,
          item.email,
          item.role?.name
        ].some(field => String(field || '').toLowerCase().includes(q))
      })
    })

    const pagedUsers = computed(() => {
      const start = (currentPage.value - 1) * pageSize.value
      return filteredUsers.value.slice(start, start + pageSize.value)
    })

    const isAdminRole = (roleName) => String(roleName || '').includes('管理员')
    const isAllStations = (stations = []) => Array.isArray(stations) && stations.includes('__ALL__')
    const formatDate = (value) => (value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-')

    const normalizeStationSelection = (selected) => {
      if (!Array.isArray(selected)) return
      if (selected.includes('__ALL__') && selected.length > 1) {
        userForm.stations = ['__ALL__']
      }
    }

    const hydrateUserWithMeta = (user, metaMap = new Map()) => {
      const meta = metaMap.get(user.username) || {}
      return {
        ...user,
        phone: user.phone || meta.phone || '',
        stations: Array.isArray(user.stations) && user.stations.length > 0
          ? user.stations
          : Array.isArray(meta.stations) && meta.stations.length > 0
            ? meta.stations
            : ['__ALL__']
      }
    }

    const fetchData = async () => {
      loading.value = true
      try {
        const [userData, roleData, farms, userMetaRows] = await Promise.all([
          getUsers(),
          getRoles(),
          farmService.loadAvailableFarms(true),
          getUsersMeta()
        ])
        const normalizedUsers = Array.isArray(userData) ? userData : userData?.users || []
        const userMetaMap = new Map(
          (Array.isArray(userMetaRows) ? userMetaRows : [])
            .filter(item => item?.username)
            .map(item => [item.username, item])
        )
        users.value = normalizedUsers.map(item => hydrateUserWithMeta(item, userMetaMap))
        roles.value = Array.isArray(roleData) ? roleData : []
        farmOptions.value = Array.isArray(farms) ? farms : []
      } catch (error) {
        ElMessage.error(error?.response?.data?.message || '加载用户数据失败')
      } finally {
        loading.value = false
      }
    }

    const openCreateDialog = () => {
      isEdit.value = false
      Object.assign(userForm, EMPTY_USER_FORM())
      showUserDialog.value = true
    }

    const openEditDialog = (row) => {
      isEdit.value = true
      currentUserId.value = row.id
      Object.assign(userForm, {
        id: row.id,
        username: row.username,
        password: '',
        full_name: row.full_name || '',
        phone: row.phone || '',
        email: row.email || '',
        role_id: row.role?.id,
        stations: row.stations?.length ? [...row.stations] : ['__ALL__'],
        is_active: !!row.is_active
      })
      showUserDialog.value = true
    }

    const submitUser = async () => {
      if (!userFormRef.value) return
      await userFormRef.value.validate(async (valid) => {
        if (!valid) return
        submitting.value = true
        try {
          let targetUserId = currentUserId.value
          if (isEdit.value) {
            await updateUser(currentUserId.value, {
              full_name: userForm.full_name,
              email: userForm.email,
              role_id: userForm.role_id,
              is_active: userForm.is_active
            })
            appendAuditLog({
              module: '用户管理',
              operationType: '修改',
              details: `修改用户[${userForm.username}]信息`,
              result: '成功'
            })
          } else {
            const created = await createUser({
              username: userForm.username,
              password: userForm.password,
              full_name: userForm.full_name,
              email: userForm.email,
              role_id: userForm.role_id,
              is_active: userForm.is_active
            })
            targetUserId = created?.user_id || null
            appendAuditLog({
              module: '用户管理',
              operationType: '新增',
              details: `新增用户[${userForm.username}]`,
              result: '成功'
            })
          }

          if (targetUserId) {
            await updateUserMeta(targetUserId, {
              phone: userForm.phone,
              stations: userForm.stations
            })
          }

          ElMessage.success(isEdit.value ? '用户更新成功' : '用户创建成功')
          showUserDialog.value = false
          await fetchData()
        } catch (error) {
          appendAuditLog({
            module: '用户管理',
            operationType: isEdit.value ? '修改' : '新增',
            details: `操作用户[${userForm.username}]`,
            result: '失败'
          })
          ElMessage.error(error?.response?.data?.message || '提交失败')
        } finally {
          submitting.value = false
        }
      })
    }

    const openResetDialog = (row) => {
      currentUserId.value = row.id
      resetForm.password = ''
      resetForm.confirmPassword = ''
      showResetDialog.value = true
    }

    const submitResetPassword = async () => {
      if (!resetFormRef.value) return
      await resetFormRef.value.validate(async (valid) => {
        if (!valid) return
        resetting.value = true
        try {
          await resetUserPassword(currentUserId.value, resetForm.password)
          appendAuditLog({
            module: '用户管理',
            operationType: '重置密码',
            details: `重置用户ID[${currentUserId.value}]密码`,
            result: '成功'
          })
          ElMessage.success('密码重置成功')
          showResetDialog.value = false
        } catch (error) {
          appendAuditLog({
            module: '用户管理',
            operationType: '重置密码',
            details: `重置用户ID[${currentUserId.value}]密码`,
            result: '失败'
          })
          ElMessage.error(error?.response?.data?.message || '重置密码失败')
        } finally {
          resetting.value = false
        }
      })
    }

    const toggleStatus = async (row) => {
      const nextActive = !row.is_active
      try {
        await ElMessageBox.confirm(
          `确认${nextActive ? '启用' : '冻结'}用户 [${row.username}] 吗？`,
          '提示',
          { type: 'warning' }
        )
        await updateUser(row.id, { is_active: nextActive })
        appendAuditLog({
          module: '用户管理',
          operationType: nextActive ? '解冻' : '冻结',
          details: `${nextActive ? '解冻' : '冻结'}用户[${row.username}]`,
          result: '成功'
        })
        ElMessage.success('状态更新成功')
        await fetchData()
      } catch (error) {
        if (error !== 'cancel') {
          appendAuditLog({
            module: '用户管理',
            operationType: nextActive ? '解冻' : '冻结',
            details: `${nextActive ? '解冻' : '冻结'}用户[${row.username}]`,
            result: '失败'
          })
          ElMessage.error(error?.response?.data?.message || '状态更新失败')
        }
      }
    }

    const removeUser = async (row) => {
      try {
        await ElMessageBox.confirm(`确认删除用户 [${row.username}] 吗？`, '警告', { type: 'warning' })
        await deleteUser(row.id)
        await deleteUserMeta(row.id)
        appendAuditLog({
          module: '用户管理',
          operationType: '删除',
          details: `删除用户[${row.username}]`,
          result: '成功'
        })
        ElMessage.success('删除成功')
        await fetchData()
      } catch (error) {
        if (error !== 'cancel') {
          appendAuditLog({
            module: '用户管理',
            operationType: '删除',
            details: `删除用户[${row.username}]`,
            result: '失败'
          })
          ElMessage.error(error?.response?.data?.message || '删除失败')
        }
      }
    }

    onMounted(fetchData)

    return {
      loading,
      submitting,
      resetting,
      users,
      roles,
      farmOptions,
      searchQuery,
      currentPage,
      pageSize,
      showUserDialog,
      showResetDialog,
      isEdit,
      userForm,
      resetForm,
      rules,
      resetRules,
      userFormRef,
      resetFormRef,
      filteredUsers,
      pagedUsers,
      canManageUsers,
      isAdminRole,
      isAllStations,
      formatDate,
      normalizeStationSelection,
      fetchData,
      openCreateDialog,
      openEditDialog,
      submitUser,
      openResetDialog,
      submitResetPassword,
      toggleStatus,
      removeUser,
      Plus,
      Edit,
      Refresh,
      Delete,
      Lock,
      Key
    }
  }
}
</script>

<style scoped>
.user-management {
  min-height: 100%;
  padding: 20px;
}

.user-management.embedded {
  padding: 0;
}

.page-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.page-header p {
  margin: 8px 0 14px;
  color: var(--text-secondary);
}

.card-shell {
  background: var(--surface);
  border: 1px solid var(--border-color);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 12px;
}

.search-input {
  max-width: 380px;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.data-table {
  margin-top: 8px;
}

.data-table :deep(.el-table__header th) {
  color: var(--text-secondary);
  background: var(--table-header-bg) !important;
  border-bottom: 1px solid var(--table-border);
}

.pager {
  margin-top: 14px;
  display: flex;
  justify-content: center;
}

@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input {
    max-width: none;
  }

  .toolbar-actions {
    justify-content: flex-end;
  }
}
</style>
