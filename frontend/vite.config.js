import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The single .env file lives at the repository root, one level up.
const ENV_DIR = '..'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ENV_DIR, '')
  const port = Number(env.FRONTEND_PORT || 5101)
  return {
    plugins: [react()],
    envDir: ENV_DIR,
    server: { port, strictPort: true }, // fail instead of silently switching ports
    preview: { port, strictPort: true },
  }
})
