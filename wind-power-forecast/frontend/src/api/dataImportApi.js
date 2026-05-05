import axiosInstance from './axios'

// === 实测数据 ===

export function uploadActualPower({ file, farmCode, strategy, onUploadProgress, signal }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('table_name', 'actual_power')
  formData.append('farm_code', farmCode)
  formData.append('strategy', strategy)

  return axiosInstance.post('/operational/api/upload_operational_csv', formData, {
    timeout: 600000,
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
    signal
  })
}

// === 气象预测数据 (ECMWF 格点) ===

export function uploadActualPowerAsync({ file, farmCode, strategy, onUploadProgress, signal }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('farm_code', farmCode)
  formData.append('strategy', strategy)

  return axiosInstance.post('/operational/api/upload_actual_power_async', formData, {
    timeout: 600000,
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
    signal
  })
}

export function getImportJob(jobId, { signal } = {}) {
  return axiosInstance.get(`/operational/api/import_jobs/${jobId}`, {
    timeout: 10000,
    params: { t: Date.now() },
    headers: { 'Cache-Control': 'no-cache' },
    _silent: true,
    signal
  })
}

export function getEcmwfGridImportJob(jobId, { signal } = {}) {
  return axiosInstance.get(`/api/ecmwf/grid/import_jobs/${jobId}`, {
    timeout: 10000,
    params: { t: Date.now() },
    headers: { 'Cache-Control': 'no-cache' },
    _silent: true,
    signal
  })
}

export function uploadEcmwfGridAsync({ file, farmCode, onUploadProgress, signal }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('farm_code', farmCode)

  return axiosInstance.post('/api/ecmwf/grid/ingest_async', formData, {
    timeout: 600000,
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
    signal
  })
}

// === 气象预测数据 (train_pre_short / train_pre_middle) ===

export function uploadFeatureCsv({ file, farmCode, tableName, onUploadProgress, signal }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('farm_code', farmCode)
  formData.append('table_name', tableName)

  return axiosInstance.post('/api/upload_feature_csv', formData, {
    timeout: 600000,
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
    signal
  })
}

// === E text Pipeline ===

export function getEtextPipelineConfig() {
  return axiosInstance.get('/api/etext_pipeline/config')
}

export function updateEtextPipelineConfig(config) {
  return axiosInstance.put('/api/etext_pipeline/config', config)
}

export function triggerEtextPipeline() {
  return axiosInstance.post('/api/etext_pipeline/trigger', null, {
    timeout: 60000
  })
}

export function getEtextTriggerStatus(jobId) {
  return axiosInstance.get(`/api/etext_pipeline/trigger/${jobId}`, {
    timeout: 10000
  })
}
