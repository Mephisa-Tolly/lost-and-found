<script setup>
import { onMounted, computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchStore } from '@/store/match'
import { useAuthStore } from '@/store/auth'
import request from '@/api/request'
import CategoryChip from '@/components/CategoryChip.vue'
import MatchCandidate from '@/components/MatchCandidate.vue'

const route = useRoute()
const router = useRouter()
const store = useMatchStore()
const auth = useAuthStore()

// 确认/忽略只向管理员开放；普通用户只读查看匹配结果
const isAdmin = computed(() => auth.isAdmin)

const decidedAny = ref(false)

// AI 通道真实状态：用来给候选卡片的「语义/字面」徽标定性
const aiStatus = ref(null)
async function loadAiStatus() {
  try {
    aiStatus.value = await request.get('/ai/status')
  } catch {
    aiStatus.value = null
  }
}
const aiSemanticOk = computed(() => {
  const s = aiStatus.value
  if (!s || !s.enabled) return false
  // 最近一次调用失败（如模型 1305 限流）时，语义通道事实上不可用
  if (s.last_call && s.last_call.ok === false) return false
  return true
})
const aiDownReason = computed(() => {
  const s = aiStatus.value
  if (!s || !s.enabled) return '未配置大模型 Key'
  return s.last_call?.note || '模型调用失败'
})

onMounted(() => {
  store.load(route.params.id)
  loadAiStatus()
})
// 同一路由内切换帖子 id 时组件不会重建，需要手动重载，否则显示上一条的数据
watch(
  () => route.params.id,
  (id, old) => {
    if (id && id !== old) {
      decidedAny.value = false
      store.load(id)
    }
  },
)

const src = computed(() => store.item)
const total = computed(() => store.candidates.length)
const progress = computed(() =>
  total.value ? Math.round(((total.value - store.pendingCount) / total.value) * 100) : 0,
)

async function onConfirm(c) {
  const others = store.pendingCount - (store.decisions[c.match_id] ? 0 : 1)
  const extra =
    others > 0
      ? `\n\n确认后该记录其余 ${others} 条待确认候选将自动作废。`
      : ''
  try {
    await ElMessageBox.confirm(
      `确认「${c.candidate?.title}」与你发布的记录是同一件物品？\n\n确认后不可撤销，将进入认领核验流程。${extra}`,
      '确认匹配',
      {
        confirmButtonText: '确认（不可撤销）',
        cancelButtonText: '再看看',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }
  await store.decide(c.match_id, 'confirm')
  decidedAny.value = true
  ElMessage.success('已确认，可继续提交认领申请')
}

async function onIgnore(c) {
  await store.decide(c.match_id, 'ignore')
  ElMessage.info('已忽略该候选')
}

function goDetail() {
  router.push(`/items/${route.params.id}`)
}
</script>

<template>
  <div v-loading="store.loading" class="page">
    <div class="page-head">
      <div>
        <div class="crumb">
          <span class="link" @click="router.push('/items')">信息池</span>
          <el-icon><ArrowRight /></el-icon>
          <span class="link" @click="goDetail">物品详情</span>
          <el-icon><ArrowRight /></el-icon>
          <span>匹配结果</span>
        </div>
        <h1 class="page-title">AI 匹配结果{{ isAdmin ? '与人工确认' : '' }}</h1>
        <p class="page-sub">
          系统已按类别、地点、时间窗硬过滤，再由同义词归一与语义通道排序。候选仅供参考，{{
            isAdmin ? '归属由你确认。' : '最终确认由管理员完成，你可以先浏览候选。'
          }}
        </p>
      </div>
      <el-button plain @click="goDetail">
        <el-icon><Back /></el-icon>&nbsp;返回详情
      </el-button>
    </div>

    <section v-if="src" class="panel src-bar">
      <div class="src-left">
        <span class="q-label">比对源</span>
        <span class="q-title">{{ src.title }}</span>
        <CategoryChip :category="src.category" />
        <span class="q-meta"><el-icon><Location /></el-icon>{{ src.location }}</span>
        <span class="q-meta"><el-icon><Clock /></el-icon>{{ String(src.time).slice(5, 16) }}</span>
      </div>
      <div class="src-right">
        <template v-if="isAdmin">
          <el-progress
            :percentage="progress"
            :stroke-width="7"
            :show-text="false"
            style="width: 130px"
          />
          <span class="prog-text">
            已处理 {{ total - store.pendingCount }}/{{ total }}
          </span>
        </template>
        <span v-else class="prog-text">共 {{ total }} 条候选 · 只读</span>
      </div>
    </section>

    <div class="summary">
      <div class="sum-item">
        <span class="num">{{ total }}</span>
        <span class="lbl">候选总数</span>
      </div>
      <div class="sum-item pending">
        <span class="num">{{ store.pendingCount }}</span>
        <span class="lbl">{{ isAdmin ? '待确认' : '待管理员确认' }}</span>
      </div>
      <div class="sum-item ok">
        <span class="num">{{ store.confirmedCount }}</span>
        <span class="lbl">已确认</span>
      </div>
      <div class="sum-item no">
        <span class="num">{{ store.ignoredCount }}</span>
        <span class="lbl">已忽略</span>
      </div>
    </div>

    <div class="list">
      <template v-if="total">
        <MatchCandidate
          v-for="(c, i) in store.candidates"
          :key="c.match_id"
          :candidate="c"
          :index="i + 1"
          :decision="store.decisions[c.match_id]"
          :reviewing="store.reviewing === c.match_id"
          :ai-semantic-ok="aiSemanticOk"
          :ai-down-reason="aiDownReason"
          :readonly="!isAdmin"
          class="rise"
          :style="{ animationDelay: `${i * 60}ms` }"
          @confirm="onConfirm"
          @ignore="onIgnore"
        />
      </template>

      <div v-else-if="!store.loading" class="panel empty">
        <div class="empty-icon"><el-icon><Search /></el-icon></div>
        <div>暂无可匹配的候选</div>
        <div class="empty-sub">
          可能是信息池中暂无同类记录，或时间窗、地点条件过窄。可以放宽条件后重试，或等待命中推送。
        </div>
        <el-button plain style="margin-top: 16px" @click="router.push('/items')">去信息池看看</el-button>
      </div>
    </div>

    <el-alert
      v-if="decidedAny && isAdmin"
      class="foot-alert"
      type="success"
      :closable="false"
      show-icon
      title="已完成人工确认"
      description="确认只表示你知道这条候选存在，不代表系统判定归属。正式认领仍需私密特征核验、拾得者确认与管理员二次核验。"
    />
    <div v-else class="foot-note">
      <el-icon><InfoFilled /></el-icon>
      <template v-if="isAdmin">
        AI 只负责召回与排序，不输出归属结论；相似度按高 / 中 / 低分级呈现，不代表匹配概率。
      </template>
      <template v-else>
        AI 只负责召回与排序，不输出归属结论；确认匹配由管理员在管理端完成，如确认是你的物品，可到详情页提交认领申请。
      </template>
    </div>
  </div>
</template>

<style scoped>
.link {
  cursor: pointer;
  color: var(--primary);
}

.src-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 15px 20px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.src-left {
  display: flex;
  align-items: center;
  gap: 11px;
  flex-wrap: wrap;
}

.q-label {
  font-size: 11.5px;
  font-weight: 650;
  color: #6d28d9;
  background: #f4f0ff;
  border-radius: 6px;
  padding: 3px 8px;
}

.q-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--ink);
}

.q-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: var(--muted);
}

.q-meta .el-icon {
  font-size: 13px;
  color: #a3aec2;
}

.src-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.prog-text {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}

.summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}

.sum-item {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 13px 16px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.sum-item .num {
  font-size: 21px;
  font-weight: 720;
  color: var(--ink);
  letter-spacing: -0.5px;
}

.sum-item .lbl {
  font-size: 12px;
  color: var(--muted);
}

.sum-item.pending .num {
  color: #b26a00;
}
.sum-item.ok .num {
  color: #07835c;
}
.sum-item.no .num {
  color: #98a2b3;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-left: 11px;
}

.empty-sub {
  font-size: 12.5px;
  color: #98a2b3;
  margin-top: 6px;
  max-width: 520px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.7;
}

.foot-note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #98a2b3;
  margin-top: 18px;
  padding-left: 4px;
}

.foot-alert {
  margin-top: 18px;
  border-radius: 12px;
}

@media (max-width: 860px) {
  /* 四列统计在手机上每格只剩 40px，改成两列 */
  .summary {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .sum-item {
    padding: 11px 13px;
  }

  .sum-item .num {
    font-size: 19px;
  }

  .src-bar {
    gap: 10px;
    padding: 13px 15px;
  }

  .q-title {
    flex: 1 1 100%;
    word-break: break-word;
  }

  .src-right {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .src-right .el-progress {
    flex: 1;
    max-width: 180px;
  }
}
</style>
