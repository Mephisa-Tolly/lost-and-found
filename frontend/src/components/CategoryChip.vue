<script setup>
import { computed } from 'vue'
import { CATEGORY_META } from '@/constants/dict'

const props = defineProps({
  category: { type: String, default: '其他' },
  size: { type: String, default: 'sm' },
})

const meta = computed(() => CATEGORY_META[props.category] || CATEGORY_META['其他'])
</script>

<template>
  <span
    class="chip cat-chip"
    :class="[size === 'lg' ? 'lg' : '']"
    :style="{ background: meta.bg, color: meta.color }"
  >
    <el-icon><component :is="meta.icon" /></el-icon>
    {{ category }}
  </span>
</template>

<style scoped>
.cat-chip {
  gap: 5px;
}
.cat-chip .el-icon {
  font-size: 12px;
}
.lg {
  height: 28px;
  padding: 0 12px;
  font-size: 12.5px;
}
.lg .el-icon {
  font-size: 14px;
}
</style>
