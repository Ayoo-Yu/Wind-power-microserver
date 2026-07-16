<template>
  <div class="access-management page-shell">
    <div class="page-header">
      <div>
        <h2>账号与权限</h2>
        <p>在一个入口维护登录账号、场站范围和角色权限矩阵。</p>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="access-tabs">
      <el-tab-pane v-if="canManageUsers" label="账号管理" name="users">
        <UserManagement v-if="activeTab === 'users'" embedded />
      </el-tab-pane>
      <el-tab-pane v-if="canManageRoles" label="角色权限" name="roles">
        <RoleManagement v-if="activeTab === 'roles'" embedded />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import UserManagement from './UserManagement.vue'
import RoleManagement from './RoleManagement.vue'
import { getStoredUser, hasPermission } from '../utils/permission'

const route = useRoute()
const router = useRouter()
const currentUser = computed(() => getStoredUser() || {})
const canManageUsers = computed(() => hasPermission(currentUser.value, 'manage_users'))
const canManageRoles = computed(() => hasPermission(currentUser.value, 'manage_roles'))

const resolveTab = (requestedTab) => {
  if (requestedTab === 'roles' && canManageRoles.value) return 'roles'
  if (canManageUsers.value) return 'users'
  return 'roles'
}

const activeTab = ref(resolveTab(route.query.tab))

watch(() => route.query.tab, (requestedTab) => {
  const nextTab = resolveTab(requestedTab)
  if (activeTab.value !== nextTab) activeTab.value = nextTab
})

watch(activeTab, (nextTab) => {
  if (route.query.tab === nextTab) return
  router.replace({ path: '/users', query: { ...route.query, tab: nextTab } })
})
</script>

<style scoped>
.access-management {
  min-height: 100%;
  padding: 20px;
}

.page-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.page-header p {
  margin: 8px 0 16px;
  color: var(--text-secondary);
}

.access-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.access-tabs :deep(.el-tabs__item) {
  min-width: 108px;
  color: var(--text-secondary);
}

.access-tabs :deep(.el-tabs__item.is-active) {
  color: var(--accent);
}
</style>
