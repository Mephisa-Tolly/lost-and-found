<script setup>
/**
 * 广场（原「信息池」）：展示系统内所有用户发布的信息帖
 * 默认按发布时间倒序（最新在最上面），顶部提供四类筛选：
 *   类别（多选）、地点（多选）、失物/招领、时间顺序
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import { CATEGORIES, LOCATIONS } from '@/constants/dict'
import ItemCard from '@/components/ItemCard.vue'

const router = useRouter()

const list = ref([])
const total = ref(0)
const loading = ref(false)

// 筛选状态
const f = ref({
  keyword: '',
  type: 'all',        // all | lost | found
  categories: [],     // 多选类别
  locations: [],      // 多选地点
  order: 'desc',      // desc 最新在前 / asc 最早在前
})

const hasFilter = computed(
  () =>
    f.value.keyword ||
    f.value.type !== 'all' ||
    f.value.categories.length ||
    f.value.locations.length ||
    f.value.order !== 'desc',
)

async function load() {
  loading.value = true
  try {
    // 一次拉全量（最大 100/页，自动翻页），保证「所有帖子」都在
    const params = (page) => {
      const p = {
        page,
        size: 100,
        order: f.value.order,
      }
      if (f.value.type !== 'all') p.type = f.value.type
      if (f.value.categories.length) p.categories = f.value.categories.join(',')
      if (f.value.locations.length) p.locations = f.value.locations.join(',')
      if (f.value.keyword) p.keyword = f.value.keyword
      return p
    }

    const first = await request.get('/items', { params: params(1) })
    let all = first.list || []
    total.value = first.total || all.length
    const pages = Math.ceil(total.value / 100)
    for (let p = 2; p <= pages; p++) {
      const nxt = await request.get('/items', { params: params(p) })
      all = all.concat(nxt.list || [])
    }
    list.value = all
  } catch (e) {
    list.value = []
  } finally {
    loading.value = false
  }
}

function reset() {
  f.value = { keyword: '', type: 'all', categories: [], locations: [], order: 'desc' }
  load()
}

// 下拉筛选后立即生效（不需要点「检索」）
watch(
  () => [f.value.type, f.value.categories, f.value.locations, f.value.order],
  () => load(),
  { deep: true },
)

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">
          <span>广场</span>
          <el-icon><ArrowRight /></el-icon>
          <span>全部信息帖</span>
        </div>
        <h1 class="page-title">广场</h1>
      </div>
      <div class="head-actions">
        <el-button plain @click="router.push('/publish/found')">
          <el-icon><Bell /></el-icon>&nbsp;发布招领
        </el-button>
        <el-button type="primary" @click="router.push('/publish/lost')">
          <el-icon><Search /></el-icon>&nbsp;发布失物
        </el-button>
      </div>
    </div>

    <section class="panel filter-bar">
      <el-input
        v-model="f.keyword"
        placeholder="搜索标题、描述…"
        clearable
        class="search"
        @keyup.enter="load"
        @clear="load"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-radio-group v-model="f.type">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="lost">失物</el-radio-button>
        <el-radio-button value="found">招领</el-radio-button>
      </el-radio-group>

      <el-select
        v-model="f.categories"
        multiple
        collapse-tags
        collapse-tags-tooltip
        placeholder="物品类别（可多选）"
        class="sel-wide"
      >
        <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
      </el-select>

      <el-select
        v-model="f.locations"
        multiple
        collapse-tags
        collapse-tags-tooltip
        placeholder="地点（可多选）"
        class="sel-wide"
      >
        <el-option v-for="l in LOCATIONS" :key="l" :label="l" :value="l" />
      </el-select>

      <el-select v-model="f.order" class="sel">
        <el-option label="最新在前" value="desc" />
        <el-option label="最早在前" value="asc" />
      </el-select>

      <el-button type="primary" @click="load">
        <el-icon><Search /></el-icon>&nbsp;检索
      </el-button>
      <el-button v-if="hasFilter" text @click="reset">重置</el-button>
    </section>

    <div class="result-line">
      <span>共 <b>{{ total }}</b> 条信息帖</span>
      <span class="hint">
        当前筛选：{{ f.type === 'all' ? '全部类型' : f.type === 'lost' ? '仅失物' : '仅招领' }}
        · {{ f.order === 'desc' ? '最新在前' : '最早在前' }}
        <template v-if="f.categories.length"> · 类别 {{ f.categories.length }} 项</template>
        <template v-if="f.locations.length"> · 地点 {{ f.locations.length }} 项</template>
      </span>
    </div>

    <div v-loading="loading" class="list-wrap">
      <template v-if="list.length">
        <ItemCard
          v-for="(item, i) in list"
          :key="item.item_id"
          :item="item"
          class="rise"
          :style="{ animationDelay: `${i * 30}ms` }"
        />
      </template>
      <div v-else-if="!loading" class="panel empty">
        <div class="empty-icon"><el-icon><FolderOpened /></el-icon></div>
        <div>没有符合条件的信息帖</div>
        <div class="empty-sub">试试减少筛选条件，或者发布一条新的失物 / 招领</div>
        <el-button v-if="hasFilter" plain style="margin-top: 14px" @click="reset">清除筛选</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.head-actions {
  display: flex;
  gap: 10px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.search {
  width: 220px;
}

.sel {
  width: 120px;
}

.sel-wide {
  width: 190px;
}

.result-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12.5px;
  color: var(--muted);
  margin: 0 2px 12px;
  flex-wrap: wrap;
}

.result-line b {
  color: var(--ink);
  font-weight: 700;
}

.hint {
  color: #a3adbf;
}

.list-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}

.empty-sub {
  font-size: 12.5px;
  color: #98a2b3;
  margin-top: 6px;
}

@media (max-width: 640px) {
  /* 手机上筛选区每个控件独占一行，避免两个控件挤在同一行被压缩 */
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    padding: 12px;
  }

  .search,
  .sel,
  .sel-wide {
    width: 100%;
  }

  .filter-bar .el-radio-group {
    width: 100%;
    display: flex;
  }

  .filter-bar .el-radio-button {
    flex: 1;
  }

  .filter-bar .el-radio-button__inner {
    width: 100%;
    padding: 8px 0;
  }

  .filter-bar .el-button {
    margin-left: 0;
  }

  .result-line {
    flex-direction: column;
    align-items: stretch;
    gap: 3px;
  }
}
</style>
