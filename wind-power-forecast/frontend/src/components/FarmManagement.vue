<template>
  <div class="farm-management">
    <el-card>
      <template #header>
        <div class="header-row">
          <span>场站管理</span>
          <el-button type="primary" @click="openCreateDialog">新增场站</el-button>
        </div>
      </template>

      <el-table :data="farms" v-loading="loading" border>
        <el-table-column prop="farm_code" label="场站编码" min-width="140" />
        <el-table-column prop="farm_name" label="场站名称" min-width="180" />
        <el-table-column prop="capacity" label="装机容量(MW)" min-width="120" />
        <el-table-column prop="location" label="位置" min-width="160" />
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="handleToggle(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑场站' : '新增场站'" width="520px">
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="场站编码" prop="farm_code">
          <el-input v-model="formData.farm_code" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="场站名称" prop="farm_name">
          <el-input v-model="formData.farm_name" />
        </el-form-item>
        <el-form-item label="装机容量" prop="capacity">
          <el-input-number v-model="formData.capacity" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="formData.location" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="formData.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createFarm, deleteFarm, getFarms, toggleFarm, updateFarm } from '@/api/farmApi'

const loading = ref(false)
const submitting = ref(false)
const farms = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()

const formData = reactive({
  farm_code: '',
  farm_name: '',
  capacity: 0,
  location: '',
  is_active: true
})

const rules = {
  farm_code: [{ required: true, message: '请输入场站编码', trigger: 'blur' }],
  farm_name: [{ required: true, message: '请输入场站名称', trigger: 'blur' }],
  capacity: [{ required: true, message: '请输入装机容量', trigger: 'change' }]
}

function resetForm() {
  formData.farm_code = ''
  formData.farm_name = ''
  formData.capacity = 0
  formData.location = ''
  formData.is_active = true
}

async function fetchFarms() {
  loading.value = true
  try {
    farms.value = await getFarms()
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  formData.farm_code = row.farm_code
  formData.farm_name = row.farm_name
  formData.capacity = Number(row.capacity || 0)
  formData.location = row.location || ''
  formData.is_active = !!row.is_active
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      farm_name: formData.farm_name,
      capacity: Number(formData.capacity || 0),
      location: formData.location,
      is_active: formData.is_active
    }
    if (isEdit.value) {
      await updateFarm(formData.farm_code, payload)
      ElMessage.success('场站更新成功')
    } else {
      await createFarm({ farm_code: formData.farm_code, ...payload })
      ElMessage.success('场站创建成功')
    }
    dialogVisible.value = false
    await fetchFarms()
  } finally {
    submitting.value = false
  }
}

async function handleToggle(row) {
  await toggleFarm(row.farm_code)
  ElMessage.success('场站状态已更新')
  await fetchFarms()
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除场站 ${row.farm_name} (${row.farm_code})？`, '提示', {
    type: 'warning'
  })
  await deleteFarm(row.farm_code)
  ElMessage.success('场站已删除')
  await fetchFarms()
}

onMounted(fetchFarms)
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
