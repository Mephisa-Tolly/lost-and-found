import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { title: '登录', public: true } },
  { path: '/', redirect: '/square' },

  // ---------- 用户端 ----------
  {
    path: '/square',
    name: 'Square',
    component: () => import('@/views/Square.vue'),
    meta: { title: '广场', group: '广场', role: 'user' },
  },
  {
    path: '/publish/lost',
    name: 'PublishLost',
    component: () => import('@/views/PublishLost.vue'),
    meta: { title: '发布失物', group: '信息发布', role: 'user' },
  },
  {
    path: '/publish/found',
    name: 'PublishFound',
    component: () => import('@/views/PublishFound.vue'),
    meta: { title: '发布招领', group: '信息发布', role: 'user' },
  },
  { path: '/items', redirect: '/square' },
  {
    path: '/items/:id',
    name: 'ItemDetail',
    component: () => import('@/views/ItemDetail.vue'),
    // 管理员从信息管理点进来看详情，普通用户从广场点进来，两种角色都允许
    meta: { title: '帖子详情', group: '广场' },
  },
  {
    path: '/items/:id/matches',
    name: 'MatchReview',
    component: () => import('@/views/MatchReview.vue'),
    // 用户与管理员都可查看匹配结果；「确认匹配」操作在页面内按角色隐藏，后端接口同样校验管理员
    meta: { title: 'AI 匹配结果', group: '智能匹配' },
  },
  {
    path: '/matches',
    name: 'MatchInbox',
    component: () => import('@/views/MatchInbox.vue'),
    meta: { title: '待确认匹配', group: '智能匹配', role: 'admin' },
  },
  {
    path: '/my-claims',
    name: 'MyClaims',
    component: () => import('@/views/MyClaims.vue'),
    meta: { title: '我的申请', group: '我的', role: 'user' },
  },
  { path: '/dashboard', redirect: '/square' },

  // ---------- 管理端 ----------
  {
    path: '/admin',
    name: 'AdminItems',
    component: () => import('@/views/AdminItems.vue'),
    meta: { title: '信息管理', group: '管理端', role: 'admin' },
  },
  {
    path: '/admin/claims',
    name: 'AdminClaims',
    component: () => import('@/views/AdminClaims.vue'),
    meta: { title: '认领审核', group: '管理端', role: 'admin' },
  },

  { path: '/:pathMatch(.*)*', redirect: '/square' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/**
 * 登录拦截：
 * - 未登录 → 一律去 /login
 * - 已登录访问不属于自己角色的页面 → 回到本角色首页
 * 直接用 localStorage 判断，避免每次跳转都发请求。
 */
router.beforeEach((to) => {
  const token = localStorage.getItem('lf_token')
  const role = localStorage.getItem('lf_role')

  if (to.meta?.public) return true
  if (!token) return { path: '/login', replace: true }
  if (to.meta?.role && to.meta.role !== role) {
    return { path: role === 'admin' ? '/admin' : '/square', replace: true }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta?.title
    ? `${to.meta.title} · 校园失物招领 V3.0`
    : '校园智能失物招领匹配系统 · V3.0'
})

export default router
