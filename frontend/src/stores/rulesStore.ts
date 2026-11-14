import { defineStore } from 'pinia'
import { activateRule, createRule, fetchRules, previewRule } from '../api/rules'
import type { RuleItem, RulePreviewRow } from '../types/domain'

interface RulesState {
  items: RuleItem[]
  active: RuleItem | null
  tokens: string[]
  preview: { valid: boolean; message: string; missing: string[]; rows: RulePreviewRow[] } | null
  loading: boolean
  saving: boolean
  error: string
}

export const useRulesStore = defineStore('rules', {
  state: (): RulesState => ({
    items: [],
    active: null,
    tokens: [],
    preview: null,
    loading: false,
    saving: false,
    error: '',
  }),
  actions: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const result = await fetchRules()
        this.items = result.items
        this.active = result.active
        this.tokens = result.tokens
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '规则加载失败'
      } finally {
        this.loading = false
      }
    },
    async previewTemplate(template: string) {
      try {
        this.preview = await previewRule(template)
      } catch (error) {
        this.preview = {
          valid: false,
          message: (error as { message?: string }).message ?? '预览失败',
          missing: [],
          rows: [],
        }
      }
    },
    async save(template: string, note: string) {
      this.saving = true
      this.error = ''
      try {
        await createRule({ template, note })
        await this.load()
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '规则保存失败'
        throw error
      } finally {
        this.saving = false
      }
    },
    async activate(ruleId: string) {
      await activateRule(ruleId)
      await this.load()
    },
  },
})
