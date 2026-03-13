const STORAGE_KEY = 'data_quality_markers'

export function listDataQualityMarkers() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    console.warn('读取数据质量标记失败', error)
    return []
  }
}

export function saveDataQualityMarkers(markers = []) {
  const safeMarkers = Array.isArray(markers) ? markers : []
  localStorage.setItem(STORAGE_KEY, JSON.stringify(safeMarkers))
}

export function appendDataQualityMarker(marker) {
  const markers = listDataQualityMarkers()
  const next = [marker, ...markers]
  saveDataQualityMarkers(next)
  return next
}
