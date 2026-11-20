/**
 * axios 封装层
 * —— 全站唯一的数据出入口，所有请求都走真实后端，不再有本地假数据。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 后端服务地址
// - 打包后（8000 端口）页面和接口同源，用相对路径 /api/v1，手机/局域网访问也能用
// - 开发模式（5173 端口热更新）页面在 5173、后端在 8000，用绝对地址
const API_BASE = window.location.port === '5173'
  ? 'http://localhost:8000/api/v1'
  : '/api/v1'

const request = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：留出鉴权位（当前课程 Demo 无登录态）
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('lf_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截：统一拆包 { code, msg/message, data }
request.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body.code !== 'undefined') {
      // 后端成功码为 200
      if (body.code === 200 || body.code === 0) return body.data
      ElMessage.error(body.msg || body.message || '请求失败')
      return Promise.reject(new Error(body.msg || body.message || '请求失败'))
    }
    // 未包装的原始响应（如 404 直接返回 detail）
    return body
  },
  (error) => {
    const detail = error?.response?.data?.detail || error?.response?.data?.msg
    const msg =
      detail ||
      (error.code === 'ECONNABORTED'
        ? '请求超时，请稍后重试'
        : '连接不上后端服务，请确认后端已在 8000 端口启动')
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

export { API_BASE }
export default request
