<script setup>
/**
 * 认领审核（管理端）
 * 管理员查看所有用户提交的认领申请，逐条通过 / 不通过，并填写审核说明。
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAdminClaims, reviewClaim } from '@/api/items'

const list = ref([])
const stat = ref({ total: 0, pending: 0, passed: 0, rejected: 0 })
const loading = ref(false)
const reviewing = ref(null)

const status = ref('待核验')
const keyword = ref('')

const shown = computed(() => list.value)

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
    const data = await fetchAdminClaims({ status: status.value, keyword: keyword.value })
    list.value = data.list || []
    stat.value = data.stat || { total: 0, pending: 0, passed: 0, rejected: 0 }
  } catch (e) {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function doReview(row, action) {
  const pass = action === 'approve'
  let note = ''
  try {
    const r = await ElMessageBox.prompt(
      pass
        ? `确认「${row.applicant}」对《${row.item.title}》的认领申请通过？通过后该物品标记为已确认，同物品的其他待审申请自动作废。`
        : `驳回「${row.applicant}」对《${row.item.title}》的申请？请填写驳回原因，用户会在「我的申请」里看到。`,
      pass ? '通过申请' : '不通过',
      {
        confirmButtonText: pass ? '确认通过' : '确认驳回',
        cancelButtonText: '取消',
        inputPlaceholder: pass ? '可选：填写核验说明' : '请填写驳回原因（必填）',
        inputValidator: (v) => (pass ? true : (v && v.trim() ? true : '驳回必须填写原因')),
        type: pass ? 'success' : 'warning',
        inputValue: '',
      },
    )
    note = r.value || ''
  } catch {
    return
  }

  reviewing.value = row.claim_id
  try {
    await reviewClaim(row.claim_id, action, note)
    ElMessage.success(pass ? '已通过该申请' : '已驳回该申请')
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.response?.data?.msg || '操作失败')
  } finally {
    reviewing.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">
          <span>管理端</span>
          <el-icon><ArrowRight /></el-icon>
          <span>认领审核</span>
        </div>
        <h1 class="page-title">认领审核</h1>
        <p class="page-sub">
          核对用户填写的私密特征与发布者登记的「私密特征」是否吻合，决定通过或不通过。
        </p>
      </div>
      <div class="head-actions">
        <el-button plain :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>&nbsp;刷新
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
      <el-radio-group v-model="status" @change="load">
        <el-radio-button value="待核验">待审核</el-radio-button>
        <el-radio-button value="已通过">已通过</el-radio-button>
        <el-radio-button value="已拒绝">未通过</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
      <div class="search-wrap">
        <el-input
          v-model="keyword"
          placeholder="搜索物品标题 / 申请人 / 特征"
          clearable
          @keyup.enter="load"
          @clear="load"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="load">检索</el-button>
      </div>
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
            <span class="applicant"><el-icon><User /></el-icon>{{ c.applicant }}</span>
            <span><el-icon><PriceTag /></el-icon>{{ c.item.category }}</span>
            <span><el-icon><Location /></el-icon>{{ c.item.location }}</span>
            <span><el-icon><Clock /></el-icon>{{ String(c.created_at).slice(0, 16) }}</span>
            <span v-if="c.item.type" class="type">
              {{ c.item.type === 'lost' ? '失物' : '招领' }}
            </span>
          </div>

          <div class="cmp">
            <div class="cmp-box">
              <span class="c-label">用户填写的核验特征</span>
              <p class="c-text">{{ c.answers }}</p>
            </div>
            <div class="cmp-box ref">
              <span class="c-label">发布者登记的私密特征</span>
              <p class="c-text">{{ c.item.private_features || '（发布者未填写，需人工判断）' }}</p>
            </div>
          </div>

          <div v-if="c.status === '待核验'" class="c-ops">
            <el-button
              type="success"
              :loading="reviewing === c.claim_id"
              @click="doReview(c, 'approve')"
            >
              <el-icon><Select /></el-icon>&nbsp;通过
            </el-button>
            <el-button
              type="danger"
              plain
              :loading="reviewing === c.claim_id"
              @click="doReview(c, 'reject')"
            >
              <el-icon><CloseBold /></el-icon>&nbsp;不通过
            </el-button>
          </div>
          <div v-else class="c-done" :class="c.passed ? 'ok' : 'no'">
            <el-icon><component :is="c.passed ? 'CircleCheckFilled' : 'CircleCloseFilled'" /></el-icon>
            <span>{{ c.passed ? '已通过' : '已驳回' }}</span>
            <span v-if="c.reviewed_at" class="c-time">{{ String(c.reviewed_at).slice(0, 16) }}</span>
            <span v-if="c.review_note" class="c-note">说明：{{ c.review_note }}</span>
          </div>
        </article>
      </template>
      <div v-else-if="!loading" class="panel empty">
        <div class="empty-icon"><el-icon><Document /></el-icon></div>
        <div>{{ status === '待核验' ? '暂无待审核的认领申请' : '没有符合条件申请' }}</div>
        <div class="empty-sub">用户提交认领申请后会出现在这里。</div>
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

.search-wrap {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-wrap .el-input {
  width: 240px;
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

.c-meta .applicant {
  color: var(--ink-2);
  font-weight: 600;
}

.c-meta .type {
  background: #f2f4f9;
  border-radius: 5px;
  padding: 1px 6px;
  font-size: 11px;
}

.cmp {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}

.cmp-box {
  background: #f8f9fc;
  border: 1px solid #eef0f6;
  border-radius: 9px;
  padding: 10px 12px;
}

.cmp-box.ref {
  background: #f7f9ff;
  border-color: #e4e9fb;
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

.c-ops {
  display: flex;
  gap: 10px;
}

.c-done {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12.5px;
  border-radius: 9px;
  padding: 9px 12px;
}

.c-done.ok {
  background: #eefbf5;
  border: 1px solid #cdeee2;
  color: #07835c;
}

.c-done.no {
  background: #fef5f4;
  border: 1px solid #fbd9d5;
  color: #b42318;
}

.c-time {
  margin-left: auto;
  font-size: 11.5px;
  opacity: 0.8;
}

.c-note {
  flex: 1 1 100%;
  color: #5c6a80;
  font-size: 12px;
}

@media (max-width: 640px) {
  .cmp {
    grid-template-columns: 1fr;
  }

  .search-wrap {
    width: 100%;
  }

  .search-wrap .el-input {
    width: 100%;
  }

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
    font-size: 12px;
  }
}
</style>
