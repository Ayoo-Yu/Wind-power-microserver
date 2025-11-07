import { ref, computed } from 'vue'
import axiosInstance from '../api/axios'

const STORAGE_KEY = 'selectedWindFarmCode'
const DEFAULT_CODE = 'default-farm'

const windFarms = ref([])
const isLoading = ref(false)
const loadError = ref(null)
const selectedWindFarmCode = ref(localStorage.getItem(STORAGE_KEY) || DEFAULT_CODE)

const findDefaultCandidate = (farms) => {
  if (!Array.isArray(farms) || farms.length === 0) {
    return DEFAULT_CODE
  }
  const active = farms.find(farm => farm.is_active !== false)
  const first = active || farms[0]
  return first.farm_code || first.farm_name || DEFAULT_CODE
}

const setSelectedWindFarm = (code) => {
  const normalized = (code || '').trim() || DEFAULT_CODE
  selectedWindFarmCode.value = normalized
  try {
    localStorage.setItem(STORAGE_KEY, normalized)
  } catch (error) {
    console.warn('无法缓存所选场站:', error)
  }
}

const loadWindFarms = async () => {
  if (isLoading.value) {
    return
  }

  isLoading.value = true
  loadError.value = null

  try {
    const response = await axiosInstance.get('/report/farms')
    const farms = Array.isArray(response.data) ? response.data : []
    windFarms.value = farms

    const codes = farms.map(farm => farm.farm_code || farm.farm_name).filter(Boolean)
    if (!codes.includes(selectedWindFarmCode.value)) {
      setSelectedWindFarm(findDefaultCandidate(farms))
    }
  } catch (error) {
    console.error('加载场站列表失败:', error)
    loadError.value = error
    if (!selectedWindFarmCode.value) {
      setSelectedWindFarm(DEFAULT_CODE)
    }
  } finally {
    isLoading.value = false
  }
}

const getSelectedWindFarmCode = () => selectedWindFarmCode.value || DEFAULT_CODE

const selectedWindFarm = computed({
  get: () => getSelectedWindFarmCode(),
  set: value => setSelectedWindFarm(value),
})

const findWindFarmByCode = (code) => {
  return windFarms.value.find(farm => farm.farm_code === code)
}

export const useWindFarmStore = () => ({
  windFarms,
  isLoading,
  loadError,
  selectedWindFarmCode,
  selectedWindFarm,
  loadWindFarms,
  setSelectedWindFarm,
  findWindFarmByCode,
})

export { getSelectedWindFarmCode }


