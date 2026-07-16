import axiosInstance from './axios'

import { withLegacyReadFallback } from './legacyFallback.cjs'

export function getFleetMetrics(payload) {
  return withLegacyReadFallback(
    () => axiosInstance.post('/api/v1/power-compare/fleet_metrics', payload),
    () => axiosInstance.post('/power-compare/fleet_metrics', payload)
  )
}

export function getRegulatoryMetrics(payload) {
  return withLegacyReadFallback(
    () => axiosInstance.post('/api/v1/power-compare/regulatory_metrics', payload),
    () => axiosInstance.post('/power-compare/regulatory_metrics', payload)
  )
}

export function getFleetSeries(payload) {
  return withLegacyReadFallback(
    () => axiosInstance.post('/api/v1/power-compare/fleet_series', payload),
    () => axiosInstance.post('/power-compare/fleet_series', payload)
  )
}

export function getPowerCompareData(payload) {
  return withLegacyReadFallback(
    () => axiosInstance.post('/api/v1/power-compare/data', payload, { _silent: true }),
    () => axiosInstance.post('/power-compare/data', payload, { _silent: true })
  )
}
