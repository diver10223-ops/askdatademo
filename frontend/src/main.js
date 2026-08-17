import { createApp, h } from 'vue';
import { createRouter, createWebHashHistory, createWebHistory, RouterView } from 'vue-router';
import App from './App.vue';
import V21View from './V21View.vue';
import AdminView from './AdminView.vue';
import { isOffline } from './runtime';
import './style.css';
const router = createRouter({ history: isOffline ? createWebHashHistory() : createWebHistory(), routes: [{ path: '/', component: App }, { path: '/v2', component: App }, { path: '/v2.1', component: V21View }, { path: '/admin/:pathMatch(.*)*', component: AdminView }] });
createApp({ render: () => h(RouterView) }).use(router).mount('#app');
