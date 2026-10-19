import api from './api'
import type {
  Summary, Performance, Signal, CoinConfig, CoinDetail,
  RadarItem, QueueItem, AdminUser, AdminStats, AuditEntry,
  Trade, TradesBalance, TradesProfit, CoinPerformance,
  DailyEntry, ModeStatus, UserSession, FactorAnalysis,
  BacktestResult, WsStatus, EngineHealth, RejectionStats,
  FilterAnalysis, MLValidation, MonthlyReport, RSSummary,
  DecisionTrace, IndianStatus, IndianSignal, IndianPerformance,
  IndianJourney,
} from '@/types'

export const authApi = {
  session: () =>
    api.get<{
      authenticated: boolean
      user?: { id: string; email: string; tier: string; is_admin: boolean }
    }>('/auth/session'),
  logout: () => api.get('/auth/logout'),
}

export const dashboardApi = {
  full:        () => api.get('/api/dashboard'),
  summary:     () => api.get<Summary>('/api/dashboard/summary'),
  performance: () => api.get<Performance>('/api/dashboard/performance'),
  signals:     () => api.get<{ radar: RadarItem[]; queue: QueueItem[]; timestamp: string }>('/api/dashboard/signals'),
  history:     (limit = 20) => api.get<Signal[]>(`/api/dashboard/history?limit=${limit}`),
  universe:    () => api.get<CoinConfig[]>('/api/dashboard/universe'),
  ticker:      () => api.get('/api/dashboard/ticker'),
  coinDetail:  (coin: string) => api.get<CoinDetail>(`/api/dashboard/coin/${coin}`),
}

export const signalsApi = {
  list: (params?: { limit?: number; grade?: string; coin?: string; outcome?: string }) =>
    api.get<Signal[]>('/api/signals', { params }),
  page: (params: { limit: number; offset: number; grade?: string; coin?: string; outcome?: string }) =>
    api.get<{ items: Signal[]; total: number; limit: number; offset: number }>('/api/signals/page', { params }),
  active:  () => api.get('/api/signals/active'),
  latest:  () => api.get('/api/signals/latest'),
  byId:    (id: number) => api.get(`/api/signal/${id}`),
  analyze: (coin: string) => api.get(`/api/analyze/${coin}`),
  scan:    () => api.get('/api/scan'),
}

export const coinsApi = {
  list:     () => api.get<CoinConfig[]>('/api/coins'),
  add:      (coin: string) => api.post('/api/coins/add', { coin }),
  toggle:   (coin: string, enabled: boolean) => api.post('/api/coins/toggle', { coin, enabled }),
  remove:   (coin: string) => api.delete(`/api/coins/${coin}`),
  validate: (coin: string) => api.get<{ valid: boolean; reason?: string; coin?: string }>(`/api/coins/validate/${coin}`),
  states:   () => api.get('/api/coins/states'),
}

export const tradesApi = {
  summary:     () => api.get('/api/trades/summary'),
  open:        () => api.get<Trade[]>('/api/trades/open'),
  profit:      () => api.get<TradesProfit>('/api/trades/profit'),
  balance:     () => api.get<TradesBalance>('/api/trades/balance'),
  history:     (options: number | { limit: number; offset: number; grade?: string; outcome?: string; coin?: string } = 20, offset = 0) => {
    const params = typeof options === 'number' ? { limit: options, offset } : options
    return api.get<{ trades: Trade[]; trades_count: number; limit: number; offset: number }>('/api/trades/history', { params })
  },
  daily:       (days = 7) => api.get<{ data: DailyEntry[] }>(`/api/trades/daily?days=${days}`),
  performance: () => api.get<CoinPerformance[]>('/api/trades/performance'),
  ping:        () => api.get('/api/trades/ping'),
  wsStatus:    () => api.get<WsStatus>('/api/trades/ws_status'),
  forceSell:   (trade_id: number, totp_code: string) => api.post('/api/trades/close', { trade_id, totp_code }),
}

export const adminApi = {
  overview:          () => api.get('/api/admin/overview'),
  stats:             () => api.get<AdminStats>('/api/admin/stats'),
  users:             (params?: { limit?: number; offset?: number; tier?: string; search?: string }) =>
    api.get<{ total: number; users: AdminUser[] }>('/api/admin/users', { params }),
  userById:          (id: number) => api.get(`/api/admin/users/${id}`),
  updateTier:        (id: number, tier: string) => api.post(`/api/admin/users/${id}/tier`, { tier }),
  deactivate:        (id: number) => api.post(`/api/admin/users/${id}/deactivate`),
  reactivate:        (id: number) => api.post(`/api/admin/users/${id}/reactivate`),
  sessions:          (params?: { user_id?: number; limit?: number }) => api.get('/api/admin/sessions', { params }),
  revokeSession:     (sessionId: string) => api.post(`/api/admin/sessions/${sessionId}/revoke`),
  revokeAllSessions: (userId: number) => api.post(`/api/admin/users/${userId}/sessions/revoke-all`),
  cleanupSessions:   () => api.post('/api/admin/sessions/cleanup'),
  audit:             (params?: { limit?: number; offset?: number; search?: string; actions?: string; success?: boolean }) =>
    api.get<{ total: number; logs: AuditEntry[] }>('/api/admin/audit', { params }),
  system:            () => api.get('/api/admin/system'),
  pricing:           () => api.get('/api/admin/pricing'),
}

export const systemApi = {
  health:       () => api.get('/api/health'),
  disk:         () => api.get('/api/system/disk'),
  dockerPurge:  (totp_code: string) => api.post('/api/system/docker-purge', { totp_code }),
  modeStatus:   () => api.get<ModeStatus>('/api/mode/status'),
  modeToggle:   (mode: string, totp_code: string) => api.post('/api/mode/toggle', { mode, totp_code }),
  syncOutcomes: () => api.post('/api/sync/outcomes'),
  auditLog:     (limit = 50) => api.get<AuditEntry[]>(`/api/audit/log?limit=${limit}`),
  wsStatus:     () => api.get<WsStatus>('/api/ws/status'),
}

export const performanceApi = {
  stats:           () => api.get('/api/stats'),
  backtest:        (coin: string) => api.get<BacktestResult>(`/api/backtest/${coin}`),
  backtestHistory: () => api.get('/api/backtest/history/all'),
  factorAnalysis:  () => api.get<FactorAnalysis>('/api/analysis/factors'),
}

export const mlApi = {
  status:                () => api.get('/api/health'),
  adaptationHistory:     (limit = 20) => api.get(`/api/admin/adaptations/history?limit=${limit}`),
  pendingRecommendations:() => api.get('/api/admin/adaptations/pending'),
  approveRecommendation: (id: number) => api.post(`/api/admin/adaptations/${id}/approve`),
  rejectRecommendation:  (id: number, reason = '') => api.post(`/api/admin/adaptations/${id}/reject`, { reason }),
  manualRollback:        (parameter: string) => api.post('/api/admin/adaptations/rollback', { parameter }),
  activeCheckpoints:     () => api.get('/api/admin/adaptations/checkpoints'),
  versionHistory:        (limit = 10) => api.get(`/api/admin/adaptations/versions?limit=${limit}`),
  performanceByVersion:  () => api.get('/api/admin/adaptations/performance/version'),
  performanceByRegime:   () => api.get('/api/admin/adaptations/performance/regime'),
  currentParameters:     () => api.get('/api/admin/adaptations/parameters'),
  validationReport:      () => api.get('/api/engine/ml/validation'),
}

export const engineApi = {
  health:              () => api.get<EngineHealth>('/api/engine/health'),
  rejections:          () => api.get<{ total: RejectionStats; daily: unknown[]; weekly: unknown; top: unknown[] }>('/api/engine/rejections'),
  rejectionsByCoin:    (coin: string) => api.get(`/api/engine/rejections/coin/${coin}`),
  traces:              (limit = 50) => api.get<{ traces: DecisionTrace[]; summary: Record<string, unknown>; count: number }>(`/api/engine/traces?limit=${limit}`),
  tracesByCoin:        (coin: string) => api.get<{ coin: string; latest: DecisionTrace | null; traces: DecisionTrace[]; count: number }>(`/api/engine/traces/${coin}`),
  relativeStrength:    () => api.get<RSSummary>('/api/engine/relative-strength'),
  relativeStrengthCoin:(coin: string) => api.get(`/api/engine/relative-strength/${coin}`),
  score:               (coin: string) => api.get(`/api/engine/score/${coin}`),
  filterAnalysis:      () => api.get<FilterAnalysis>('/api/engine/filter-analysis'),
  confidence:          (coin: string) => api.get(`/api/engine/confidence/${coin}`),
  mlValidation:        () => api.get<MLValidation>('/api/engine/ml/validation'),
  monthlyReport:       (year?: number, month?: number) => api.get<MonthlyReport>('/api/engine/monthly-report', { params: { year, month } }),
  monthlyHistory:      (months = 3) => api.get<MonthlyReport[]>(`/api/engine/monthly-report/history?months=${months}`),
  filterReport:        () => api.get<FilterAnalysis>('/api/engine/filter-report'),
  resetRejections:     (totp_code: string) => api.post('/api/engine/rejections/reset', { totp_code }),
}

export const marketApi = {
  fearGreed:   () => api.get('/api/fear-greed'),
  macroEvents: () => api.get('/api/macro-events'),
}

export const meApi = {
  get:               () => api.get('/api/me'),
  createApiKey:      (name: string) => api.post('/api/me/api-keys', { name }),
  deleteApiKey:      (id: number) => api.delete(`/api/me/api-keys/${id}`),
  sessions:          () => api.get<{ sessions: UserSession[] }>('/api/me/sessions'),
  revokeSession:     (sessionId: string) => api.post(`/api/me/sessions/${sessionId}/revoke`),
  revokeAllSessions: () => api.post('/api/me/sessions/revoke-all'),
}

export const pricingApi = {
  get: () => api.get('/api/pricing'),
}

export const indianApi = {
  status:      () => api.get<IndianStatus>('/api/indian/status'),
  orb:         () => api.get<Record<string, unknown>>('/api/indian/orb'),
  signals:     (limit = 50) => api.get<IndianSignal[]>(`/api/indian/signals?limit=${limit}`),
  performance: () => api.get<IndianPerformance>('/api/indian/performance'),
  journey:     (signalId: number) => api.get<IndianJourney>(`/api/indian/signals/${signalId}/journey`),
  refresh:     () => api.post<{ success: boolean; rate_limited?: boolean; reason?: string; results?: Record<string, unknown> }>('/api/indian/refresh'),
  setupOrb:    () => api.post('/api/indian/orb/setup'),
  scan:        () => api.post<{ success: boolean; signals: number }>('/api/indian/scan'),
}