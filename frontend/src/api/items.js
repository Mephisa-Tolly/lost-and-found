/**
 * 物品 / 匹配 / 认领 接口（V3.0）
 *
 * 本文件是「后端字段」与「页面字段」之间的唯一转换层：
 * 后端（王恒 FastAPI）返回的原始结构在这里统一转成页面需要的格式，
 * 页面组件（views / components）一行都不用改。
 */
import request from './request'

/* ============ 字段适配工具 ============ */

const API_ORIGIN =
  window.location.port === '5173' ? 'http://localhost:8000' : ''

/**
 * 图片地址补全：
 * - 线上同源部署时后端返回 /api/v1/media/xxx.jpg，直接用
 * - 本地 dev（5173）时页面与后端不同源，需要补成 http://localhost:8000/...
 */
export function mediaUrl(u) {
  if (!u) return ''
  if (/^(https?:|data:|blob:)/.test(u)) return u
  return `${API_ORIGIN}${u}`
}

/** 时间统一成 "YYYY-MM-DD HH:mm" */
function normTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 16)
}

/**
 * 后端 item -> 页面 item
 * 主要差异：sensitive_level 后端是 'normal'/'sensitive'，页面用 0/1 布尔判断；
 *          images 后端是字符串，页面用数组；contact 默认隐藏。
 */
export function adaptItem(raw) {
  if (!raw) return null
  let images = []
  if (Array.isArray(raw.images)) images = raw.images
  else if (typeof raw.images === 'string' && raw.images.trim()) {
    try {
      images = JSON.parse(raw.images)
    } catch (e) {
      images = raw.images.split(',').filter(Boolean)
    }
  }
  const sensitive = raw.sensitive_level
  return {
    ...raw,
    item_id: Number(raw.item_id),
    time: normTime(raw.time),
    created_at: normTime(raw.created_at),
    images: images.map(mediaUrl),
    anonymous: raw.anonymous === 1 || raw.anonymous === true,
    // 页面以 1 / 0 判断是否敏感
    sensitive_level: sensitive === 'sensitive' || sensitive === 1 || sensitive === '1' ? 1 : 0,
    contact: raw.contact || raw.contact_encrypted || '',
    private_features: raw.private_features || '',
  }
}

/** 后端 match -> 页面候选（页面需要 candidate 嵌套对象 + reasons 数组） */
function adaptMatch(raw) {
  if (!raw) return null
  return {
    match_id: raw.match_id,
    candidate_id: raw.candidate_id || raw.candidate_item_id,
    candidate: adaptItem(raw.candidate),
    score: Number(raw.score || 0),
    level: raw.level || '低',
    reasons: Array.isArray(raw.reasons) ? raw.reasons : [],
    source: raw.source || 'semantic',
    review: raw.review || null,
  }
}

/** 页面 payload -> 后端 ItemCreate（后端必填 time，且 created_by 缺省为 1） */
function toBackendItem(payload) {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const fallbackTime =
    `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ` +
    `${pad(now.getHours())}:${pad(now.getMinutes())}:00`
  return {
    type: payload.type === 'found' ? 'found' : 'lost',
    title: payload.title,
    category: payload.category,
    location: payload.location,
    time: normTime(payload.time) ? `${normTime(payload.time)}:00` : fallbackTime,
    description: payload.description,
    color: payload.color || null,
    brand: payload.brand || null,
    images: Array.isArray(payload.images) ? payload.images : [],
    anonymous: !!payload.anonymous,
    // 这两项以前被这一层吃掉了：表单填了也送不到后端，认领核验因此没有标准答案
    contact: payload.contact || '',
    private_features: payload.private_features || '',
    created_by: 1,
  }
}

/* ============ 对外接口 ============ */

/** 物品列表（分页/筛选） */
export async function fetchItems(params = {}) {
  const query = {
    page: params.page || 1,
    size: params.size || 100,
  }
  if (params.type && params.type !== 'all') query.type = params.type
  if (params.category && params.category !== 'all') query.category = params.category
  if (params.status && params.status !== 'all') query.status = params.status
  if (params.keyword) query.keyword = params.keyword

  const data = await request.get('/items', { params: query })
  const list = (data?.list || []).map(adaptItem)
  // 前端排序（后端按创建时间倒序返回，这里支持按时间/相似度切换）
  if (params.sort === 'time_asc') {
    list.sort((a, b) => String(a.time).localeCompare(String(b.time)))
  }
  return { total: data?.total ?? list.length, list }
}

/**
 * 拉取全部物品（自动翻页）。
 * 后端单页上限 100，测试阶段数据可能超过这个数，
 * 只用一页会导致第 101 条之后在列表里彻底消失。
 */
export async function fetchAllItems(params = {}, maxPages = 30) {
  const PAGE_SIZE = 100
  const all = []
  let total = 0
  for (let page = 1; page <= maxPages; page++) {
    const { list, total: t } = await fetchItems({ ...params, page, size: PAGE_SIZE })
    total = t
    all.push(...list)
    if (!list.length || all.length >= total) break
  }
  return { total, list: all }
}

/** 物品详情 */
export async function fetchItem(id) {
  const data = await request.get(`/items/${id}`)
  return adaptItem(data)
}

/** 发布寻物 / 招领 */
export async function createItem(payload) {
  const data = await request.post('/items', toBackendItem(payload))
  const itemId = data?.item_id
  // 后端返回后补一次详情，页面需要完整对象
  if (itemId) {
    try {
      return await fetchItem(itemId)
    } catch (e) {
      return { item_id: itemId, ...payload, status: '待匹配' }
    }
  }
  return data
}

/** 首页统计 */
export async function fetchStats() {
  const data = await request.get('/stats')
  return {
    total: data?.total || 0,
    lost: data?.lost || 0,
    found: data?.found || 0,
    matched: data?.matched || 0,
  }
}

/** 某物品的 AI 匹配候选（Top-3） */
export async function fetchMatches(id) {
  const data = await request.get(`/items/${id}/matches`)
  const list = (data?.list || []).map(adaptMatch)
  return { item_id: Number(id), total: list.length, list, item: adaptItem(data?.item) }
}

/** 待人工确认的匹配总览 */
export async function fetchPendingMatches() {
  const data = await request.get('/matches/pending')
  const list = (data?.list || []).map((row) => ({
    item: adaptItem(row.item),
    candidates: (row.candidates || []).map(adaptMatch),
    pending: row.pending || 0,
  }))
  return { total: data?.total ?? list.length, list }
}

/** 人工确认候选 */
export function confirmMatch(matchId) {
  return request.patch(`/matches/${matchId}/confirm`, { status: '已确认' })
}

/** 人工忽略候选 */
export function ignoreMatch(matchId) {
  return request.patch(`/matches/${matchId}/confirm`, { status: '已拒绝' })
}

/** 提交认领申请（found）/ 提交线索（lost），由后端按物品类型与 kind 双向校验 */
export function createClaim(itemId, payload) {
  return request.post(`/items/${itemId}/claims`, {
    applicant: payload?.applicant || '匿名用户',
    answers: payload?.answers || '',
    kind: payload?.kind || 'claim',
  })
}

/* ============ 认领申请（V3.0） ============ */

/** 我的认领申请 / 线索（用户端） */
export function fetchMyClaims() {
  return request.get('/claims/mine')
}

/** 全部认领申请（管理端）。kind: claim 认领 / clue 线索 / 不传 全部 */
export function fetchAdminClaims(params = {}) {
  const query = {}
  if (params.status && params.status !== 'all') query.status = params.status
  if (params.kind && params.kind !== 'all') query.kind = params.kind
  if (params.keyword) query.keyword = params.keyword
  return request.get('/admin/claims', { params: query })
}

/** 审核认领申请：action = 'approve' | 'reject' */
export function reviewClaim(claimId, action, note = '') {
  return request.post(`/admin/claims/${claimId}/review`, { action, note })
}
