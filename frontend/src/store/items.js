import { defineStore } from 'pinia'
import { fetchAllItems, fetchItem, createItem, fetchStats } from '@/api/items'

export const useItemStore = defineStore('items', {
  state: () => ({
    list: [],
    current: null,
    stats: { total: 0, lost: 0, found: 0, matched: 0 },
    loading: false,
    submitting: false,
    filters: { type: 'all', category: 'all', status: 'all', keyword: '', sort: 'time' },
  }),

  getters: {
    filtered(state) {
      const list = [...state.list]
      if (state.filters.sort === 'time') {
        list.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
      }
      return list
    },
  },

  actions: {
    async loadList() {
      this.loading = true
      try {
        // 自动翻页拉全量，避免数据超过 100 条后列表缺尾
        const data = await fetchAllItems({
          type: this.filters.type,
          category: this.filters.category,
          status: this.filters.status,
          keyword: this.filters.keyword,
        })
        this.list = data.list || []
      } finally {
        this.loading = false
      }
    },

    async loadItem(id) {
      this.loading = true
      try {
        this.current = await fetchItem(id)
        return this.current
      } finally {
        this.loading = false
      }
    },

    async loadStats() {
      this.stats = await fetchStats()
    },

    async create(payload) {
      this.submitting = true
      try {
        return await createItem(payload)
      } finally {
        this.submitting = false
      }
    },

    resetFilters() {
      this.filters = { type: 'all', category: 'all', status: 'all', keyword: '', sort: 'time' }
    },
  },
})
