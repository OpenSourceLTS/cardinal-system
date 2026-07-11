import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';

export default {
  plugins: [tailwindcss(), sveltekit()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080'
    },
    watch: {
      usePolling: true
    },
    hmr: {
      host: 'localhost',
      port: 5173
    }
  }
};
