<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useItemStore } from '@/store/items'
import { fetchMatches } from '@/api/items'
import { CATEGORIES, LOCATIONS, SENSITIVE_CATEGORIES } from '@/constants/dict'

const props = defineProps({
  type: { type: String, required: true }, // 'lost' | 'found'
})

const router = useRouter()
const store = useItemStore()
const formRef = ref()

const isLost = computed(() => props.type === 'lost')
const word = computed(() => (isLost.value ? '失物' : '招领'))

const form = reactive({
  title: '',
  category: '',
  location: '',
  date: '',
  time: '',
  color: '',
  brand: '',
  description: '',
  anonymous: false,
  contact: '',
  private_features: '',
})

const rules = {
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择物品类别', trigger: 'change' }],
  location: [{ required: true, message: '请选择或填写地点', trigger: 'change' }],
  date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  description: [{ required: true, message: '请填写详细描述，这是匹配的主要依据', trigger: 'blur' }],
}

const isSensitive = computed(() => SENSITIVE_CATEGORIES.includes(form.category))
const descLen = computed(() => form.description.length)

/** 禁止选择未来日期：失物不可能在未来丢失 */
function disabledDate(d) {
  const today = new Date()
  today.setHours(23, 59, 59, 999)
  return d.getTime() > today.getTime()
}

/** 图片大小与格式校验：不合法的文件直接从列表移除，禁止进入提交 */
const MAX_IMG_MB = 5
const MAX_IMG_COUNT = 3
const fileList = ref([])

function isImageFile(file) {
  const t = file?.raw?.type || file?.type || ''
  if (/^image\//.test(t)) return true
  // 个别浏览器对图片不给 MIME，用扩展名兜底（仍要求以图片扩展名结尾）
  return /\.(jpe?g|png|webp|gif|bmp)$/i.test(file?.name || '')
}

function handleImgChange(file, files) {
  const realSize = file.raw?.size ?? file.size ?? 0
  if (!isImageFile(file)) {
    ElMessage.error('只能上传图片文件（jpg/png/webp/gif/bmp），其他类型已拦截')
    fileList.value = files.filter((f) => f.uid !== file.uid)
    return
  }
  if (realSize / 1024 / 1024 > MAX_IMG_MB) {
    ElMessage.error(`图片不能超过 ${MAX_IMG_MB}MB，当前 ${(realSize / 1024 / 1024).toFixed(1)}MB`)
    fileList.value = files.filter((f) => f.uid !== file.uid)
    return
  }
  fileList.value = files
}

function handleImgExceed() {
  ElMessage.warning(`最多上传 ${MAX_IMG_COUNT} 张图片`)
}

/** 压缩图片：最长边 1400px、JPEG 0.85，手机原图 3MB 通常压到 300KB 以内 */
function compressImage(file) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onerror = () => resolve('')
    reader.onload = () => {
      const dataUrl = String(reader.result || '')
      // GIF 压缩会丢帧，原样上传
      if (/^image\/gif$/i.test(file.raw?.type || '')) return resolve(dataUrl)
      const img = new Image()
      img.onerror = () => resolve(dataUrl)
      img.onload = () => {
        const MAX = 1400
        let { width: w, height: h } = img
        if (Math.max(w, h) > MAX) {
          const scale = MAX / Math.max(w, h)
          w = Math.round(w * scale)
          h = Math.round(h * scale)
        }
        const canvas = document.createElement('canvas')
        canvas.width = w
        canvas.height = h
        canvas.getContext('2d').drawImage(img, 0, 0, w, h)
        resolve(canvas.toDataURL('image/jpeg', 0.85))
      }
      img.src = dataUrl
    }
    reader.readAsDataURL(file.raw)
  })
}

/** 提交前把已校验的图片压成 data:image/...;base64 数组（后端落盘存文件） */
async function readImages() {
  const files = fileList.value.filter((f) => f.raw && isImageFile(f))
  const arr = await Promise.all(files.map(compressImage))
  return arr.filter(Boolean)
}

const resultVisible = ref(false)
const candidates = ref([])
const createdId = ref(null)

watch(
  () => props.type,
  () => {
    formRef.value?.resetFields()
    fileList.value = []
    Object.assign(form, {
      title: '', category: '', location: '', date: '', time: '', color: '', brand: '',
      description: '', anonymous: false, contact: '', private_features: '',
    })
  },
)

async function submit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) {
      ElMessage.warning('请先补全必填项')
      return
    }
    const images = await readImages()
    const payload = {
      type: props.type,
      title: form.title,
      category: form.category,
      location: form.location,
      time: `${form.date} ${form.time || '00:00'}`,
      color: form.color,
      brand: form.brand,
      description: form.description,
      images,
      anonymous: form.anonymous ? 1 : 0,
      contact: form.contact,
      sensitive_level: isSensitive.value ? 1 : 0,
      private_features: form.private_features,
    }
    const created = await store.create(payload)
    createdId.value = created.item_id
    // 图片已随这条记录入库，清空选择，避免下一条重复带图
    fileList.value = []
    const res = await fetchMatches(created.item_id)
    candidates.value = res.list || []
    resultVisible.value = true
  })
}

function goMatches() {
  resultVisible.value = false
  router.push(`/items/${createdId.value}/matches`)
}
function goList() {
  resultVisible.value = false
  router.push('/items')
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">
          <span>信息发布</span>
          <el-icon><ArrowRight /></el-icon>
          <span>发布{{ word }}</span>
        </div>
        <h1 class="page-title">发布{{ word }}信息</h1>
        <p class="page-sub">
          填写结构化字段后，系统会自动与信息池中的存量记录做双向比对，命中即推送 Top-3 候选。
        </p>
      </div>
      <el-button plain @click="router.push('/items')">
        <el-icon><Files /></el-icon>&nbsp;返回信息池
      </el-button>
    </div>

    <div class="layout">
      <section class="panel form-panel">
        <div class="panel-head">
          <h2 class="panel-title">{{ isLost ? '丢失信息' : '拾获信息' }}填写</h2>
          <span class="panel-hint">带 <em>*</em> 为必填项</span>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          class="form-body"
          @submit.prevent
        >
          <div class="grid">
            <el-form-item label="标题" prop="title" class="span-2">
              <el-input
                v-model="form.title"
                maxlength="30"
                show-word-limit
                :placeholder="isLost ? '例如：丢失银色保温杯' : '例如：捡到一个银色水杯'"
              />
            </el-form-item>

            <el-form-item label="物品类别" prop="category">
              <el-select v-model="form.category" placeholder="请选择类别" style="width: 100%">
                <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>

            <el-form-item :label="isLost ? '丢失地点' : '拾获地点'" prop="location">
              <el-select
                v-model="form.location"
                filterable
                allow-create
                default-first-option
                placeholder="选择或输入具体地点"
                style="width: 100%"
              >
                <el-option v-for="l in LOCATIONS" :key="l" :label="l" :value="l" />
              </el-select>
            </el-form-item>

            <el-form-item label="日期" prop="date">
              <el-date-picker
                v-model="form.date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                :disabled-date="disabledDate"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="时间">
              <el-time-picker
                v-model="form.time"
                format="HH:mm"
                value-format="HH:mm"
                placeholder="选择时间"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="颜色（选填）">
              <el-input v-model="form.color" placeholder="例如：银色" maxlength="10" />
            </el-form-item>

            <el-form-item label="品牌（选填）">
              <el-input v-model="form.brand" placeholder="例如：膳魔师" maxlength="20" />
            </el-form-item>

            <el-form-item label="详细描述" prop="description" class="span-2">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="4"
                maxlength="300"
                show-word-limit
                placeholder="描述外观、磨损、贴纸等可辨识特征。描述越具体，AI 匹配越准。"
              />
              <div class="field-tip">
                <el-icon><InfoFilled /></el-icon>
                当前 {{ descLen }}/300 字。请勿填写学号、身份证号等敏感信息。
              </div>
            </el-form-item>

            <el-form-item :label="`图片（选填，最多 ${MAX_IMG_COUNT} 张）`" class="span-2">
              <div class="upload-block">
                <el-upload
                  v-model:file-list="fileList"
                  list-type="picture-card"
                  :auto-upload="false"
                  :limit="MAX_IMG_COUNT"
                  accept="image/jpeg,image/png,image/webp,image/gif,image/bmp"
                  :on-change="handleImgChange"
                  :on-exceed="handleImgExceed"
                >
                  <el-icon><Plus /></el-icon>
                </el-upload>
                <div class="field-tip">
                  <el-icon><WarningFilled /></el-icon>
                  单张不超过 {{ MAX_IMG_MB }}MB；上传前请自行遮挡人脸、证件号与屏幕内容。
                </div>
              </div>
            </el-form-item>

            <el-form-item label="私密特征（选填，仅用于认领核验，不公开展示）" class="span-2">
              <el-input
                v-model="form.private_features"
                placeholder="例如：杯底左侧有磕碰、贴着小熊贴纸。认领人必须答对才能进入核验。"
              />
            </el-form-item>
          </div>

          <el-alert
            v-if="isSensitive"
            type="warning"
            :closable="false"
            show-icon
            class="sensitive-alert"
            title="该类别为敏感物品"
            description="证件、银行卡、钥匙类信息发布后，关键细节不对外展示，认领需通过私密特征核验与管理员二次核验。"
          />

          <div class="switch-row">
            <el-switch v-model="form.anonymous" />
            <div>
              <div class="switch-title">匿名发布</div>
              <div class="switch-sub">开启后公开页面不展示姓名、学号与头像</div>
            </div>
          </div>

          <el-form-item label="联系方式（选填，默认隐藏）" class="contact-item">
            <el-input
              v-model="form.contact"
              placeholder="仅在匹配成功且双方确认后可见"
              :disabled="form.anonymous"
            />
          </el-form-item>

          <div class="form-actions">
            <el-button @click="formRef.resetFields()">重置</el-button>
            <el-button type="primary" size="large" :loading="store.submitting" @click="submit">
              <el-icon><Promotion /></el-icon>&nbsp;提交发布并匹配
            </el-button>
          </div>
        </el-form>
      </section>

      <aside class="tips">
        <div class="tip-card">
          <div class="tip-icon"><el-icon><MagicStick /></el-icon></div>
          <h3>发布后会自动匹配</h3>
          <p>系统先按类别、地点、时间窗做结构化硬过滤，再用同义词归一与语义通道排序，返回 Top-3 候选。</p>
        </div>
        <div class="tip-card">
          <div class="tip-icon amber"><el-icon><View /></el-icon></div>
          <h3>匹配结果你也能看</h3>
          <p>发布后可在广场点「匹配」查看候选；归属确认由管理员在管理端完成，你无需操作，也不会误判。</p>
        </div>
        <div class="tip-card">
          <div class="tip-icon rose"><el-icon><Lock /></el-icon></div>
          <h3>隐私默认保护</h3>
          <p>联系方式默认隐藏；敏感物品不公开关键细节；匿名发布不展示身份。</p>
        </div>
      </aside>
    </div>

    <el-dialog v-model="resultVisible" width="520" :show-close="false" align-center>
      <div class="result">
        <div class="result-icon">
          <el-icon><CircleCheckFilled /></el-icon>
        </div>
        <h3>发布成功</h3>
        <p class="result-sub">
          已写入统一信息池。
          <template v-if="candidates.length">
            系统自动比对了存量记录，为你找到 <b>{{ candidates.length }}</b> 条候选。
          </template>
          <template v-else> 暂无匹配候选，可在信息池中继续浏览。 </template>
        </p>
        <div v-if="candidates.length" class="mini-list">
          <div v-for="c in candidates" :key="c.match_id" class="mini-row">
            <span class="mini-score">{{ Math.round(c.score * 100) }}%</span>
            <span class="mini-title">{{ c.candidate?.title }}</span>
            <span
              class="chip"
              :class="{ 'level-high': c.level === '高', 'level-mid': c.level === '中', 'level-low': c.level === '低' }"
            >{{ c.level }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="goList">留在信息池</el-button>
        <el-button v-if="candidates.length" type="primary" @click="goMatches">
          查看匹配结果
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 20px;
  align-items: start;
}

.form-panel {
  overflow: hidden;
}

.panel-hint em {
  color: #ef4444;
  font-style: normal;
}

.form-body {
  padding: 22px 24px 8px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 18px;
}

.span-2 {
  grid-column: span 2;
}

.upload-block {
  width: 100%;
}

/* 默认 148×148 的图片卡在表单里留白过多，缩到 104 并统一圆角 */
.upload-block :deep(.el-upload--picture-card),
.upload-block :deep(.el-upload-list--picture-card .el-upload-list__item) {
  width: 104px;
  height: 104px;
  border-radius: 10px;
}

.upload-block :deep(.el-upload--picture-card) {
  border: 1px dashed #d6dae6;
  background: #fbfcfe;
}

.upload-block :deep(.el-upload--picture-card:hover) {
  border-color: var(--primary);
}

.upload-block :deep(.el-upload-list--picture-card) {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.field-tip {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #98a2b3;
  margin-top: 6px;
  line-height: 1.5;
}

.field-tip .el-icon {
  font-size: 13px;
  flex: none;
}

.sensitive-alert {
  margin: 4px 0 18px;
  border-radius: 12px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f8f9fc;
  border: 1px solid var(--line);
  margin-bottom: 16px;
}

.switch-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink);
}

.switch-sub {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.contact-item {
  margin-bottom: 8px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 0 22px;
  border-top: 1px solid var(--line);
  margin-top: 8px;
}

/* 右侧提示 */
.tips {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 80px;
}

.tip-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 18px 18px 16px;
}

.tip-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 17px;
  margin-bottom: 10px;
}

.tip-icon.amber {
  background: #fff6e6;
  color: #d98200;
}

.tip-icon.rose {
  background: #fdeef2;
  color: #db2777;
}

.tip-card h3 {
  margin: 0 0 6px;
  font-size: 13.5px;
  font-weight: 650;
  color: var(--ink);
}

.tip-card p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--muted);
}

/* 结果弹窗 */
.result {
  text-align: center;
  padding: 8px 6px 2px;
}

.result-icon {
  width: 54px;
  height: 54px;
  margin: 0 auto 12px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-size: 28px;
  color: #10b981;
  background: #e7f8f1;
}

.result h3 {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 700;
}

.result-sub {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.7;
}

.mini-list {
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
}

.mini-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
}

.mini-row + .mini-row {
  border-top: 1px solid var(--line);
}

.mini-score {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  width: 40px;
}

.mini-title {
  flex: 1;
  font-size: 13px;
  color: var(--ink-2);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

@media (max-width: 1180px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .tips {
    position: static;
    flex-direction: row;
  }
  .tip-card {
    flex: 1;
  }
}

@media (max-width: 640px) {
  /* 手机上一行放两个输入框只剩 150px，全部改成单列 */
  .grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: span 1;
  }

  .form-body {
    padding: 16px 14px 4px;
  }

  .tips {
    flex-direction: column;
  }
}
</style>
