import { defineStore } from 'pinia'
import { fetchMatches, confirmMatch, ignoreMatch } from '@/api/items'
import { fetchItem } from '@/api/items'

export const useMatchStore = defineStore('match', {
  state: () => ({
    itemId: null,
    item: null,
    candidates: [],
    loading: false,
    reviewing: null,
    /** 本地人工确认状态：{ [matchId]: 'confirmed' | 'ignored' } */
    decisions: {},
  }),

  getters: {
    pendingCount: (state) => state.candidates.filter((c) => !state.decisions[c.match_id]).length,
    confirmedCount: (state) =>
      state.candidates.filter((c) => state.decisions[c.match_id] === 'confirmed').length,
    ignoredCount: (state) =>
      state.candidates.filter((c) => state.decisions[c.match_id] === 'ignored').length,
  },

  actions: {
    async load(itemId) {
      this.loading = true
      this.itemId = itemId
      try {
        const [item, data] = await Promise.all([fetchItem(itemId), fetchMatches(itemId)])
        this.item = item
        this.candidates = (data.list || []).map((c) => ({
          ...c,
          decision: c.review || null,
        }))
        this.decisions = {}
        this.candidates.forEach((c) => {
          if (c.decision) this.decisions[c.match_id] = c.decision
        })
      } finally {
        this.loading = false
      }
    },

    async decide(matchId, action) {
      this.reviewing = matchId
      try {
        if (action === 'confirm') await confirmMatch(matchId)
        else await ignoreMatch(matchId)
        this.decisions = {
          ...this.decisions,
          [matchId]: action === 'confirm' ? 'confirmed' : 'ignored',
        }
        return true
      } finally {
        this.reviewing = null
      }
    },

    reset() {
      this.itemId = null
      this.item = null
      this.candidates = []
      this.decisions = {}
    },
  },
})
