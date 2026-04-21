// frontend/vue.config.js
const MAIN_BACKEND_PORT = process.env.MAIN_BACKEND_PORT || process.env.VUE_APP_MAIN_BACKEND_PORT || '5000'
const AUTO_BACKEND_PORT = process.env.AUTO_BACKEND_PORT || process.env.VUE_APP_AUTO_BACKEND_PORT || '5001'

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

module.exports = {
  devServer: {
    proxy: {
      '/api/v1/autopredict': {
        target: `http://127.0.0.1:${AUTO_BACKEND_PORT}`,
        ws: false,
        changeOrigin: true,
        secure: false,
        configure: (proxy) => attachJsonBodyForward(proxy)
      },

      '/api/v1': {
        target: `http://127.0.0.1:${MAIN_BACKEND_PORT}`,
        ws: false,
        changeOrigin: true,
        secure: false,
        configure: (proxy) => attachJsonBodyForward(proxy)
      },

      '/api/(start|start_ultra|stop|status|tasks|logs|save|resurrect|clearsave|delete|schedule|script_info|task_status)': {
        target: `http://127.0.0.1:${AUTO_BACKEND_PORT}`,
        ws: false,
        changeOrigin: true,
        secure: false,
        configure: (proxy) => attachJsonBodyForward(proxy)
      },

      '/get-daily-metrics': {
        target: `http://127.0.0.1:${AUTO_BACKEND_PORT}`,
        ws: false,
        changeOrigin: true,
        secure: false,
        configure: (proxy) => attachJsonBodyForward(proxy)
      },

      '/api': {
        target: `http://127.0.0.1:${MAIN_BACKEND_PORT}`,
        ws: true,
        secure: false,
        changeOrigin: true,
        configure: (proxy) => attachJsonBodyForward(proxy)
      }
    }
  }
}
