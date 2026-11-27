import {defineConfig} from 'vite';
export default defineConfig({build:{outDir:'dist-monitor',lib:{entry:'src/components/WorkforceMonitor.jsx',formats:['es'],fileName:'workforce-monitor'},rollupOptions:{external:['react','react/jsx-runtime']}}});
