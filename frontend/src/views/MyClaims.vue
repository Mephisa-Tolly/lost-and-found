<script setup>
/**
 * 我的申请（用户端）
 * 只展示当前登录用户自己提交的认领申请，以及管理员给出的审核结果。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMyClaims } from '@/api/items'

const router = useRouter()
const list = ref([])
const stat = ref({ total: 0, pending: 0, passed: 0, rejected: 0 })
const loading = ref(false)

const filter = ref('all') // all | 待核验 | 已通过 | 已拒绝

const shown = computed(() =>
  filter.value === 'all' ? list.value : list.value.filter((c) => c.status === filter.value),
)

function statusStyle(s) {
  return {
    待核验: { color: '#b45309', bg: '#fffbeb' },
    已通过: { color: '#07835c', bg: '#e7f8f1' },
    已拒绝: { color: '#b42318', bg: '#fef3f2' },
    已完成: { color: '#07835c', bg: '#e7f8f1' },
  }[s] || { color: '#667085', bg: '#f2f4f9' }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchMyClaims()
    list.value = data.list || []
    stat.value = data.stat || { total: 0, pending: 0, passed: 0, rejected: 0 }
  } catch (e) {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">
          <span>我的</span>
          <el-icon><ArrowRight /></el-icon>
          <span>认领申请</span>
        </div>
        <h1 class="page-title">我的申请</h1>
        <p class="page-sub">
          这里是你提交过的认领申请。管理员审核后会显示结果，通过即表示物品归你。
        </p>
      </div>
      <div class="head-actions">
        <el-button plain @click="router.push('/square')">
          <el-icon><Files /></el-icon>&nbsp;去广场看看
        </el-button>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-num">{{ stat.total }}</div>
        <div class="stat-label">申请总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num warn">{{ stat.pending }}</div>
        <div class="stat-label">待审核</div>
      </div>
      <div class="stat-card">
        <div class="stat-num ok">{{ stat.passed }}</div>
        <div class="stat-label">已通过</div>
      </div>
      <div class="stat-card">
        <div class="stat-num no">{{ stat.rejected }}</div>
        <div class="stat-label">未通过</div>
      </div>
    </div>

    <section class="panel filter-bar">
      <el-radio-group v-model="filter">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="待核验">待审核</el-radio-button>
        <el-radio-button value="已通过">已通过</el-radio-button>
        <el-radio-button value="已拒绝">未通过</el-radio-button>
      </el-radio-group>
      <el-button text @click="load">
        <el-icon><Refresh /></el-icon>&nbsp;刷新
      </el-button>
    </section>

    <div v-loading="loading" class="list-wrap">
      <template v-if="shown.length">
        <article v-for="c in shown" :key="c.claim_id" class="claim-card">
          <div class="c-head">
            <span class="c-title">{{ c.item.title }}</span>
            <span class="c-tag" :style="{
              color: statusStyle(c.status).color,
              background: statusStyle(c.status).bg,
            }">{{ c.status }}</span>
          </div>
          <div class="c-meta">
            <span><el-icon><PriceTag /></el-icon>{{ c.item.category }}</span>
            <span><el-icon><Location /></el-icon>{{ c.item.location }}</span>
            <span><el-icon><Clock /></el-icon>提交于 {{ String(c.created_at).slice(0, 16) }}</span>
          </div>
          <div class="c-block">
            <span class="c-label">你填写的核验特征</span>
            <p class="c-text">{{ c.answers }}</p>
          </div>
          <div v-if="c.status !== '待核验'" class="c-review" :class="c.passed ? 'ok' : 'no'">
            <div class="c-review-head">
              <el-icon><component :is="c.passed ? 'CircleCheckFilled' : 'CircleCloseFilled'" /></el-icon>
              <span>管理员审核结果：{{ c.passed ? '通过' : '不通过' }}</span>
              <span v-if="c.reviewed_at" class="c-time">{{ String(c.reviewed_at).slice(0, 16) }}</span>
            </div>
            <p v-if="c.review_note" class="c-note">说明：{{ c.review_note }}</p>
            <p v-else class="c-note">管理员未填写补充说明。</p>
          </div>
          <div v-else class="c-wait">
            <el-icon><Clock /></el-icon>
            管理员还未审核，请耐心等待。审核结果会显示在这里。
          </div>
        </article>
      </template>
      <div v-else-if="!loading" class="panel empty">
        <div class="empty-icon"><el-icon><Document /></el-icon></div>
        <div>{{ filter === 'all' ? '你还没有提交过认领申请' : '这个状态下没有申请' }}</div>
        <div class="empty-sub">
          在广场找到自己的东西，点进详情页填写私密特征，就能提交认领申请。
        </div>
        <el-button type="primary" plain style="margin-top: 14px" @click="router.push('/square')">
          去广场看看
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.head-actions {
  display: flex;
  gap: 10px;
}

.stat-num.warn {
  color: #b45309;
}

.stat-num.ok {
  color: #07835c;
}

.stat-num.no {
  color: #b42318;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.list-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 180px;
}

.claim-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 18px;
}

.c-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.c-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--ink);
  flex: 1;
  min-width: 0;
}

.c-tag {
  flex: none;
  font-size: 11.5px;
  font-weight: 650;
  padding: 3px 9px;
  border-radius: 7px;
}

.c-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
  font-size: 12.5px;
  color: var(--muted);
  margin-bottom: 11px;
}

.c-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.c-block {
  background: #f8f9fc;
  border-radius: 9px;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.c-label {
  font-size: 11.5px;
  font-weight: 650;
  color: #98a2b3;
  letter-spacing: 0.3px;
}

.c-text {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #3f4a5f;
  word-break: break-word;
}

.c-review {
  border-radius: 9px;
  padding: 10px 12px;
  font-size: 12.5px;
}

.c-review.ok {
  background: #eefbf5;
  border: 1px solid #cdeee2;
  color: #07835c;
}

.c-review.no {
  background: #fef5f4;
  border: 1px solid #fbd9d5;
  color: #b42318;
}

.c-review-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 650;
  flex-wrap: wrap;
}

.c-time {
  margin-left: auto;
  font-weight: 500;
  opacity: 0.75;
  font-size: 11.5px;
}

.c-note {
  margin: 5px 0 0;
  color: #5c6a80;
  line-height: 1.55;
  word-break: break-word;
}

.c-wait {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 9px;
  padding: 9px 12px;
}

@media (max-width: 640px) {
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-bar .el-radio-group {
    display: flex;
    width: 100%;
  }

  .filter-bar .el-radio-button {
    flex: 1;
  }

  .filter-bar .el-radio-button__inner {
    width: 100%;
    padding: 8px 0;
  }
}
</style>
