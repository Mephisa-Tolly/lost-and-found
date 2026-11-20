/**
 * 业务字典（分类 / 地点 / 状态）
 * 与后端 schema.sql 及 PRD V1.1 的字段口径保持一致。
 * 这是真实的业务常量，不是演示数据。
 */

export const CATEGORIES = [
  '校园卡/学生证',
  '雨伞',
  '水杯',
  '耳机',
  '充电宝',
  '钥匙',
  '银行卡',
  '书本/文具',
  '其他',
]

// 敏感物品：发布时不展示完整描述，需走人工核验
export const SENSITIVE_CATEGORIES = ['校园卡/学生证', '银行卡', '钥匙']

export const LOCATIONS = [
  '图书馆一楼',
  '图书馆二楼',
  '图书馆自习区',
  '教学楼A201',
  '教学楼B103',
  '一食堂',
  '二食堂',
  '操场',
  '快递站',
  '男生宿舍3号楼',
]

export const STATUS_OPTIONS = ['待匹配', '已匹配', '认领中', '已确认', '已关闭', '无人认领']

export const CATEGORY_META = {
  '校园卡/学生证': { color: '#6366f1', bg: '#eef2ff', icon: 'Postcard' },
  雨伞: { color: '#0ea5e9', bg: '#e0f2fe', icon: 'Umbrella' },
  水杯: { color: '#14b8a6', bg: '#ccfbf1', icon: 'Coffee' },
  耳机: { color: '#8b5cf6', bg: '#f3e8ff', icon: 'Headset' },
  充电宝: { color: '#f59e0b', bg: '#fef3c7', icon: 'Lightning' },
  钥匙: { color: '#ef4444', bg: '#fee2e2', icon: 'Key' },
  银行卡: { color: '#ec4899', bg: '#fce7f3', icon: 'CreditCard' },
  '书本/文具': { color: '#10b981', bg: '#d1fae5', icon: 'Notebook' },
  其他: { color: '#64748b', bg: '#f1f5f9', icon: 'Box' },
}
