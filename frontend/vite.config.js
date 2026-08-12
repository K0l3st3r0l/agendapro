import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
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
            '/static': {
                target: 'http://backend:8000',
                changeOrigin: true,
            }
        }
    }
});
