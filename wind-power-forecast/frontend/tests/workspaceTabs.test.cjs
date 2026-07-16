const test = require('node:test')
const assert = require('node:assert/strict')

let closeWorkspaceTab
let restoreWorkspaceTabs
let upsertWorkspaceTab

test.before(async () => {
  const module = await import('../src/utils/workspaceTabs.mjs')
  closeWorkspaceTab = module.closeWorkspaceTab
  restoreWorkspaceTabs = module.restoreWorkspaceTabs
  upsertWorkspaceTab = module.upsertWorkspaceTab
})

const route = (name, path, title, extra = {}) => ({
  name,
  path,
  fullPath: extra.fullPath || path,
  meta: { title, ...(extra.meta || {}) }
})

test('同一业务页面只保留一个页签并更新最新访问地址', () => {
  const first = route('UserManagement', '/users', '账号与权限', { fullPath: '/users?tab=users' })
  const second = route('UserManagement', '/users', '账号与权限', { fullPath: '/users?tab=roles' })

  const tabs = upsertWorkspaceTab(upsertWorkspaceTab([], first), second)

  assert.equal(tabs.length, 1)
  assert.equal(tabs[0].fullPath, '/users?tab=roles')
})

test('首页页签固定且无法关闭', () => {
  const home = route('HomePage', '/', '首页总览', { meta: { affix: true } })
  const tabs = upsertWorkspaceTab([], home)
  const result = closeWorkspaceTab(tabs, 'HomePage', 'HomePage')

  assert.equal(tabs[0].closable, false)
  assert.deepEqual(result.tabs, tabs)
  assert.equal(result.nextTab, null)
})

test('关闭活动页签后优先切换到右侧相邻页签', () => {
  const home = route('HomePage', '/', '首页总览', { meta: { affix: true } })
  const predict = route('AutoPredict', '/autopredict', '预测任务')
  const compare = route('PowerCompare', '/powercompare', '预测曲线与考核')
  const tabs = [home, predict, compare].reduce(upsertWorkspaceTab, [])

  const result = closeWorkspaceTab(tabs, 'AutoPredict', 'AutoPredict')

  assert.deepEqual(result.tabs.map(tab => tab.key), ['HomePage', 'PowerCompare'])
  assert.equal(result.nextTab.key, 'PowerCompare')
})

test('刷新恢复时忽略已失效的路由记录', () => {
  const stored = [
    { path: '/autopredict', fullPath: '/autopredict' },
    { path: '/removed-page', fullPath: '/removed-page' }
  ]
  const routes = new Map([
    ['/autopredict', route('AutoPredict', '/autopredict', '预测任务')]
  ])

  const tabs = restoreWorkspaceTabs(stored, target => routes.get(target) || { path: target })

  assert.deepEqual(tabs.map(tab => tab.key), ['AutoPredict'])
})
