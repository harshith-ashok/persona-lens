import { createRouter, createWebHistory } from 'vue-router'

import Login from '../views/Login.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: Login },
    { path: '/register', component: () => import('../views/Register.vue') },
    { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
  ],
})

export default router
