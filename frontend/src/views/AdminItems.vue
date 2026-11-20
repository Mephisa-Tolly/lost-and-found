<script setup>
/**
 * 管理端：信息管理
 * 管理员可以看到全部信息帖（含敏感级别），并可单条删除或批量删除。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { mediaUrl } from '@/api/items'
import { CATEGORIES } from '@/constants/dict'

const router = useRouter()

const list = ref([])
const total = ref(0)
const loading = ref(false)
const selected = ref([])
const overview = ref(null)
const keyword = ref('')
const typeFilter = ref('all')
const categoryFilter = ref('all')
const page = ref(1)
const size = ref(20)

async function loadOverview() {
  try {
    overview.value = await request.get('/admin/overview')
  } catch (e) {
    overview.value = null
  }
}

async function load() {
  loading.value = true
  selected.value = []
  try {
    const params = { page: page.value, size: size.value }
    if (typeFilter.value !== 'all') params.type = typeFilter.value
    if (categoryFilter.value !== 'all') params.category = categoryFilter.value
    if (keyword.value) params.keyword = keyword.value
    const data = await request.get('/admin/items', { params })
    list.value = data.list || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function onSelect(rows) {
  selected.value = rows
}

async function removeOne(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除这条信息吗？\n\n《${row.title}》\n\n删除后该信息及其匹配、认领记录将一并移除，且无法恢复。`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  const res = await request.delete(`/admin/items/${row.item_id}`)
  ElMessage.success(`已删除《${res.title}》`)
  await Promise.all([load(), loadOverview()])
}

async function removeSelected() {
  if (!selected.value.length) return
  const ids = selected.value.map((r) => r.item_id)
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 条信息吗？删除后不可恢复。`,
      '批量删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  const res = await request.post('/admin/items/bulk-delete', { item_ids: ids })
  ElMessage.success(`已删除 ${res.deleted} 条`)
  await Promise.all([load(), loadOverview()])
}

function resetFilter() {
  keyword.value = ''
  typeFilter.value = 'all'
  categoryFilter.value = 'all'
  page.value = 1
  load()
}

onMounted(() => {
  load()
  loadOverview()
})

const totalPages = computed(() => Math.ceil(total.value / size.value) || 1)

/** 后端存的是 JSON 字符串，解析成数组供缩略图与预览 */
function parseImages(row) {
  const im = row?.images
  let arr = []
  if (Array.isArray(im)) arr = im
  else if (typeof im === 'string' && im.trim()) {
    try {
      const parsed = JSON.parse(im)
      arr = Array.isArray(parsed) ? parsed : []
    } catch {
      arr = []
    }
  }
  return arr.map(mediaUrl)
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">
          <span>管理端</span>
          <el-icon><ArrowRight /></el-icon>
          <span>信息管理</span>
        </div>
        <h1 class="page-title">信息管理</h1>
        <p class="page-sub">
          查看并清理全部信息帖。删除会连带移除该信息的匹配候选与认领申请，操作不可恢复。
        </p>
      </div>
      <div class="head-actions">
        <el-button
          type="danger"
          :disabled="!selected.length"
          @click="removeSelected"
        >
          <el-icon><Delete /></el-icon>&nbsp;批量删除{{ selected.length ? `（${selected.length}）` : '' }}
        </el-button>
        <el-button plain @click="load">
          <el-icon><Refresh /></el-icon>&nbsp;刷新
        </el-button>
      </div>
    </div>

    <div v-if="overview" class="stat-row">
      <div class="stat">
        <span class="n">{{ overview.items }}</span>
        <span class="l">信息总数</span>
      </div>
      <div class="stat">
        <span class="n">{{ overview.lost }}</span>
        <span class="l">失物帖</span>
      </div>
      <div class="stat">
        <span class="n">{{ overview.found }}</span>
        <span class="l">招领帖</span>
      </div>
      <div class="stat warn">
        <span class="n">{{ overview.sensitive }}</span>
        <span class="l">敏感信息</span>
      </div>
      <div class="stat">
        <span class="n">{{ overview.matches }}</span>
        <span class="l">匹配记录</span>
      </div>
    </div>

    <section class="panel filter-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索标题、描述…"
        clearable
        class="search"
        @keyup.enter="page = 1; load()"
        @clear="page = 1; load()"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-radio-group v-model="typeFilter" @change="page = 1; load()">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="lost">失物</el-radio-button>
        <el-radio-button value="found">招领</el-radio-button>
      </el-radio-group>

      <el-select v-model="categoryFilter" class="sel" @change="page = 1; load()">
        <el-option label="全部类别" value="all" />
        <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
      </el-select>

      <el-button type="primary" @click="page = 1; load()">
        <el-icon><Search /></el-icon>&nbsp;检索
      </el-button>
      <el-button text @click="resetFilter">重置</el-button>
    </section>

    <div class="panel table-panel" v-loading="loading">
      <el-table
        :data="list"
        style="width: 100%"
        row-key="item_id"
        @selection-change="onSelect"
        empty-text="暂无信息"
      >
        <el-table-column type="selection" width="46" />
        <el-table-column prop="item_id" label="ID" width="66" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === 'lost' ? 'danger' : 'success'" size="small" effect="light">
              {{ row.type === 'lost' ? '失物' : '招领' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column label="图片" width="90">
          <template #default="{ row }">
            <template v-if="parseImages(row).length">
              <el-image
                :src="parseImages(row)[0]"
                :preview-src-list="parseImages(row)"
                :initial-index="0"
                fit="cover"
                class="cell-img"
                preview-teleported
              />
              <span v-if="parseImages(row).length > 1" class="img-count">+{{ parseImages(row).length - 1 }}</span>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="110" />
        <el-table-column prop="location" label="地点" width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-txt">{{ row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="敏感" width="76">
          <template #default="{ row }">
            <el-tag
              v-if="String(row.sensitive_level) === 'sensitive' || String(row.sensitive_level) === '1'"
              type="warning"
              size="small"
              effect="plain"
            >
              敏感
            </el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="发布时间" width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="168" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="router.push(`/items/${row.item_id}/matches`)">
              <el-icon><MagicStick /></el-icon>&nbsp;匹配
            </el-button>
            <el-button type="danger" link @click="removeOne(row)">
              <el-icon><Delete /></el-icon>&nbsp;删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="muted">共 {{ total }} 条</span>
        <el-pagination
          v-model:current-page="page"
          :page-size="size"
          :total="total"
          layout="prev, pager, next"
          background
          @current-change="load"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.head-actions {
  display: flex;
  gap: 10px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat .n {
  font-size: 22px;
  font-weight: 720;
  color: var(--ink);
}

.stat .l {
  font-size: 12px;
  color: var(--muted);
}

.stat.warn .n {
  color: #b26a00;
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
  width: 240px;
}

.sel {
  width: 140px;
}

.table-panel {
  padding: 6px 14px 14px;
}

.status-txt {
  font-size: 12.5px;
  color: var(--muted);
}

.muted {
  color: #b6c0d0;
  font-size: 12.5px;
}

.cell-img {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  border: 1px solid var(--line);
  vertical-align: middle;
}

.img-count {
  font-size: 11px;
  color: var(--muted);
  margin-left: 4px;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
}

@media (max-width: 900px) {
  .stat-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .search,
  .sel {
    width: 100%;
  }
}
</style>
