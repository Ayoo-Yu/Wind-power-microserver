export function shouldFallbackToLegacy(error) {
  const status = error?.response?.status
  return status === 404 || status === 405
}

export async function withLegacyReadFallback(v1Call, legacyCall) {
  try {
    return await v1Call()
  } catch (error) {
    if (shouldFallbackToLegacy(error)) {
      return legacyCall()
    }
    throw error
  }
}
