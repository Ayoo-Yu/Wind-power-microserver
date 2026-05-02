// frontend/vue.config.js
const BACKEND_PORT = process.env.MAIN_BACKEND_PORT || process.env.VUE_APP_MAIN_BACKEND_PORT || '5000'

function attachJsonBodyForward(proxy) {
  proxy.on('proxyReq', (proxyReq, req, res) => {
    if (req.body) {
      const bodyData = JSON.stringify(req.body)
      proxyReq.setHeader('Content-Type', 'application/json')
      proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData))
      proxyReq.write(bodyData)
    }
  })
}

const proxyTarget = {
  target: `http://127.0.0.1:${BACKEND_PORT}`,
  ws: false,
  changeOrigin: true,
  secure: false,
  configure: (proxy) => attachJsonBodyForward(proxy)
}

const proxyTargetWs = {
  ...proxyTarget,
  ws: true
}

module.exports = {
  css: {
    loaderOptions: {
      sass: {
        api: 'modern'
      }
    }
  },
  devServer: {
    proxy: {
      '/api/v1/autopredict': proxyTarget,
      '/api/v1': proxyTarget,
      '/api/(start|start_ultra|stop|status|tasks|logs|save|resurrect|clearsave|delete|schedule|script_info|task_status)': proxyTarget,
      '/get-daily-metrics': proxyTarget,
      '/api': proxyTargetWs,
      '/scada/': proxyTarget,
      '/operational': proxyTarget
    }
  }
}
