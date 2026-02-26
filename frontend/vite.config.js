import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/cases': 'http://localhost:3001',
      '/uploads': 'http://localhost:3001'
    }
  }
});
