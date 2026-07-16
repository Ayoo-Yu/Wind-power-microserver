import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

function createProxyTarget(backendPort, ws = false) {
  return {
    target: `http://127.0.0.1:${backendPort}`,
    changeOrigin: true,
    secure: false,
    ws
  }
}

export default defineConfig(({ mode }) => {
  const modeEnv = loadEnv(mode, process.cwd(), '')
  const backendPort = process.env.MAIN_BACKEND_PORT ||
    modeEnv.MAIN_BACKEND_PORT ||
    process.env.VUE_APP_MAIN_BACKEND_PORT ||
    modeEnv.VUE_APP_MAIN_BACKEND_PORT ||
    '5000'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '0.0.0.0',
      port: 8080,
      strictPort: true,
      proxy: {
        '/api/v1/autopredict': createProxyTarget(backendPort),
        '/api/v1': createProxyTarget(backendPort),
        '^/api/(start|start_ultra|stop|status|tasks|logs|save|resurrect|clearsave|delete|schedule|script_info|task_status)': createProxyTarget(backendPort),
        '/get-daily-metrics': createProxyTarget(backendPort),
        '/api': createProxyTarget(backendPort, true),
        '/scada/': createProxyTarget(backendPort),
        '/operational': createProxyTarget(backendPort)
      }
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      sourcemap: false,
      chunkSizeWarningLimit: 1300
    }
  }
})
