import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Espeja el "paths" de tsconfig.json. Sin esto, TypeScript aceptaba
    // `import x from '@/components/Foo'` y Vite fallaba al resolverlo.
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      // Las imágenes generadas se sirven desde el backend. Sin este proxy,
      // en desarrollo salían rotas: nginx sí las rutea en producción
      // (frontend/nginx.conf), pero el dev server no lo hacía.
      '/static': {
        target: 'http://backend:8000',
        changeOrigin: true,
      }
    }
  }
})
