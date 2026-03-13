<template>
  <div class="role-management page-shell">
    <div class="page-header">
      <h2>角色管理</h2>
      <p>配置角色权限矩阵，覆盖左侧菜单与关键操作按钮</p>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-button :icon="Refresh" :loading="loading" @click="fetchRoles">刷新</el-button>
          <el-button v-if="canManageRoles" :icon="MagicStick" @click="initPresetRoles">初始化预设角色</el-button>
        </div>
        <el-button v-if="canManageRoles" type="primary" :icon="Plus" @click="openCreateDialog">新增角色</el-button>
      </div>

      <el-table :data="roles" v-loading="loading" border stripe>
        <el-table-column prop="name" label="角色名称" min-width="140" />
        <el-table-column prop="description" label="说明" min-width="220" />
        <el-table-column label="权限数量" width="110">
          <template #default="{ row }">{{ normalizePermissions(row.permissions).length }}</template>
        </el-table-column>
        <el-table-column label="权限预览" min-width="360">
          <template #default="{ row }">
            <div class="permission-tags">
              <el-tag v-for="perm in normalizePermissions(row.permissions).slice(0, 6)" :key="perm" effect="plain">
                {{ getPermissionLabel(perm) }}
              </el-tag>
              <el-tag v-if="normalizePermissions(row.permissions).length > 6" type="info" effect="plain">
                +{{ normalizePermissions(row.permissions).length - 6 }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="canManageRoles" label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" type="primary" :icon="Edit" @click="openEditDialog(row)" />
              <el-button size="small" type="danger" :icon="Delete" @click="removeRole(row)" />
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showRoleDialog" :title="isEdit ? '编辑角色' : '新增角色'" width="760px" destroy-on-close>
      <el-form ref="roleFormRef" :model="roleForm" :rules="rules" label-width="96px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model.trim="roleForm.name" :disabled="isEdit && isBuiltinRole(roleForm.name)" />
        </el-form-item>
        <el-form-item label="角色说明" prop="description">
          <el-input v-model.trim="roleForm.description" type="textarea" rows="2" />
        </el-form-item>
        <el-form-item label="权限矩阵" prop="permissions">
          <div class="perm-tree-wrap">
            <el-tree
              ref="permissionTreeRef"
              node-key="id"
              show-checkbox
              default-expand-all
              :check-strictly="false"
              :props="{ label: 'label', children: 'children' }"
              :data="permissionTree"
              @check="syncCheckedPermissions"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRoleDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRole">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { computed, nextTick, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, MagicStick, Plus, Refresh } from '@element-plus/icons-vue'
import { createRole, deleteRole, getRoles, updateRole } from '../api/auth'
import { ALL_PERMISSION_KEYS, PERMISSION_TREE, ROLE_PRESETS } from '../constants/permissions'
import { appendAuditLog } from '../utils/auditLogStore'
import { getStoredUser, hasPermission } from '../utils/permission'

export default {
  name: 'RoleManagement',
  setup() {
    const loading = ref(false)
    const submitting = ref(false)
    const roles = ref([])
    const showRoleDialog = ref(false)
    const isEdit = ref(false)
    const roleFormRef = ref(null)
    const permissionTreeRef = ref(null)

    const roleForm = reactive({
      id: null,
      name: '',
      description: '',
      permissions: []
    })

    const currentUser = computed(() => getStoredUser() || {})
    const canManageRoles = computed(() => hasPermission(currentUser.value, 'manage_roles'))

    const permissionTree = PERMISSION_TREE
    const permissionLabelMap = ALL_PERMISSION_KEYS.reduce((acc, key) => {
      const item = permissionTree.flatMap(group => group.children).find(node => node.id === key)
      acc[key] = item?.label || key
      return acc
    }, {})

    const rules = {
      name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
      permissions: [{ type: 'array', min: 1, required: true, message: '请至少勾选一个权限', trigger: 'change' }]
    }

    const normalizePermissions = (value) => {
      if (Array.isArray(value)) return value
      if (value && Array.isArray(value.permissions)) return value.permissions
      return []
    }

    const getPermissionLabel = (key) => permissionLabelMap[key] || key
    const isBuiltinRole = (name) => ['系统管理员', 'admin', 'Administrator'].includes(String(name || ''))

    const fetchRoles = async () => {
      loading.value = true
      try {
        const data = await getRoles()
        roles.value = Array.isArray(data) ? data : []
      } catch (error) {
        ElMessage.error(error?.response?.data?.message || '加载角色失败')
      } finally {
        loading.value = false
      }
    }

    const openCreateDialog = () => {
      isEdit.value = false
      Object.assign(roleForm, { id: null, name: '', description: '', permissions: [] })
      showRoleDialog.value = true
      nextTick(() => permissionTreeRef.value?.setCheckedKeys([]))
    }

    const openEditDialog = (row) => {
      isEdit.value = true
      Object.assign(roleForm, {
        id: row.id,
        name: row.name || '',
        description: row.description || '',
        permissions: [...normalizePermissions(row.permissions)]
      })
      showRoleDialog.value = true
      nextTick(() => permissionTreeRef.value?.setCheckedKeys(roleForm.permissions))
    }

    const syncCheckedPermissions = () => {
      const checked = permissionTreeRef.value?.getCheckedKeys() || []
      roleForm.permissions = checked.filter(key => ALL_PERMISSION_KEYS.includes(key))
    }

    const submitRole = async () => {
      syncCheckedPermissions()
      if (!roleFormRef.value) return
      await roleFormRef.value.validate(async (valid) => {
        if (!valid) return
        submitting.value = true
        try {
          const payload = {
            name: roleForm.name,
            description: roleForm.description,
            permissions: roleForm.permissions
          }
          if (isEdit.value) {
            await updateRole(roleForm.id, payload)
            appendAuditLog({
              module: '角色管理',
              operationType: '修改',
              details: `修改角色[${roleForm.name}]权限`,
              result: '成功'
            })
          } else {
            await createRole(payload)
            appendAuditLog({
              module: '角色管理',
              operationType: '新增',
              details: `新增角色[${roleForm.name}]`,
              result: '成功'
            })
          }
          ElMessage.success(isEdit.value ? '角色更新成功' : '角色创建成功')
          showRoleDialog.value = false
          await fetchRoles()
        } catch (error) {
          appendAuditLog({
            module: '角色管理',
            operationType: isEdit.value ? '修改' : '新增',
            details: `操作角色[${roleForm.name}]`,
            result: '失败'
          })
          ElMessage.error(error?.response?.data?.message || '保存角色失败')
        } finally {
          submitting.value = false
        }
      })
    }

    const removeRole = async (row) => {
      try {
        await ElMessageBox.confirm(`确认删除角色 [${row.name}] 吗？`, '警告', { type: 'warning' })
        await deleteRole(row.id)
        appendAuditLog({
          module: '角色管理',
          operationType: '删除',
          details: `删除角色[${row.name}]`,
          result: '成功'
        })
        ElMessage.success('删除成功')
        await fetchRoles()
      } catch (error) {
        if (error !== 'cancel') {
          appendAuditLog({
            module: '角色管理',
            operationType: '删除',
            details: `删除角色[${row.name}]`,
            result: '失败'
          })
          ElMessage.error(error?.response?.data?.message || '删除角色失败')
        }
      }
    }

    const initPresetRoles = async () => {
      const existingNames = new Set(roles.value.map(item => item.name))
      const missing = ROLE_PRESETS.filter(item => !existingNames.has(item.name))
      if (missing.length === 0) {
        ElMessage.info('预设角色已存在，无需初始化')
        return
      }
      loading.value = true
      try {
        for (const item of missing) {
          await createRole({
            name: item.name,
            description: item.description,
            permissions: item.permissions
          })
          appendAuditLog({
            module: '角色管理',
            operationType: '新增',
            details: `初始化预设角色[${item.name}]`,
            result: '成功'
          })
        }
        ElMessage.success(`已初始化 ${missing.length} 个预设角色`)
        await fetchRoles()
      } catch (error) {
        ElMessage.error(error?.response?.data?.message || '初始化角色失败')
      } finally {
        loading.value = false
      }
    }

    onMounted(fetchRoles)

    return {
      loading,
      submitting,
      roles,
      showRoleDialog,
      isEdit,
      roleForm,
      roleFormRef,
      permissionTreeRef,
      permissionTree,
      rules,
      canManageRoles,
      normalizePermissions,
      getPermissionLabel,
      isBuiltinRole,
      fetchRoles,
      openCreateDialog,
      openEditDialog,
      syncCheckedPermissions,
      submitRole,
      removeRole,
      initPresetRoles,
      Plus,
      Edit,
      Delete,
      Refresh,
      MagicStick
    }
  }
}
</script>

<style scoped>
.role-management {
  min-height: 100%;
  padding: 20px;
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
  background: rgba(6, 21, 34, 0.86);
  border: 1px solid rgba(130, 178, 212, 0.2);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.permission-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.perm-tree-wrap {
  width: 100%;
  max-height: 360px;
  overflow: auto;
  border: 1px solid rgba(130, 178, 212, 0.28);
  border-radius: 8px;
  padding: 8px;
}
</style>
