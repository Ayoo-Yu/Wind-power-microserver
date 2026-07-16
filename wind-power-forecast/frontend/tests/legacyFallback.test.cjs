const test = require('node:test')
const assert = require('node:assert/strict')

const {
  shouldFallbackToLegacy,
  withLegacyReadFallback
} = require('../src/api/legacyFallback.cjs')

test('旧接口只在服务端明确表示路由不兼容时启用', async () => {
  assert.equal(shouldFallbackToLegacy({ response: { status: 404 } }), true)
  assert.equal(shouldFallbackToLegacy({ response: { status: 405 } }), true)
  assert.equal(shouldFallbackToLegacy({ response: { status: 500 } }), false)
  assert.equal(shouldFallbackToLegacy(new Error('network timeout')), false)

  let legacyCalls = 0
  const result = await withLegacyReadFallback(
    async () => Promise.reject({ response: { status: 404 } }),
    async () => {
      legacyCalls += 1
      return 'legacy'
    }
  )

  assert.equal(result, 'legacy')
  assert.equal(legacyCalls, 1)
})

test('响应未知的网络故障不会触发第二次请求', async () => {
  const networkError = new Error('network timeout')
  let legacyCalls = 0

  await assert.rejects(
    withLegacyReadFallback(
      async () => Promise.reject(networkError),
      async () => {
        legacyCalls += 1
      }
    ),
    networkError
  )

  assert.equal(legacyCalls, 0)
})
