<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchPendingMatches } from '@/api/items'
import CategoryChip from '@/components/CategoryChip.vue'

const router = useRouter()
const rows = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const data = await fetchPendingMatches()
    rows.value = data.list || []
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">
          <span>智能匹配</span>
          <el-icon><ArrowRight /></el-icon>
          <span>待确认匹配</span>
        </div>
        <h1 class="page-title">待确认匹配</h1>
      </div>
    </div>

    <div v-loading="loading" class="grid">
      <article
        v-for="row in rows"
        :key="row.item.item_id"
        class="card rising"
        @click="router.push(`/items/${row.item.item_id}/matches`)"
      >
        <div class="card-top">
          <span class="type" :class="row.item.type === 'lost' ? 'lost' : 'found'">
            {{ row.item.type === 'lost' ? '寻物' : '招领' }}
          </span>
          <span v-if="row.pending" class="badge">{{ row.pending }} 待确认</span>
          <span v-else class="badge done">已全部处理</span>
        </div>
        <h3>{{ row.item.title }}</h3>
        <div class="meta">
          <CategoryChip :category="row.item.category" />
          <span class="m"><el-icon><Location /></el-icon>{{ row.item.location }}</span>
        </div>
        <div class="cands">
          <div v-for="c in row.candidates.slice(0, 3)" :key="c.match_id" class="cand-row">
            <span class="sc">{{ Math.round(c.score * 100) }}%</span>
            <span class="ct">{{ c.candidate?.title }}</span>
            <span
              class="lv"
              :class="{ high: c.level === '高', mid: c.level === '中', low: c.level === '低' }"
            >{{ c.level }}</span>
          </div>
        </div>
        <div class="card-foot">
          去确认<el-icon><ArrowRight /></el-icon>
        </div>
      </article>

      <div v-if="!rows.length && !loading" class="panel empty" style="grid-column: 1/-1">
        <div class="empty-icon"><el-icon><MagicStick /></el-icon></div>
        <div>暂无待确认的匹配</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  /* minmax(0, 1fr)：列宽必须允许收缩，否则卡片内容会把整列撑出视口 */
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  min-height: 180px;
}

.card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 18px 20px 14px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  display: flex;
  flex-direction: column;
}

.card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow);
  border-color: #dfe3f2;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.type {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
}

.type.lost {
  color: #d92d20;
  background: #fef1ef;
}

.type.found {
  color: #0e9384;
  background: #e8f8f4;
}

.badge {
  margin-left: auto;
  font-size: 11.5px;
  font-weight: 650;
  color: #b26a00;
  background: #fff4e0;
  padding: 3px 9px;
  border-radius: 7px;
}

.badge.done {
  color: #07835c;
  background: #e7f8f1;
}

.card h3 {
  margin: 0 0 9px;
  font-size: 15px;
  font-weight: 650;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.m {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.m .el-icon {
  font-size: 12px;
  color: #a3aec2;
}

.cands {
  border-top: 1px dashed var(--line-strong);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.cand-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sc {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--primary);
  width: 36px;
}

.ct {
  flex: 1;
  font-size: 12px;
  color: #5c6a80;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lv {
  font-size: 10.5px;
  font-weight: 650;
  padding: 1px 6px;
  border-radius: 5px;
}

.lv.high {
  color: #07835c;
  background: #e7f8f1;
}
.lv.mid {
  color: #b26a00;
  background: #fff4e0;
}
.lv.low {
  color: #5a667d;
  background: #f1f3f8;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  margin-top: 12px;
}

@media (max-width: 1200px) {
  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  /* 手机竖屏两列放不下：卡片里有分数环 + 物品摘要，最小需要 300px */
  .grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
  }
}
</style>
