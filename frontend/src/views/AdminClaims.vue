<script setup>
/**
 * 认领审核（管理端）
 * 两个队列：
 *   - 认领申请：失主对「招领帖」提交，核对私密特征是否吻合
 *   - 线索：知情人对「寻物帖」提交，核实后联系失主
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
// claim = 认领申请 / clue = 线索
const kind = ref('claim')
const isClue = computed(() => kind.value === 'clue')

const shown = computed(() => list.value)

const unitLabel = computed(() => (isClue.value ? '线索' : '申请'))

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
    const data = await fetchAdminClaims({
      status: status.value,
      keyword: keyword.value,
      kind: kind.value,
    })
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
  const clue = row.kind === 'clue'
  let note = ''
  try {
    const r = await ElMessageBox.prompt(
      pass
        ? clue
          ? `采纳「${row.applicant}」对《${row.item.title}》提交的线索？采纳后该线索会转发给发布失物帖的用户，由其自行判断是否接受。`
          : `确认「${row.applicant}」对《${row.item.title}》的认领申请通过？通过后该物品标记为已确认，同物品的其他待审申请自动作废。`
        : clue
          ? `忽略「${row.applicant}」提交的线索？请填写原因，用户会在「我的申请」里看到。`
          : `驳回「${row.applicant}」对《${row.item.title}》的申请？请填写驳回原因，用户会在「我的申请」里看到。`,
      pass ? (clue ? '采纳线索' : '通过申请') : clue ? '忽略线索' : '不通过',
      {
        confirmButtonText: pass ? (clue ? '确认采纳' : '确认通过') : clue ? '确认忽略' : '确认驳回',
        cancelButtonText: '取消',
        inputPlaceholder: pass ? '可选：填写核实说明' : '请填写原因（必填）',
        inputValidator: (v) => (pass ? true : (v && v.trim() ? true : '必须填写原因')),
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
    ElMessage.success(
      pass ? (clue ? '已采纳该线索' : '已通过该申请') : clue ? '已忽略该线索' : '已驳回该申请',
    )
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.response?.data?.msg || '操作失败')
  } finally {
    reviewing.value = null
  }
}

function onKindChange() {
  status.value = '待核验'
  load()
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
          <span>认领与线索</span>
        </div>
        <h1 class="page-title">认领与线索</h1>
      </div>
      <div class="head-actions">
        <el-button plain :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>&nbsp;刷新
        </el-button>
      </div>
    </div>

    <section class="panel kind-bar">
      <div class="kind-tabs">
        <button class="kind-tab" :class="{ on: kind === 'claim' }" @click="kind = 'claim'; onKindChange()">
          <el-icon><DocumentChecked /></el-icon>认领申请
        </button>
        <button class="kind-tab" :class="{ on: kind === 'clue' }" @click="kind = 'clue'; onKindChange()">
          <el-icon><ChatLineSquare /></el-icon>线索
        </button>
      </div>
    </section>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-num">{{ stat.total }}</div>
        <div class="stat-label">{{ unitLabel }}总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num warn">{{ stat.pending }}</div>
        <div class="stat-label">待审核</div>
      </div>
      <div class="stat-card">
        <div class="stat-num ok">{{ stat.passed }}</div>
        <div class="stat-label">{{ isClue ? '已采纳' : '已通过' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-num no">{{ stat.rejected }}</div>
        <div class="stat-label">{{ isClue ? '已忽略' : '未通过' }}</div>
      </div>
    </div>

    <section class="panel filter-bar">
      <el-radio-group v-model="status" @change="load">
        <el-radio-button value="待核验">待审核</el-radio-button>
        <el-radio-button value="已通过">{{ isClue ? '已采纳' : '已通过' }}</el-radio-button>
        <el-radio-button value="已拒绝">{{ isClue ? '已忽略' : '未通过' }}</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
      <div class="search-wrap">
        <el-input
          v-model="keyword"
          :placeholder="isClue ? '搜索物品标题 / 线索人 / 线索内容' : '搜索物品标题 / 申请人 / 特征'"
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
            <span v-if="c.kind === 'clue'" class="c-kind clue">线索</span>
            <span v-else class="c-kind claim">认领</span>
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
              {{ c.item.type === 'lost' ? '寻物帖' : '招领帖' }}
            </span>
          </div>

          <div class="cmp">
            <div class="cmp-box">
              <span class="c-label">{{ c.kind === 'clue' ? '申请者提交的线索内容' : '申请者填写的核验特征' }}</span>
              <p class="c-text">{{ c.answers }}</p>
            </div>
            <div class="cmp-box ref">
              <span class="c-label">{{ c.kind === 'clue' ? '失主登记的特征（对照）' : '发布者登记的私密特征' }}</span>
              <p class="c-text">{{ c.item.private_features || '（发布者未填写，需人工判断）' }}</p>
            </div>
          </div>

          <div v-if="c.status === '待核验'" class="c-ops">
            <el-button
              type="success"
              :loading="reviewing === c.claim_id"
              @click="doReview(c, 'approve')"
            >
              <el-icon><Select /></el-icon>&nbsp;{{ c.kind === 'clue' ? '采纳线索' : '通过' }}
            </el-button>
            <el-button
              type="danger"
              plain
              :loading="reviewing === c.claim_id"
              @click="doReview(c, 'reject')"
            >
              <el-icon><CloseBold /></el-icon>&nbsp;{{ c.kind === 'clue' ? '忽略' : '不通过' }}
            </el-button>
          </div>
          <div v-else class="c-done" :class="c.passed ? 'ok' : 'no'">
            <el-icon><component :is="c.passed ? 'CircleCheckFilled' : 'CircleCloseFilled'" /></el-icon>
            <span>{{ c.passed ? (c.kind === 'clue' ? '已采纳' : '已通过') : (c.kind === 'clue' ? '已忽略' : '已驳回') }}</span>
            <span v-if="c.reviewed_at" class="c-time">{{ String(c.reviewed_at).slice(0, 16) }}</span>
            <span v-if="c.review_note" class="c-note">说明：{{ c.review_note }}</span>
          </div>
        </article>
      </template>
      <div v-else-if="!loading" class="panel empty">
        <div class="empty-icon"><el-icon><Document /></el-icon></div>
        <div>{{ status === '待核验' ? `暂无待审核的${unitLabel}` : `没有符合条件的${unitLabel}` }}</div>
        <div class="empty-sub">
          {{ isClue ? '用户在寻物帖下提交线索后会出现在这里。' : '用户在招领帖提交认领申请后会出现在这里。' }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.head-actions {
  display: flex;
  gap: 10px;
}

.kind-bar {
  padding: 8px;
  margin-bottom: 14px;
}

.kind-tabs {
  display: flex;
  gap: 6px;
}

.kind-tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 18px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--muted);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.16s ease;
}

.kind-tab:hover {
  background: #f5f6fb;
  color: var(--ink-2);
}

.kind-tab.on {
  color: var(--primary);
  background: linear-gradient(90deg, #eef0ff, #f6f4ff);
  border-color: #e3e2fb;
}

.c-kind {
  flex: none;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 5px;
}

.c-kind.claim {
  color: #1d4ed8;
  background: #e8eeff;
}

.c-kind.clue {
  color: #0e9384;
  background: #e8f8f4;
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
