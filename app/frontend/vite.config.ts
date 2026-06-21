import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// O backend (Streamlit/FastAPI) responde em localhost:8502.
// O proxy reescreve /api -> localhost:8502 para evitar CORS em dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8502',
    },
  },
})
