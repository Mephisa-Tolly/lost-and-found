<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useItemStore } from '@/store/items'
import { createClaim } from '@/api/items'
import CategoryChip from '@/components/CategoryChip.vue'

const route = useRoute()
const router = useRouter()
const store = useItemStore()

const item = computed(() => store.current)
const isLost = computed(() => item.value?.type === 'lost')

const claimVisible = ref(false)
const claimForm = ref({ applicant: '', answers: '' })
const submitting = ref(false)
const loadError = ref('')

onMounted(async () => {
  try {
    await store.loadItem(route.params.id)
    if (!store.current) loadError.value = '未找到该物品记录'
  } catch (e) {
    loadError.value = '未找到该物品记录，可能已被删除或链接有误'
  }
})

const metaRows = computed(() => {
  const it = item.value
  if (!it) return []
  return [
    { label: isLost.value ? '丢失地点' : '拾获地点', value: it.location, icon: 'Location' },
    { label: isLost.value ? '丢失时间' : '拾获时间', value: String(it.time).slice(0, 16), icon: 'Clock' },
    { label: '颜色', value: it.color || '未填写', icon: 'Brush' },
    { label: '品牌', value: it.brand || '未填写', icon: 'PriceTag' },
    { label: '当前状态', value: it.status, icon: 'Flag' },
    { label: '发布方式', value: it.anonymous ? '匿名发布' : '实名发布', icon: 'Hide' },
  ]
})

async function submitClaim() {
  if (!claimForm.value.answers.trim()) {
    ElMessage.warning('必须填写私密特征核验答案')
    return
  }
  submitting.value = true
  try {
    await createClaim(item.value.item_id, claimForm.value)
    claimVisible.value = false
    ElMessage.success('认领申请已提交，等待拾得者确认与管理员二次核验')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-loading="store.loading" class="page">
    <template v-if="item">
      <div class="crumb">
        <span class="link" @click="router.push('/items')">信息池</span>
        <el-icon><ArrowRight /></el-icon>
        <span>物品详情</span>
        <el-icon><ArrowRight /></el-icon>
        <span>#{{ item.item_id }}</span>
      </div>

      <div class="layout">
        <div class="left">
          <section class="panel hero">
            <div class="hero-top">
              <span class="type-badge" :class="isLost ? 'lost' : 'found'">
                {{ isLost ? '寻物' : '招领' }}
              </span>
              <h1>{{ item.title }}</h1>
              <span class="status-chip">{{ item.status }}</span>
            </div>

            <div class="hero-tags">
              <CategoryChip :category="item.category" size="lg" />
              <span v-if="item.sensitive_level" class="chip sens">
                <el-icon><Lock /></el-icon>敏感物品
              </span>
              <span v-if="item.anonymous" class="chip anon">
                <el-icon><Hide /></el-icon>匿名发布
              </span>
            </div>

            <div class="meta-grid">
              <div v-for="m in metaRows" :key="m.label" class="meta-cell">
                <div class="meta-label">
                  <el-icon><component :is="m.icon" /></el-icon>{{ m.label }}
                </div>
                <div class="meta-value">{{ m.value }}</div>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">物品描述</h2>
            </div>
            <div class="panel-pad desc-body">
              <p>{{ item.description }}</p>
              <div v-if="item.images && item.images.length" class="img-row">
                <el-image
                  v-for="(src, i) in item.images"
                  :key="i"
                  :src="src"
                  :preview-src-list="item.images"
                  :initial-index="i"
                  fit="cover"
                  class="item-img"
                  preview-teleported
                />
              </div>
              <el-alert
                v-if="item.sensitive_level"
                type="warning"
                :closable="false"
                show-icon
                title="敏感物品：关键细节不公开"
                description="该记录属于证件 / 银行卡 / 钥匙类，页面不展示凭证号、卡号等关键信息，认领须通过私密特征核验与管理端二次核验。"
                class="sens-alert"
              />
              <div class="privacy-note">
                <el-icon><InfoFilled /></el-icon>
                联系方式默认隐藏，匹配成功且双方确认后才可见。
              </div>
            </div>
          </section>
        </div>

        <aside class="right">
          <section class="panel action-card">
            <h3>可执行操作</h3>
            <el-button type="primary" size="large" class="block" @click="router.push(`/items/${item.item_id}/matches`)">
              <el-icon><MagicStick /></el-icon>&nbsp;查看 AI 匹配候选
            </el-button>
            <el-button v-if="!isLost" size="large" class="block" @click="claimVisible = true">
              <el-icon><Tickets /></el-icon>&nbsp;这是我要找的，申请认领
            </el-button>
            <p class="action-tip">
              AI 只给出候选，不判定归属。确认候选后仍需私密特征核验、拾得者确认与管理员二次核验。
            </p>
          </section>

          <section class="panel flow-card">
            <h3>认领流程</h3>
            <ol class="flow">
              <li><span>1</span>提交认领申请并回答私密特征</li>
              <li><span>2</span>拾得者初步确认</li>
              <li><span>3</span>管理员二次核验</li>
              <li><span>4</span>双方确认后发放联系方式</li>
            </ol>
          </section>
        </aside>
      </div>
    </template>

    <div v-if="loadError" class="panel empty">
      <div class="empty-icon"><el-icon><Warning /></el-icon></div>
      <div>{{ loadError }}</div>
      <el-button plain style="margin-top: 16px" @click="router.push('/items')">返回信息池</el-button>
    </div>

    <el-dialog v-model="claimVisible" title="申请认领" width="480" align-center>
      <el-form label-position="top">
        <el-form-item label="你的称呼">
          <el-input v-model="claimForm.applicant" placeholder="选填，默认匿名申请人" />
        </el-form-item>
        <el-form-item label="私密特征核验（必填）">
          <el-input
            v-model="claimForm.answers"
            type="textarea"
            :rows="3"
            placeholder="请描述只有物主才知道的细节，例如：杯底左侧有磕碰、贴着小熊贴纸"
          />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="答错将被驳回"
          description="核验答案仅拾得者与管理员可见，失主端不展示标准答案。"
        />
      </el-form>
      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitClaim">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.link {
  cursor: pointer;
  color: var(--primary);
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  align-items: start;
}

.left {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero {
  padding: 26px 28px 22px;
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.hero-top h1 {
  margin: 0;
  font-size: 23px;
  font-weight: 720;
  letter-spacing: -0.3px;
  color: var(--ink);
}

.type-badge {
  font-size: 11.5px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 7px;
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

.status-chip {
  margin-left: auto;
  font-size: 12px;
  font-weight: 650;
  color: #1d4ed8;
  background: #e8eeff;
  padding: 4px 10px;
  border-radius: 8px;
}

.hero-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.chip.sens {
  background: #fef3f2;
  color: #b42318;
}

.chip.anon {
  background: #f4f0ff;
  color: #6d28d9;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px 18px;
  padding-top: 18px;
  border-top: 1px dashed var(--line-strong);
}

.meta-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: #98a2b3;
  margin-bottom: 5px;
}

.meta-value {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink-2);
}

.desc-body p {
  margin: 0 0 14px;
  font-size: 14px;
  line-height: 1.85;
  color: #475467;
}

.img-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 0 0 14px;
}

.item-img {
  width: 132px;
  height: 132px;
  border-radius: 10px;
  border: 1px solid var(--line);
  overflow: hidden;
}

.sens-alert {
  border-radius: 12px;
  margin-bottom: 14px;
}

.privacy-note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #98a2b3;
  background: #f8f9fc;
  border-radius: 10px;
  padding: 10px 13px;
}

.right {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 80px;
}

.action-card,
.flow-card {
  padding: 20px;
}

.action-card h3,
.flow-card h3 {
  margin: 0 0 14px;
  font-size: 14px;
  font-weight: 680;
  color: var(--ink);
}

.block {
  width: 100%;
  margin: 0 0 10px;
}

.action-tip {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: #98a2b3;
}

.flow {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.flow li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
  color: var(--muted);
}

.flow li span {
  width: 21px;
  height: 21px;
  flex: none;
  border-radius: 7px;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
  background: var(--primary-soft);
}

@media (max-width: 1180px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .right {
    position: static;
  }
}
</style>
