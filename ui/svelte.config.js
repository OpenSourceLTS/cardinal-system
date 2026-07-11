import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
export default {
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html'
    }),
    prerender: {
      handleHttpError: ({ path }) => {
        if (path === '/favicon.ico') return;
        throw new Error(`Prerender error for ${path}`);
      }
    }
  }
};
