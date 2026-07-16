function shouldFallbackToLegacy(error) {
  const status = error && error.response && error.response.status
  return status === 404 || status === 405
}

async function withLegacyReadFallback(v1Call, legacyCall) {
  try {
    return await v1Call()
  } catch (error) {
    if (shouldFallbackToLegacy(error)) {
      return legacyCall()
    }
    throw error
  }
}

module.exports = {
  shouldFallbackToLegacy,
  withLegacyReadFallback
}
