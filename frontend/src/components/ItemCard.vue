<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { mediaUrl } from '@/api/items'
import CategoryChip from './CategoryChip.vue'

const props = defineProps({
  item: { type: Object, required: true },
})

const router = useRouter()

const isLost = computed(() => props.item.type === 'lost')

const STATUS_STYLE = {
  待匹配: { color: '#5a667d', bg: '#f1f3f8' },
  已匹配: { color: '#1d4ed8', bg: '#e8eeff' },
  认领中: { color: '#b26a00', bg: '#fff4e0' },
  已确认: { color: '#07835c', bg: '#e7f8f1' },
  已关闭: { color: '#667085', bg: '#f1f3f8' },
  无人认领: { color: '#b42318', bg: '#fef0ef' },
}

const statusStyle = computed(() => STATUS_STYLE[props.item.status] || STATUS_STYLE['待匹配'])

const timeText = computed(() => String(props.item.time || '').slice(5, 16))

// 广场列表来自后端原始字段，images 是 JSON 字符串；详情页则已适配成数组，两种都兼容
const images = computed(() => {
  const im = props.item.images
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
})
const thumb = computed(() => images.value[0] || '')

function goDetail() {
  router.push(`/items/${props.item.item_id}`)
}
function goMatches() {
  router.push(`/items/${props.item.item_id}/matches`)
}
</script>

<template>
  <article class="item-card" @click="goDetail">
    <div class="side" :class="isLost ? 'lost' : 'found'">
      <el-icon><component :is="isLost ? 'Search' : 'Box'" /></el-icon>
    </div>

    <div class="body">
      <div class="row-1">
        <span class="type-badge" :class="isLost ? 'lost' : 'found'">
          {{ isLost ? '寻物' : '招领' }}
        </span>
        <h3 class="title">{{ item.title }}</h3>
        <span class="status" :style="{ color: statusStyle.color, background: statusStyle.bg }">
          {{ item.status }}
        </span>
      </div>

      <div class="row-2">
        <CategoryChip :category="item.category" />
        <span class="meta"><el-icon><Location /></el-icon>{{ item.location }}</span>
        <span class="meta"><el-icon><Clock /></el-icon>{{ timeText }}</span>
        <span v-if="item.color" class="meta"><el-icon><Brush /></el-icon>{{ item.color }}</span>
        <span v-if="item.brand" class="meta"><el-icon><PriceTag /></el-icon>{{ item.brand }}</span>
        <span v-if="item.anonymous" class="meta anon"><el-icon><Hide /></el-icon>匿名</span>
      </div>

      <p class="desc">{{ item.description }}</p>
    </div>

    <div v-if="thumb" class="thumb-col" @click.stop>
      <el-image
        :src="thumb"
        fit="cover"
        class="thumb"
        :preview-src-list="images"
        :initial-index="0"
        preview-teleported
      />
    </div>

    <div class="actions">
      <el-button text size="small" @click.stop="goDetail">
        详情<el-icon class="el-icon--right"><ArrowRight /></el-icon>
      </el-button>
      <el-button type="primary" plain size="small" @click.stop="goMatches">
        <el-icon><MagicStick /></el-icon>&nbsp;匹配
      </el-button>
    </div>
  </article>
</template>

<style scoped>
.item-card {
  display: flex;
  align-items: stretch;
  gap: 16px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.item-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow);
  border-color: #dfe3f2;
}

.side {
  width: 46px;
  flex: none;
  border-radius: 13px;
  display: grid;
  place-items: center;
  font-size: 21px;
}

.side.lost {
  background: linear-gradient(135deg, #fff1f0, #ffe7e3);
  color: #e0453b;
}

.side.found {
  background: linear-gradient(135deg, #eaf7f3, #dff3ff);
  color: #0d9488;
}

.body {
  flex: 1;
  min-width: 0;
}

.row-1 {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 9px;
}

.type-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
  letter-spacing: 0.4px;
  flex: none;
}

.type-badge.lost {
  color: #d92d20;
  background: #fef1ef;
}

.type-badge.found {
  color: #0e9384;
  background: #e8f8f4;
}

.title {
  font-size: 15.5px;
  font-weight: 650;
  margin: 0;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status {
  margin-left: auto;
  flex: none;
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 7px;
}

.row-2 {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 9px;
}

.meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: var(--muted);
}

.meta .el-icon {
  font-size: 13px;
  color: #a3aec2;
}

.anon {
  color: #7c6cd6;
}

.anon .el-icon {
  color: #a294ea;
}

.desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #5c6a80;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  /* 固定两行高度：有图 / 无图的卡片因此高度一致，列表不会参差不齐 */
  min-height: calc(1.65em * 2);
}

/* 缩略图独立成列，不再挤在描述区右下角把文字压窄 */
.thumb-col {
  flex: none;
  display: grid;
  place-items: center;
  padding-left: 4px;
}

.thumb {
  width: 76px;
  height: 76px;
  border-radius: 9px;
  border: 1px solid var(--line);
  cursor: zoom-in;
}

.actions {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  flex: none;
}

/* ---------------- 手机竖屏 ---------------- */
@media (max-width: 640px) {
  .item-card {
    gap: 10px;
    padding: 13px 13px 13px 12px;
  }

  .side {
    width: 34px;
    border-radius: 10px;
    font-size: 17px;
  }

  .row-1 {
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 7px;
  }

  /* 标题换行显示完整，不再被 icon/状态挤成一个字加省略号 */
  .title {
    order: 3;
    flex: 1 1 100%;
    font-size: 14.5px;
    line-height: 1.4;
    white-space: normal;
    overflow: visible;
    word-break: break-word;
  }

  .status {
    margin-left: auto;
    font-size: 11px;
    padding: 2px 7px;
  }

  .desc {
    font-size: 12.5px;
    line-height: 1.55;
    min-height: calc(1.55em * 2);
  }

  .thumb-col {
    padding-left: 0;
    align-self: flex-start;
  }

  .thumb {
    width: 58px;
    height: 58px;
    border-radius: 8px;
  }

  /* 手机上卡片换行，把「详情 / 匹配」放到底部一行，保证手机上也能直接点匹配 */
  .item-card {
    flex-wrap: wrap;
  }

  .actions {
    flex: 1 1 100%;
    flex-direction: row;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;
    padding-top: 8px;
    border-top: 1px dashed var(--line);
  }
}
</style>
