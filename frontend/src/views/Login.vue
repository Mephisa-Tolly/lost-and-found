<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth = useAuthStore()

const form = ref({ username: '', password: '' })
const formRef = ref()
const tips = ref(false)

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    const data = await auth.login(form.value.username.trim(), form.value.password.trim())
    ElMessage.success(`欢迎，${data.role_name} ${data.username}`)
    router.replace(auth.isAdmin ? '/admin' : '/square')
  } catch (e) {
    /* 错误提示由请求拦截器统一弹出 */
  }
}

// 演示账号快捷填充：课堂验收方便，真实部署可删掉这一段
function fill(role) {
  form.value = role === 'admin'
    ? { username: 'admin', password: 'admin123' }
    : { username: 'user', password: 'user123' }
}

onMounted(() => {
  if (auth.isLogged) router.replace(auth.isAdmin ? '/admin' : '/square')
})
</script>

<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">
          <el-icon><Aim /></el-icon>
        </div>
        <div>
          <div class="brand-name">校园智能失物招领</div>
          <div class="brand-sub">Campus Lost &amp; Found · V3.0</div>
        </div>
      </div>

      <h2 class="title">登录</h2>
      <p class="sub">使用你的账号登录，系统将按角色进入对应界面</p>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" @submit.prevent="submit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="账号" clearable @keyup.enter="submit">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            show-password
            @keyup.enter="submit"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" class="submit" :loading="auth.loading" @click="submit">
          登 录
        </el-button>
      </el-form>

      <div class="foot">
        <span class="link" @click="tips = !tips">去注册</span>
        <span class="tip">（演示系统暂未开放注册）</span>
      </div>

      <div v-if="tips" class="demo">
        <div class="demo-title">演示账号（点击自动填入）</div>
        <div class="demo-row">
          <el-button size="small" plain @click="fill('user')">用户 user / user123</el-button>
          <el-button size="small" plain @click="fill('admin')">管理员 admin / admin123</el-button>
        </div>
        <div class="demo-hint">
          用户端：发布失物 / 招领、浏览广场、查看 AI 匹配结果（只读）。<br />
          管理端：信息管理、确认匹配、认领审核。
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: radial-gradient(1000px 500px at 15% 5%, #eef2ff 0%, transparent 55%),
    radial-gradient(900px 460px at 95% 95%, #e6fffb 0%, transparent 55%), #f6f8fc;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 30px 30px 22px;
  box-shadow: 0 20px 50px -28px rgba(28, 40, 74, 0.35);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 22px;
}

.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 19px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
}

.brand-sub {
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 2px;
}

.title {
  font-size: 23px;
  font-weight: 720;
  color: var(--ink);
  margin: 0 0 6px;
}

.sub {
  font-size: 12.5px;
  color: var(--muted);
  margin: 0 0 20px;
}

.submit {
  width: 100%;
  height: 42px;
  font-size: 15px;
  letter-spacing: 2px;
  border-radius: 10px;
}

.foot {
  margin-top: 16px;
  text-align: center;
  font-size: 12.5px;
}

.link {
  color: var(--primary);
  cursor: pointer;
  font-weight: 600;
}

.tip {
  color: #b6c0d0;
}

.demo {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 11px;
  background: #f7f9fe;
  border: 1px dashed #d9e2f5;
}

.demo-title {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
}

.demo-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.demo-hint {
  font-size: 11.5px;
  color: #98a2b3;
  margin-top: 8px;
  line-height: 1.6;
}

@media (max-width: 480px) {
  .login-card {
    padding: 22px 18px 16px;
  }
}
</style>
