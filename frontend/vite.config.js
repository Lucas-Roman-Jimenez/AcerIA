import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Solo lo que importa el frontend fuera de frontend/ (glosario, voz y datos de ejemplo).
    // Antes era '..': el servidor de desarrollo podía servir cualquier archivo del repositorio.
    fs: { allow: ['.', '../datos', '../voz', '../datos_ejemplo'] },
  },
})
