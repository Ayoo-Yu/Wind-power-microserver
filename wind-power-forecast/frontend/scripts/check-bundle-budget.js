'use strict'

const fs = require('node:fs')
const path = require('node:path')

const distDir = path.resolve(__dirname, '..', 'dist')
const indexPath = path.join(distDir, 'index.html')

function listAssets(folder) {
  if (!fs.existsSync(folder)) return []
  return fs.readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(folder, entry.name)
    if (entry.isDirectory()) return listAssets(absolutePath)
    if (!entry.name.endsWith('.js') && !entry.name.endsWith('.css')) return []
    return [{
      name: path.relative(distDir, absolutePath).replace(/\\/g, '/'),
      size: fs.statSync(absolutePath).size
    }]
  })
}

function largestAsset(assets, emptyName) {
  return assets.reduce(
    (largest, asset) => asset.size > largest.size ? asset : largest,
    { name: emptyName, size: 0 }
  )
}

function formatKiB(bytes) {
  return `${(bytes / 1024).toFixed(1)} KiB`
}

if (!fs.existsSync(indexPath)) {
  throw new Error('缺少 dist/index.html，请先执行 npm run build')
}

const assets = listAssets(path.join(distDir, 'assets'))
const assetByName = new Map(assets.map((asset) => [asset.name, asset]))
const html = fs.readFileSync(indexPath, 'utf8')
const initialNames = new Set(
  [...html.matchAll(/(?:src|href)=["']\/?([^"']+\.(?:js|css))(?:\?[^"']*)?["']/g)]
    .map((match) => match[1])
)
const initialAssets = [...initialNames].map((name) => {
  const asset = assetByName.get(name)
  if (!asset) throw new Error(`首页引用的构建产物不存在: ${name}`)
  return asset
})
const initialJs = initialAssets.filter((asset) => asset.name.endsWith('.js'))
const cssAssets = assets.filter((asset) => asset.name.endsWith('.css'))
const initialJsNames = new Set(initialJs.map((asset) => asset.name))
const asyncJs = assets.filter((asset) => asset.name.endsWith('.js') && !initialJsNames.has(asset.name))
const largestInitialJs = largestAsset(initialJs, '无首屏脚本')
const largestCss = largestAsset(cssAssets, '无样式文件')
const largestAsyncJs = largestAsset(asyncJs, '无异步脚本')
const initialSize = initialAssets.reduce((sum, asset) => sum + asset.size, 0)

// 预算以 Vite 迁移和树摇优化后的产物为基线，并保留小幅正常增长空间。
const checks = [
  { label: '首屏静态资源总量', actual: initialSize, limit: 1500 * 1024 },
  { label: `最大首屏脚本 ${largestInitialJs.name}`, actual: largestInitialJs.size, limit: 800 * 1024 },
  { label: `最大样式 ${largestCss.name}`, actual: largestCss.size, limit: 380 * 1024 },
  { label: `最大异步脚本 ${largestAsyncJs.name}`, actual: largestAsyncJs.size, limit: 625 * 1024 }
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
