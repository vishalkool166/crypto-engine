export type Tier         = 'free' | 'pro' | 'elite' | 'admin'
export type Grade        = 'A+' | 'A' | 'B' | 'C' | 'F'
export type Direction    = 'LONG' | 'SHORT' | 'WATCH' | 'NO TRADE'
export type TradeOutcome = 'win' | 'loss' | 'pending' | 'timeout' | 'cancelled' | 'expired'
export type HealthState  = 'HEALTHY' | 'WARNING' | 'INVALIDATED'
export type TradingMode  = 'live' | 'paper'
export type CoinState    = 'watching' | 'in_trade' | 'cooldown' | 'idle'
export type RSTier       = 'high' | 'medium' | 'low'

export interface TierFeatures {
  signal_delay_minutes:   number
  signals_per_day:        number
  show_levels:            boolean
  show_factors:           boolean
  show_thesis:            boolean
  show_ml:                boolean
  show_positions:         boolean
  show_performance:       boolean
  show_full_history:      boolean
  show_universe:          boolean
  show_system:            boolean
  api_key_access:         boolean
  backtest_access:        boolean
  coins_limit:            number
  show_score:             boolean
  show_session_breakdown: boolean
  show_phase_breakdown:   boolean
  show_mae_mfe:           boolean
  content_generator:      boolean
  ai_assistant:           boolean
}

export interface AuthUser {
  sub:         string
  email:       string
  tier:        Tier
  is_admin:    boolean
  session_id?: string
  type:        string
}

export interface User {
  id:         number
  email:      string
  name:       string | null
  avatar:     string | null
  provider:   string
  tier:       Tier
  is_admin:   boolean
  is_active:  boolean
  onboarded:  boolean
  created_at: string | null
  last_seen:  string | null
  last_login: string | null
}

export interface Signal {
  id:           number
  timestamp:    string | null
  coin:         string
  direction:    Direction
  grade:        Grade
  score:        number
  signal_type:  string
  entry:        number | null
  sl:           number | null
  tp1:          number | null
  risk_amt:     number | null
  regime:       string | null
  session:      string | null
  outcome:      TradeOutcome
  exit_price:   number | null
  pnl:          number | null
  market_score: number | null
  entry_score:  number | null
  btc_score:    number | null
  sweep_score:  number | null
}

export interface TraceStep {
  name:   string
  result: string
  score:  number
  reason: string
}

export interface DecisionTrace {
  coin:            string
  direction:       string
  timestamp:       number
  datetime:        string
  final_decision:  string
  final_score:     number
  final_grade:     string
  stopped_at:      string | null
  regime:          string
  session:         string
  score_breakdown: Record<string, unknown>
  steps:           TraceStep[]
}

export interface RSRanking {
  coin:           string
  rank:           number
  tier:           RSTier
  total_score:    number
  rs:             number
  rs_score:       number
  vol_ratio:      number
  vol_score:      number
  adx:            number
  adx_score:      number
  momentum:       number
  momentum_score: number
  change_24h:     number
  btc_change:     number
  scored_at:      number
}

export interface RSSummary {
  total:       number
  high_tier:   number
  medium_tier: number
  low_tier:    number
  top_5:       RSRanking[]
  bottom_5:    RSRanking[]
  ranked_at:   number
}

export interface RejectionReason {
  count: number
  pct:   number
}

export interface RejectionStats {
  total_scans:      number
  total_signals:    number
  total_rejections: number
  signal_rate:      number
  by_reason:        Record<string, RejectionReason>
}

export interface EngineHealth {
  coins_scanned:   number
  signals_today:   number
  total_scans:     number
  avg_scan_ms:     number
  avg_score:       number
  dominant_regime: string
  btc_cls:         string
  btc_adx:         number
  top_rejections:  Array<{ reason: string; count: number; pct: number }>
  signal_rate:     number
  updated_at:      number
}

export interface FilterBottleneck {
  filter:   string
  count:    number
  pct:      number
  severity: string
  action:   string
}

export interface FilterAnalysis {
  total_scans:      number
  total_signals:    number
  signal_rate:      number
  filter_analysis:  FilterBottleneck[]
  trace_summary:    Record<string, { count: number; pct: number }>
  daily_trend:      unknown[]
  recommendations:  Array<{
    priority: string
    type:     string
    filter?:  string
    pct?:     number
    message:  string
  }>
}

export interface MLValidation {
  trained_at:        string | null
  samples:           number
  win_rate:          number
  cv_auc:            number | null
  cv_std:            number | null
  train_auc:         number | null
  precision:         number | null
  recall:            number | null
  f1:                number | null
  confusion_matrix:  {
    true_positive:  number
    true_negative:  number
    false_positive: number
    false_negative: number
  } | null
  calibrated:        boolean
  top_features:      Array<{ feature: string; importance: number }>
  shap_top_features: Array<{ feature: string; shap_mean: number }>
  threshold:         number
  classification:    Record<string, number>
}

export interface MonthlyReport {
  period:          string
  period_label:    string
  trades:          number
  wins:            number
  losses:          number
  win_rate:        number
  total_pnl:       number
  total_pnl_pos:   boolean
  gross_profit:    number
  gross_loss:      number
  profit_factor:   number
  avg_win:         number
  avg_loss:        number
  expectancy:      number
  avg_hold_hours:  number
  max_drawdown:    number
  total_fees:      number
  total_funding:   number
  best_trade:      number
  worst_trade:     number
  best_coin:       string
  worst_coin:      string
  tp1_hit_rate:    number
  best_regime:     string
  worst_regime:    string
  best_session:    string
  top_rejection:   string
  by_regime:       Record<string, unknown>
  by_session:      Record<string, unknown>
  by_grade:        Record<string, unknown>
  by_day:          Record<string, unknown>
  generated_at:    string
  error?:          string
}

export interface RadarItem {
  coin:      string
  grade:     Grade | '--'
  direction: Direction | '--'
  score:     number
  state:     CoinState
  price:     number
  change:    number
  change_pos:boolean
  funding:   number
  tradeable: boolean
  regime:    string
  session:   string
  timestamp: number | null
  reason?:   string
  adx?:      number
  rsi?:      number
}

export interface QueueItem {
  coin:      string
  grade:     Grade
  direction: Direction
  score:     number
  state:     CoinState
  entry:     number | null
  sl:        number | null
  tp1:       number | null
  sl_pct:    number | null
  risk_amt:  number | null
  stake:     number | null
  leverage:  number | null
  regime:    string
  session:   string
}

export interface CoinDetail {
  coin:      string
  grade:     Grade | '--'
  score:     number
  direction: Direction | '--'
  regime:    string
  session:   string
  state?:    CoinState
  market: {
    price:      number
    change:     number
    change_pos: boolean
    funding:    number
  }
  signal: {
    entry:    number | null
    sl:       number | null
    tp1:      number | null
    sl_pct:   number | null
    risk_amt: number | null
    leverage: number | null
    stake:    number | null
  }
}

export interface TradeHealth {
  state:          HealthState
  failures:       string[]
  warnings:       string[]
  checks:         string[]
  move_pct:       number
  adverse_atr:    number
  is_healthy:     boolean
  is_warning:     boolean
  is_invalidated: boolean
  checked_at:     string
}

export interface Trade {
  trade_id:           number
  coin:               string
  pair:               string
  direction:          string
  grade:              string
  is_short:           boolean
  is_open:            boolean
  entry_price:        number
  actual_fill_entry:  number | null
  current_price:      number
  exit_price:         number | null
  actual_fill_exit:   number | null
  sl_price:           number | null
  tp1_price:          number | null
  sl_signal:          number | null
  tp1:                number | null
  position_size:      number
  margin_used:        number
  leverage:           number
  profit_abs:         number
  profit_ratio:       number
  net_pnl_live:       number
  pnl:                number | null
  realized_pnl:       number | null
  entry_commission:   number | null
  exit_commission:    number | null
  total_commission:   number | null
  entry_role:         string | null
  exit_role:          string | null
  funding_fees_paid:  number | null
  slippage_entry_pct: number | null
  slippage_exit_pct:  number | null
  liquidation:        number
  duration:           string | null
  duration_hours:     number | null
  opened_at:          string | null
  closed_at:          string | null
  outcome:            TradeOutcome
  close_reason:       string | null
  tp1_hit:            boolean
  health:             TradeHealth | null
  regime_at_entry:    string | null
  session_at_entry:   string | null
  score_at_entry:     number | null
  system_version:     string | null
  mae:                number | null
  mfe:                number | null
  thesis?:            Record<string, unknown> | null
}

export interface TradesBalance {
  total:      number
  free:       number
  used:       number
  unrealized: number
  currencies: Array<{
    currency:   string
    free:       number
    used:       number
    total:      number
    unrealized: number
  }>
}

export interface TradesProfit {
  profit_all_coin:         number
  profit_all_percent:      number
  profit_closed_coin:      number
  winrate:                 number
  trade_count:             number
  wins:                    number
  losses:                  number
  total_commission:        number
  total_funding_fees:      number
  best_pair:               string
  best_pair_profit_ratio:  number
  worst_pair:              string
  worst_pair_profit_ratio: number
}

export interface DailyEntry {
  date:         string
  profit_abs:   number
  profit_ratio: number
  trade_count:  number
  wins:         number
  losses:       number
  commission:   number
  funding:      number
}

export interface CoinPerformance {
  pair:         string
  coin:         string
  wins:         number
  losses:       number
  profit_abs:   number
  profit_ratio: number
  win_rate:     number
  commission:   number
  funding:      number
}

export interface Summary {
  today_pnl:        number | null
  today_pnl_pos:    boolean
  today_trades:     number | null
  win_rate:         number | null
  coins_count:      number
  watching_count:   number
  in_trade_count:   number
  cooldown_count:   number
  tradeable_count:  number | null
  mode:             TradingMode
  grades:           string[]
  next_scan_epoch:  number
  total_signals:    number
  closed_signals:   number
  pending_signals:  number
  wins:             number | null
  losses:           number | null
  total_pnl:        number | null
  timestamp:        string
}

export interface Performance {
  win_rate:        number
  total_pnl:       number
  total_pnl_pos:   boolean
  wins:            number
  losses:          number
  closed:          number
  profit_factor:   number
  gross_profit:    number
  gross_loss:      number
  best_trade:      number
  best_trade_coin: string
  max_drawdown:    number
  peak_equity:     number
  equity_curve:    Array<{ date: string; pnl: number; equity: number }>
  aplus:           GradeStats
  a:               GradeStats
  b:               GradeStats
}

export interface GradeStats {
  win_rate: number
  wins:     number
  total:    number
  pnl:      number
}

export interface CoinConfig {
  coin:       string
  enabled:    boolean
  tier:       number
  source:     string
  volume_24h: number | null
  added_at:   string | null
  grade:      string
  score:      number
  direction:  string
  has_signal: boolean
  price:      number
  change:     number
  funding:    number
  state:      CoinState
}

export interface AdminUser extends User {
  subscription?: {
    tier:                 Tier
    status:               string
    current_period_end:   string | null
    cancel_at_period_end: boolean
  } | null
  sessions?: UserSession[]
}

export interface UserSession {
  id:          number
  session_id:  string
  device:      string | null
  browser:     string | null
  ip:          string | null
  created_at:  string | null
  last_active: string | null
  expires_at:  string | null
}

export interface AuditEntry {
  id:        number
  timestamp: string | null
  action:    string
  source:    string
  detail:    string | null
  ip:        string | null
  success:   boolean
}

export interface SystemStats {
  ram_used_mb:   number
  ram_total_mb:  number
  ram_pct:       number
  ram_available: number
  cpu_pct:       number
  disk_used_gb:  number
  disk_total_gb: number
  disk_pct:      number
  uptime_secs:   number
  uptime_str:    string
  containers:    Container[]
}

export interface Container {
  name:    string
  status:  string
  mem_mb:  number
  mem_pct: number
  cpu_pct: number
}

export interface AdminStats {
  users: {
    total:     number
    active:    number
    new_today: number
    by_tier:   Record<Tier, number>
  }
  signups_week:    number
  signups_month:   number
  active_subs:     number
  mrr_estimate:    number
  pro_count:       number
  elite_count:     number
  active_sessions: number
  timestamp:       string
}

export interface FactorAnalysis {
  total:        number
  wins:         number
  losses:       number
  overall_wr:   number
  reliable:     boolean
  reliability:  string
  table:        FactorRow[]
  grade_stats:  GradeStatRow[]
  top_factors:  FactorRow[]
  weak_factors: FactorRow[]
}

export interface FactorRow {
  factor:           string
  present_total:    number
  absent_total:     number
  win_rate_present: number | null
  win_rate_absent:  number | null
  edge:             number | null
  observation:      string
}

export interface GradeStatRow {
  grade:    string
  total:    number
  wins:     number
  losses:   number
  win_rate: number
}

export interface ApiKey {
  id:         number
  prefix:     string
  name:       string
  last_used:  string | null
  created_at: string | null
  expires_at: string | null
}

export interface ModeStatus {
  mode:         TradingMode
  paper:        boolean
  grades:       string[]
  b_grade_live: boolean
}

export interface WsStatus {
  mark_price_connected: boolean
  user_data_connected:  boolean
  kline_ws_connected:   boolean
  ticker_ws_connected:  boolean
  prices_cached:        number
  mode:                 TradingMode
}

export interface TickerItem {
  coin:   string
  price:  number
  change: number
}

export interface WsPayload {
  type:            string
  tier?:           string
  summary?:        Summary
  signals?: {
    radar:     RadarItem[]
    queue:     QueueItem[]
    timestamp: string
  }
  history?:        Signal[]
  universe?:       CoinConfig[]
  performance?:    Performance
  ticker?:         TickerItem[]
  open_trades?:    Trade[]
  mark_prices?:    Record<string, number>
  engine_health?:  EngineHealth
  top_rejections?: Array<{ reason: string; count: number; pct: number }>
  timestamp?:      string
}

export interface BacktestResult {
  coin:            string
  period_start:    string
  period_end:      string
  capital:         number
  final_equity:    number
  total_return:    number
  total_signals:   number
  total_trades:    number
  wins:            number
  losses:          number
  win_rate:        number
  total_pnl:       number
  best_trade:      number
  worst_trade:     number
  avg_trade:       number
  max_drawdown:    number
  profit_factor:   number
  expectancy:      number
  phase_breakdown: {
    tp1_hit_count:  number
    tp2_hit_count:  number
    be_stop_count:  number
    tp1_hit_rate:   number
    tp2_hit_rate:   number
    be_stop_rate:   number
  }
  by_grade: Record<string, {
    trades:   number
    wins:     number
    win_rate: number
    pnl:      number
  }>
  trades?: unknown[]
  error?:  string
}

export interface IndianInstrumentConfig {
  direction:      string
  min_orb:        number
  max_orb:        number
  min_pre_range:  number
  min_prev_range: number
  sl_mult:        number
  tp_mult:        number
  entry_start_h:  number
  entry_end_h:    number
  skip_weeks:     number[]
  lot_size:       number
  time_exit_h:    number
  time_exit_m:    number
}

export interface IndianOrbLevel {
  high: number
  low:  number
  size: number
  date: string
}

export interface IndianOpenSignal {
  id:            number
  instrument:    string
  direction:     string
  entry:         number
  sl:            number
  tp1:           number
  current_price: number | null
  live_pnl_pts:  number | null
  live_rupees:   number | null
  progress_pct:  number | null
  orb_high:      number
  orb_low:       number
  orb_size:      number
  duration:      string | null
  timestamp:     string | null
  outcome:       string
}

export interface IndianSetupSignal {
  instrument: string
  direction:  string
  entry:      number
  sl:         number
  tp1:        number
  tp2:        number
  orb_high:   number
  orb_low:    number
  orb_size:   number
  sl_pts:     number
  tp_pts:     number
  rr1:        number
  pre_range:  number
  prev_range: number
}

export interface IndianSignal {
  id:          number
  timestamp:   string | null
  instrument:  string
  direction:   string
  grade:       string | null
  entry:       number
  sl:          number
  tp1:         number
  tp2:         number | null
  sl_pct:      number | null
  outcome:     string
  exit_price:  number | null
  pnl_pts:     number | null
  orb_high:    number
  orb_low:     number
  orb_size:    number
  notes:       string | null
  day_of_week: number | null
}

export interface IndianStatus {
  market_open:        boolean
  orb_ready:          boolean
  time_ist:           string
  date:               string
  instruments:        Record<string, unknown>
  orb_levels:         Record<string, IndianOrbLevel>
  day_ranges:         Record<string, number>
  ltps:               Record<string, number>
  pre_ranges:         Record<string, number>
  prev_ranges:        Record<string, number>
  instruments_config: Record<string, IndianInstrumentConfig>
  signals_today:      number
  signals:            IndianSetupSignal[]
  open_signals:       IndianOpenSignal[]
  rate_limited:       boolean
  data_age_secs:      number
}

export interface IndianPerformanceByDirection {
  total:    number
  wins:     number
  losses:   number
  win_rate: number
  pnl_pts:  number
}

export interface IndianPerformance {
  total:           number
  wins:            number
  losses:          number
  timeouts:        number
  win_rate:        number
  profitable_rate: number
  total_pts:       number
  avg_win_pts:     number
  avg_loss_pts:    number
  profit_factor:   number
  by_direction:    Record<string, IndianPerformanceByDirection>
  by_day:          Record<string, { total: number; wins: number; win_rate: number }>
}

export interface IndianJourney {
  signal_id: number
  journey:   Array<{
    timestamp:   string | null
    price:       number
    pnl_pts:     number | null
    pnl_pct:     number | null
    is_entry:    boolean
    is_exit:     boolean
    entry_price: number
    sl_price:    number | null
    tp_price:    number | null
  }>
}
