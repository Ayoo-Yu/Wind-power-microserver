// frontend/vue.config.js
const MAIN_BACKEND_PORT = process.env.MAIN_BACKEND_PORT || '5000'
const AUTO_BACKEND_PORT = process.env.AUTO_BACKEND_PORT || '5001'

module.exports = {
  devServer: {
    proxy: {
      // 规则 1: 代理特定的 autopredict API 到 5001
      '/api/(start|start_ultra|stop|status|tasks|logs|save|resurrect|clearsave|delete|schedule|script_info|task_status)': {
        target: `http://127.0.0.1:${AUTO_BACKEND_PORT}`, // 指向 autopredict 后端
        ws: false,
        changeOrigin: true,
        secure: false,
        // pathRewrite: {
        //   '^/api': '' // 移除 /api 前缀
        // },
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.body) {
              const bodyData = JSON.stringify(req.body);
              proxyReq.setHeader('Content-Type', 'application/json');
              proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
              proxyReq.write(bodyData);
            }
          });
        }
      },

      // 规则 2: 代理其他所有 /api 请求到 5000，并移除 /api 前缀
      '/api': {
        target: `http://127.0.0.1:${MAIN_BACKEND_PORT}`, // 指向主后端
        pathRewrite: {
          '^/api': ''  // 移除 /api 前缀
        },
        ws: true,
        secure: false,
        changeOrigin: true,
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.body) {
              const bodyData = JSON.stringify(req.body);
              proxyReq.setHeader('Content-Type', 'application/json');
              proxyReq.setHeader('Content-Length', Buffer.byteLength(bodyData));
              proxyReq.write(bodyData);
            }
          });
        }
      }
    }
  }
}
