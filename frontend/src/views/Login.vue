<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth = useAuthStore()

const mode = ref('login') // login | register
const form = ref({ username: '', password: '' })
const regForm = ref({ username: '', password: '', confirm: '', role: 'user', admin_code: '' })
const formRef = ref()
const regFormRef = ref()
const regLoading = ref(false)

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const regRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度需为 2—20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6—64 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (r, v, cb) => cb(v === regForm.value.password ? undefined : new Error('两次输入的密码不一致')),
      trigger: 'blur',
    },
  ],
  admin_code: [
    {
      validator: (r, v, cb) => {
        if (regForm.value.role === 'admin' && !(v || '').trim()) cb(new Error('注册管理员需要验证码'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
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

async function submitRegister() {
  const valid = await regFormRef.value?.validate().catch(() => false)
  if (!valid) return
  regLoading.value = true
  try {
    await request.post('/auth/register', {
      username: regForm.value.username.trim(),
      password: regForm.value.password,
      role: regForm.value.role,
      admin_code: regForm.value.admin_code.trim(),
    })
    ElMessage.success('注册成功，请登录')
    form.value = { username: regForm.value.username.trim(), password: '' }
    mode.value = 'login'
  } catch (e) {
    /* 错误提示由请求拦截器统一弹出 */
  } finally {
    regLoading.value = false
  }
}

function switchMode(m) {
  mode.value = m
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
        </div>
      </div>

      <template v-if="mode === 'login'">
        <h2 class="title">登录</h2>

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
          还没有账号？<span class="link" @click="switchMode('register')">去注册</span>
        </div>
      </template>

      <template v-else>
        <h2 class="title">注册</h2>

        <el-form ref="regFormRef" :model="regForm" :rules="regRules" size="large" @submit.prevent="submitRegister">
          <el-form-item prop="username">
            <el-input v-model="regForm.username" placeholder="用户名（2—20 个字符）" clearable>
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="regForm.password" type="password" placeholder="密码（至少 6 位）" show-password>
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item prop="confirm">
            <el-input v-model="regForm.confirm" type="password" placeholder="确认密码" show-password>
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item label="注册身份">
            <el-radio-group v-model="regForm.role">
              <el-radio-button value="user">普通用户</el-radio-button>
              <el-radio-button value="admin">管理员</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="regForm.role === 'admin'" prop="admin_code">
            <el-input v-model="regForm.admin_code" placeholder="管理员验证码" clearable>
              <template #prefix><el-icon><Key /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-button type="primary" class="submit" :loading="regLoading" @click="submitRegister">
            注 册
          </el-button>
        </el-form>

        <div class="foot">
          已有账号？<span class="link" @click="switchMode('login')">去登录</span>
        </div>
      </template>
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

.title {
  font-size: 23px;
  font-weight: 720;
  color: var(--ink);
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
  color: var(--muted);
}

.link {
  color: var(--primary);
  cursor: pointer;
  font-weight: 600;
}

@media (max-width: 480px) {
  .login-card {
    padding: 22px 18px 16px;
  }
}
</style>
