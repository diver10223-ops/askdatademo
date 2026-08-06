import { defineConfig } from 'vite'; import vue from '@vitejs/plugin-vue';
export default defineConfig(({mode})=>({plugins:[vue()],base:'./',build:{outDir:mode==='offline'?'offline-dist':'dist',assetsInlineLimit:10000000,cssCodeSplit:false},server:{proxy:{'/api':'http://127.0.0.1:8000'}}}));
