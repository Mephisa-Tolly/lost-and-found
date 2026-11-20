<script setup>
import { computed } from 'vue'
import CategoryChip from './CategoryChip.vue'

const props = defineProps({
  candidate: { type: Object, required: true },
  index: { type: Number, default: 1 },
  decision: { type: String, default: null },
  reviewing: { type: Boolean, default: false },
  /** AI 语义通道当前是否真的可用（Key 已配置且最近一次调用成功） */
  aiSemanticOk: { type: Boolean, default: true },
  /** 不可用原因，用于 tooltip */
  aiDownReason: { type: String, default: '' },
  /** 只读模式（普通用户）：只展示匹配结果，不显示确认/忽略操作 */
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'ignore'])

const c = computed(() => props.candidate)
const item = computed(() => c.value.candidate || {})
const scorePct = computed(() => Math.round((c.value.score || 0) * 100))

const levelClass = computed(
  () => ({ 高: 'level-high', 中: 'level-mid', 低: 'level-low' }[c.value.level] || 'level-low'),
)

const ringColor = computed(
  () => ({ 高: '#10b981', 中: '#f59e0b', 低: '#94a3b8' }[c.value.level] || '#94a3b8'),
)

const decided = computed(() => props.decision)
const isConfident = computed(() => props.decision === 'confirmed')

// 徽标必须反映「这次结果是怎么算出来的」，而不是只反映 Key 有没有填
const srcLabel = computed(() => {
  if (c.value.source === 'semantic') return '语义相近'
  return props.aiSemanticOk ? '字面相似' : '字面相似 · 语义通道不可用'
})
const srcTip = computed(() => {
  if (c.value.source === 'semantic') return '该候选由大模型语义精排产出'
  if (props.aiSemanticOk) return '该候选由 TF-IDF 字面相似度产出'
  return `语义通道当前不可用（${props.aiDownReason || '原因未知'}），已自动降级为字面相似度计算`
})
</script>

<template>
  <article class="cand" :class="{ decided, ignored: decision === 'ignored' }">
    <div class="rank">{{ index }}</div>

    <div class="ring">
      <el-progress
        type="circle"
        :percentage="scorePct"
        :width="74"
        :stroke-width="7"
        :color="ringColor"
      >
        <template #default>
          <div class="ring-num">{{ scorePct }}<span>%</span></div>
          <div class="ring-label">相似度</div>
        </template>
      </el-progress>
    </div>

    <div class="body">
      <div class="line-1">
        <span class="lv" :class="levelClass">
          <span class="dot" />{{ c.level }}相似
        </span>
        <h4>{{ item.title || '候选记录' }}</h4>
        <el-tag size="small" effect="plain" round>{{ item.type === 'lost' ? '寻物' : '招领' }}</el-tag>
        <span class="src" :class="[c.source, { degraded: c.source !== 'semantic' && !aiSemanticOk }]">
          {{ srcLabel }}
        </span>
      </div>

      <div class="line-2">
        <CategoryChip :category="item.category" />
        <span class="meta"><el-icon><Location /></el-icon>{{ item.location }}</span>
        <span class="meta"><el-icon><Clock /></el-icon>{{ String(item.time || '').slice(5, 16) }}</span>
        <span v-if="item.color" class="meta"><el-icon><Brush /></el-icon>{{ item.color }}</span>
        <span v-if="item.brand" class="meta"><el-icon><PriceTag /></el-icon>{{ item.brand }}</span>
      </div>

      <p class="desc">{{ item.description }}</p>

      <div class="reasons">
        <span class="reasons-label">相似字段</span>
        <span v-for="(r, i) in c.reasons" :key="i" class="reason">{{ r }}</span>
      </div>
    </div>

    <div class="ops">
      <template v-if="readonly">
        <div v-if="decided" class="decided-tag" :class="isConfident ? 'ok' : 'no'">
          <el-icon><component :is="isConfident ? 'CircleCheckFilled' : 'RemoveFilled'" /></el-icon>
          {{ isConfident ? '已确认' : '已忽略' }}
        </div>
        <div v-else class="decided-tag pending-tag">
          <el-icon><Clock /></el-icon>
          待管理员确认
        </div>
      </template>
      <template v-else-if="!decided">
        <el-button
          type="primary"
          :loading="reviewing"
          @click="emit('confirm', c)"
        >
          <el-icon><Select /></el-icon>&nbsp;确认匹配
        </el-button>
        <el-button plain :disabled="reviewing" @click="emit('ignore', c)">
          <el-icon><CloseBold /></el-icon>&nbsp;忽略
        </el-button>
      </template>
      <div v-else class="decided-tag" :class="isConfident ? 'ok' : 'no'">
        <el-icon><component :is="isConfident ? 'CircleCheckFilled' : 'RemoveFilled'" /></el-icon>
        {{ isConfident ? '已确认' : '已忽略' }}
      </div>
    </div>
  </article>
</template>

<style scoped>
.cand {
  position: relative;
  display: flex;
  gap: 20px;
  padding: 20px 22px 20px 26px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  transition: box-shadow 0.22s ease, border-color 0.22s ease, opacity 0.22s ease;
}

.cand:hover {
  box-shadow: var(--shadow);
  border-color: #dfe3f2;
}

.cand.decided {
  border-color: #cdeee2;
  background: linear-gradient(180deg, #fbfefd, #fff);
}

.cand.ignored {
  opacity: 0.62;
  border-color: var(--line);
  background: #fcfcfd;
}

.rank {
  position: absolute;
  left: -11px;
  top: 22px;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 6px 14px -6px rgba(99, 102, 241, 0.9);
}

.ring {
  flex: none;
  display: grid;
  place-items: center;
  padding-top: 4px;
}

.ring-num {
  font-size: 17px;
  font-weight: 720;
  color: var(--ink);
  line-height: 1.1;
}

.ring-num span {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
  margin-left: 1px;
}

.ring-label {
  font-size: 10px;
  color: var(--muted);
  margin-top: 1px;
  letter-spacing: 0.3px;
}

.body {
  flex: 1;
  min-width: 0;
}

.line-1 {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 9px;
}

.line-1 h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lv {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 650;
  flex: none;
}

.src {
  margin-left: auto;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 5px;
  flex: none;
}

.src.semantic {
  color: #6d28d9;
  background: #f4f0ff;
}

.src.lexical {
  color: #475467;
  background: #f2f4f9;
}

.src.degraded {
  color: #92400e;
  background: #fffbeb;
  box-shadow: inset 0 0 0 1px #fde68a;
}

.line-2 {
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

.desc {
  margin: 0 0 11px;
  font-size: 13px;
  line-height: 1.65;
  color: #5c6a80;
}

.reasons {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}

.reasons-label {
  font-size: 11.5px;
  color: #98a2b3;
  font-weight: 600;
  margin-right: 2px;
}

.reason {
  font-size: 11.5px;
  color: #3f4a5f;
  background: #f6f7fb;
  border: 1px solid #eef0f6;
  border-radius: 6px;
  padding: 3px 8px;
}

.ops {
  flex: none;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  width: 128px;
}

.ops :deep(.el-button) {
  width: 100%;
  margin-left: 0;
}

.decided-tag {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 34px;
  border-radius: 9px;
  font-size: 12.5px;
  font-weight: 650;
}

.decided-tag.ok {
  color: #07835c;
  background: #e7f8f1;
}

.decided-tag.no {
  color: #667085;
  background: #f2f4f9;
}

.pending-tag {
  color: #b26a00;
  background: #fff4e0;
  font-size: 12px;
  text-align: center;
  line-height: 1.3;
  height: auto;
  padding: 7px 6px;
}
</style>
