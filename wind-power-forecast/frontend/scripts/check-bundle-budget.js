'use strict'

const fs = require('node:fs')
const path = require('node:path')

const distDir = path.resolve(__dirname, '..', 'dist')

function listAssets(folder, extension) {
  const target = path.join(distDir, folder)
  if (!fs.existsSync(target)) return []
  return fs.readdirSync(target)
    .filter((name) => name.endsWith(extension))
    .map((name) => ({
      name: `${folder}/${name}`,
      size: fs.statSync(path.join(target, name)).size
    }))
}

function findAsset(assets, prefix) {
  const item = assets.find((asset) => path.basename(asset.name).startsWith(prefix))
  if (!item) throw new Error(`构建产物缺少 ${prefix}* 文件`)
  return item
}

function formatKiB(bytes) {
  return `${(bytes / 1024).toFixed(1)} KiB`
}

if (!fs.existsSync(distDir)) {
  throw new Error('缺少 dist 目录，请先执行 npm run build')
}

const jsAssets = listAssets('js', '.js')
const cssAssets = listAssets('css', '.css')
const vendorJs = findAsset(jsAssets, 'chunk-vendors.')
const appJs = findAsset(jsAssets, 'app.')
const vendorCss = findAsset(cssAssets, 'chunk-vendors.')
const appCss = findAsset(cssAssets, 'app.')
const routeAssets = jsAssets.filter((asset) => asset !== vendorJs && asset !== appJs)
const largestRoute = routeAssets.reduce(
  (largest, asset) => asset.size > largest.size ? asset : largest,
  { name: '无异步脚本', size: 0 }
)
const initialSize = vendorJs.size + appJs.size + vendorCss.size + appCss.size

// 预算以本次完成树摇优化后的产物为基线，并保留小幅正常增长空间。
const checks = [
  { label: '首屏静态资源总量', actual: initialSize, limit: 1650 * 1024 },
  { label: '供应商脚本', actual: vendorJs.size, limit: 1250 * 1024 },
  { label: '供应商样式', actual: vendorCss.size, limit: 360 * 1024 },
  { label: `最大异步脚本 ${largestRoute.name}`, actual: largestRoute.size, limit: 600 * 1024 }
]

let failed = false
for (const check of checks) {
  const passed = check.actual <= check.limit
  console.log(`${passed ? '通过' : '超限'} ${check.label}: ${formatKiB(check.actual)} / ${formatKiB(check.limit)}`)
  failed ||= !passed
}

if (failed) {
  process.exitCode = 1
}
