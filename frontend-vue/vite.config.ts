import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev proxy /api → 后端 :8000，前端跨域无忧；CORS 仍追加 5173 双保险。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 函数式 manualChunks：按依赖归集，路径分隔符统一成正斜杠，避免 Windows/POSIX 间硬编码出错。
        // echarts + zrender → echarts vendor chunk；naive-ui → ui vendor chunk。
        // 目的：消除 500KB chunk 告警、缩小主包体积，依赖未变时便于长缓存命中。
        manualChunks(id) {
          const normalized = id.replace(/\\/g, '/')
          if (
            normalized.includes('node_modules/echarts') ||
            normalized.includes('node_modules/zrender')
          ) {
            return 'echarts'
          }
          if (normalized.includes('node_modules/naive-ui')) {
            return 'ui'
          }
        },
      },
    },
    // naive-ui 是全量引入的组件库,原始体积天然偏大(此处 ~893KB / gzip ~248KB),
    // 属预期;放宽告警阈值到 1000,避免对已知偏大的 vendor chunk 误报。
    chunkSizeWarningLimit: 1000,
  },
})
