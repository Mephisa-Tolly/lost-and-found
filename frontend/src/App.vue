<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import request, { API_BASE } from '@/api/request'
import { useAuthStore } from '@/store/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// 登录页不显示外壳（侧边栏/顶栏）
const bare = computed(() => !!route.meta?.public)

// 后端 AI 状态：右上角显示大模型是否真的接上了
const aiStatus = ref(null)
onMounted(async () => {
  try {
    aiStatus.value = await request.get('/ai/status')
  } catch (e) {
    aiStatus.value = null
  }
})

const aiEnabled = computed(() => !!aiStatus.value?.enabled)
const aiLabel = computed(() => {
  if (!aiStatus.value) return 'AI 检测中'
  return aiEnabled.value
    ? `AI 已接入 · ${aiStatus.value.mode}`
    : 'AI 未配置 · 字面匹配'
})
const aiTip = computed(() => {
  if (!aiStatus.value) return '正在检测 AI 模块'
  const s = aiStatus.value
  const lines = []
  if (aiEnabled.value) {
    lines.push(`模型：${s.model}`)
    lines.push(`语义匹配 ${s.by_source.semantic} 条 · 字面匹配 ${s.by_source.lexical} 条`)
    const lc = s.last_call || {}
    if (lc.ok === true) lines.push(`最近调用：成功（${lc.at}）`)
    else if (lc.ok === false) lines.push(`最近调用：失败 —— ${lc.note || '原因未知'}`)
    else lines.push('最近调用：尚未触发（发布新帖后会调用一次）')
  } else {
    lines.push('未填写 LLM_API_KEY，当前只用字面相似度算法')
    lines.push('在 Railway 的 Variables 里配置后会自动启用大模型精排')
  }
  return lines.join('\n')
})

// 顶栏接口标签：点开是 FastAPI 自带的 Swagger 文档（以前只是个不可点的假标签，点了必 404）
const docsUrl = API_BASE.startsWith('http')
  ? `${API_BASE.replace(/\/api\/v1\/?$/, '')}/docs`
  : '/docs'

const navGroups = computed(() => {
  if (auth.isAdmin) {
    return [
      {
        label: '管理端',
        items: [
          { to: '/admin', title: '信息管理', icon: 'Files', match: '/admin' },
          { to: '/matches', title: '待确认匹配', icon: 'MagicStick', match: '/matches' },
          { to: '/admin/claims', title: '认领与线索', icon: 'DocumentChecked', match: '/admin/claims' },
        ],
      },
    ]
  }
  return [
    {
      label: '广场',
      items: [{ to: '/square', title: '广场', icon: 'Files', match: '/square' }],
    },
    {
      label: '信息发布',
      items: [
        { to: '/publish/lost', title: '发布失物', icon: 'Search', match: '/publish/lost' },
        { to: '/publish/found', title: '发布招领', icon: 'Bell', match: '/publish/found' },
      ],
    },
    {
      label: '我的',
      items: [{ to: '/my-claims', title: '我的申请', icon: 'Document', match: '/my-claims' }],
    },
  ]
})

const isActive = (item) => {
  const p = route.path
  if (item.match === '/admin') return p === '/admin' || (p.startsWith('/items') && p.endsWith('/matches') === false && p !== '/admin/claims')
  if (item.match === '/admin/claims') return p.startsWith('/admin/claims')
  if (item.match === '/matches') return p === '/matches' || p.includes('/matches')
  if (item.match === '/square') return p === '/square' || p.startsWith('/items')
  return p === item.match || p.startsWith(item.match + '/')
}

const currentGroup = computed(() => route.meta?.group || (auth.isAdmin ? '管理端' : '广场'))
const currentTitle = computed(() => route.meta?.title || (auth.isAdmin ? '信息管理' : '广场'))

async function handleLogout() {
  try {
    await ElMessageBox.confirm('退出后需要重新输入账号密码，确定退出吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  auth.logout()
  ElMessage.success('已退出登录')
  router.replace('/login')
}
</script>

<template>
  <router-view v-if="bare" />
  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <el-icon><Aim /></el-icon>
        </div>
        <div class="brand-text">
          <div class="brand-name">失物招领</div>
          <div class="brand-sub">Campus Match · V3.0</div>
        </div>
      </div>

      <nav class="nav">
        <div v-for="g in navGroups" :key="g.label" class="nav-group">
          <div class="nav-label">{{ g.label }}</div>
          <router-link
            v-for="item in g.items"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :class="{ active: isActive(item) }"
          >
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-foot">
        <div class="mode-badge">
          <span class="dot" style="color:#10b981" />
          已连接后端服务
        </div>
        <div class="version">v3.0 · {{ auth.isAdmin ? '管理端' : '用户端' }}</div>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <span class="topbar-group">{{ currentGroup }}</span>
          <el-icon class="sep"><ArrowRight /></el-icon>
          <span class="topbar-title">{{ currentTitle }}</span>
        </div>
        <div class="topbar-right">
          <a
            class="pill pill-api"
            :href="docsUrl"
            target="_blank"
            rel="noopener"
            title="打开接口文档（Swagger）"
          >
            <el-icon><Document /></el-icon> 接口文档
          </a>
          <el-tooltip :content="aiTip" placement="bottom">
            <div class="pill" :class="aiEnabled ? 'pill-ai-on' : 'pill-ai-off'">
              <span class="ai-dot" /> {{ aiLabel }}
            </div>
          </el-tooltip>
          <div class="user-chip">
            <div class="avatar">{{ (auth.username || '?').slice(0, 1).toUpperCase() }}</div>
            <div class="user-meta">
              <span class="user-name">{{ auth.username || '未登录' }}</span>
              <span class="user-role" :class="auth.isAdmin ? 'role-admin' : 'role-user'">
                {{ auth.roleName }}
              </span>
            </div>
          </div>
          <el-tooltip content="退出登录" placement="bottom">
            <button class="logout-btn" @click="handleLogout">
              <el-icon><SwitchButton /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

/* ---------------- 侧边栏 ---------------- */
.sidebar {
  width: 236px;
  flex: none;
  background: #fff;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 22px 20px 18px;
}

.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 19px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed 55%, #06b6d4);
  box-shadow: 0 8px 18px -8px rgba(79, 70, 229, 0.75);
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.brand-sub {
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
  letter-spacing: 0.4px;
}

.nav {
  padding: 6px 12px 12px;
  overflow-y: auto;
  flex: 1;
}

.nav-group + .nav-group {
  margin-top: 18px;
}

.nav-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.9px;
  color: #9aa4b6;
  padding: 0 10px;
  margin-bottom: 7px;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 11px;
  border-radius: 10px;
  color: var(--ink-2);
  font-size: 13.5px;
  font-weight: 550;
  margin-bottom: 3px;
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.nav-item:hover {
  background: #f5f6fb;
  color: var(--ink);
}

.nav-item.active {
  background: linear-gradient(90deg, #eef0ff, #f6f4ff);
  color: var(--primary);
  box-shadow: inset 0 0 0 1px #e3e2fb;
}

.nav-item.active .nav-icon {
  color: var(--primary);
}

.nav-icon {
  font-size: 16px;
  color: #8792a8;
}

.sidebar-foot {
  padding: 14px 18px 18px;
  border-top: 1px solid var(--line);
}

.mode-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: #0f766e;
  background: #e9f9f5;
  border-radius: 7px;
  padding: 5px 9px;
  font-weight: 600;
}

.version {
  font-size: 11px;
  color: #a3adbf;
  margin-top: 8px;
  letter-spacing: 0.2px;
}

/* ---------------- 主区 ---------------- */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 60px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 20;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.topbar-group {
  color: var(--muted);
}

.sep {
  font-size: 11px;
  color: #c2cad8;
}

.topbar-title {
  font-weight: 650;
  color: var(--ink);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
  background: #f5f6fa;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 11px;
}

.pill-api {
  color: var(--muted);
  text-decoration: none;
  transition: color 0.16s ease, border-color 0.16s ease;
}

.pill-api:hover {
  color: var(--primary);
  border-color: #d9dbf5;
}

.pill-ai-on {
  color: #047857;
  background: #ecfdf5;
  border-color: #a7f3d0;
  font-weight: 600;
}

.pill-ai-off {
  color: #92400e;
  background: #fffbeb;
  border-color: #fde68a;
}

.ai-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex: none;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  flex: none;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 10px 3px 3px;
  border-radius: 999px;
  background: #f7f8fc;
  border: 1px solid var(--line);
}

.user-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.user-name {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--ink);
}

.user-role {
  font-size: 10.5px;
  font-weight: 600;
}

.role-admin {
  color: #b45309;
}

.role-user {
  color: #0f766e;
}

.logout-btn {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: #fff;
  color: #8792a8;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.16s ease;
}

.logout-btn:hover {
  color: #dc2626;
  border-color: #fecaca;
  background: #fef2f2;
}

.content {
  flex: 1;
}

/* 路由过渡 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ---------------- 移动端适配（手机竖屏） ---------------- */
@media (max-width: 768px) {
  .shell {
    flex-direction: column;
  }

  /* 侧边栏改为顶部横排导航 */
  .sidebar {
    width: 100%;
    height: auto;
    position: static;
    border-right: none;
    border-bottom: 1px solid var(--line);
    flex-direction: column;
  }

  .brand {
    padding: 12px 14px 8px;
  }

  .brand-sub {
    display: none;
  }

  .nav {
    display: flex;
    gap: 4px;
    padding: 0 10px 10px;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
  }

  .nav-group {
    display: contents;
  }

  .nav-group + .nav-group {
    margin-top: 0;
  }

  .nav-label {
    display: none;
  }

  .nav-item {
    flex: none;
    height: 34px;
    padding: 0 12px;
    margin-bottom: 0;
    font-size: 13px;
    white-space: nowrap;
  }

  .sidebar-foot {
    display: none;
  }

  /* 顶栏允许换行，接口地址等不再挤压 */
  .topbar {
    flex-wrap: wrap;
    height: auto;
    padding: 8px 12px;
    row-gap: 6px;
  }

  .topbar-right {
    flex-wrap: wrap;
    gap: 6px;
  }

  .pill {
    font-size: 11px;
    padding: 4px 8px;
  }

  .content {
    padding: 12px;
    min-width: 0;
  }

  .pill-api {
    display: none;
  }

  .user-meta {
    display: none;
  }

  .user-chip {
    padding: 3px;
  }
}
</style>
