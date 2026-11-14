import { createRouter, createWebHistory } from 'vue-router'
import { setupGuards } from './guards'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/cases' },
    {
      path: '/login',
      name: 'login',
      component: () => import('../pages/LoginPage.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/cases',
      name: 'case-workbench',
      component: () => import('../pages/CaseWorkbenchPage.vue'),
      meta: { title: '案件工作台' },
    },
    {
      path: '/cases/:id',
      name: 'case-detail',
      component: () => import('../pages/CaseDetailPage.vue'),
      meta: { title: '案件详情' },
    },
    {
      path: '/rules',
      name: 'rules-runs',
      component: () => import('../pages/RulesRunsPage.vue'),
      meta: { title: '命名规则与归档批次' },
    },
    {
      path: '/pending',
      name: 'pending-queue',
      component: () => import('../pages/PendingQueuePage.vue'),
      meta: { title: '待确认队列' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/cases' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

setupGuards(router)

export default router
