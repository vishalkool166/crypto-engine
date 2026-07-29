import logging
import json
from datetime import datetime, timezone, timedelta, date
from sentence_transformers import SentenceTransformer
from rag.vectorstore import (
    get_trades_collection,
    get_signals_collection,
    get_daily_collection,
    get_coins_collection,
    get_docs_collection,
)

log = logging.getLogger(__name__)

_embedder = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is not None:
        return _embedder
    log.info("Loading sentence-transformers model...")
    _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    log.info("Embedding model loaded")
    return _embedder


def _embed(texts: list[str]) -> list[list[float]]:
    embedder = get_embedder()
    return embedder.encode(texts, show_progress_bar=False).tolist()


def _safe_float(val) -> float:
    try:
        return round(float(val or 0), 4)
    except Exception:
        return 0.0


def _safe_str(val) -> str:
    if val is None:
        return "--"
    return str(val)


def index_trades(full_reindex: bool = False) -> int:
    from database import SessionLocal, Trade as TradeModel

    collection = get_trades_collection()

    with SessionLocal() as db:
        query = db.query(TradeModel).filter(
            TradeModel.outcome.in_(["win", "loss"])
        )
        trades = query.all()

    if not trades:
        log.info("No closed trades to index")
        return 0

    existing_ids = set()
    if not full_reindex:
        try:
            results      = collection.get()
            existing_ids = set(results["ids"])
        except Exception:
            pass

    texts    = []
    ids      = []
    metadatas= []

    for t in trades:
        doc_id = f"trade_{t.id}"
        if doc_id in existing_ids:
            continue

        opened_str = "--"
        closed_str = "--"
        if t.opened_at:
            opened = t.opened_at
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            opened_str = opened.strftime("%Y-%m-%d %H:%M UTC")
        if t.closed_at:
            closed = t.closed_at
            if closed.tzinfo is None:
                closed = closed.replace(tzinfo=timezone.utc)
            closed_str = closed.strftime("%Y-%m-%d %H:%M UTC")

        pnl      = _safe_float(t.binance_net_pnl or t.net_pnl or t.pnl)
        pnl_str  = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"
        duration = _safe_float(t.duration_hours)

        text = (
            f"Trade #{t.id} | {_safe_str(t.coin)} | {_safe_str(t.direction)} | Grade {_safe_str(t.grade)}\n"
            f"Opened: {opened_str} | Closed: {closed_str}\n"
            f"Session: {_safe_str(t.session_at_entry)} | Regime: {_safe_str(t.regime_at_entry)}\n"
            f"Entry: {_safe_float(t.entry_price)} | SL: {_safe_float(t.sl_price)} | TP: {_safe_float(t.tp1_price)}\n"
            f"Outcome: {_safe_str(t.outcome)} | PnL: {pnl_str}\n"
            f"Score at entry: {_safe_float(t.score_at_entry)}\n"
            f"Duration: {duration:.1f} hours\n"
            f"Close reason: {_safe_str(t.close_reason)}\n"
            f"TP1 hit: {bool(t.tp1_hit)}\n"
            f"Win rate at entry: {_safe_float(t.win_rate_at_entry)}\n"
            f"Drawdown at entry: {_safe_float(t.drawdown_at_entry)}\n"
            f"Thesis strength at close: {_safe_float(t.thesis_strength_at_close)}\n"
            f"Total commission: {_safe_float(t.total_commission)}\n"
            f"Funding fees: {_safe_float(t.funding_fees_paid)}"
        )

        metadata = {
            "trade_id":  t.id,
            "coin":      _safe_str(t.coin),
            "direction": _safe_str(t.direction),
            "grade":     _safe_str(t.grade),
            "outcome":   _safe_str(t.outcome),
            "session":   _safe_str(t.session_at_entry),
            "regime":    _safe_str(t.regime_at_entry),
            "pnl":       pnl,
            "type":      "trade",
        }

        texts.append(text)
        ids.append(doc_id)
        metadatas.append(metadata)

    if not texts:
        log.info("No new trades to index")
        return 0

    batch_size = 50
    indexed    = 0
    for i in range(0, len(texts), batch_size):
        batch_texts     = texts[i:i + batch_size]
        batch_ids       = ids[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]
        embeddings      = _embed(batch_texts)
        collection.add(
            documents  = batch_texts,
            embeddings = embeddings,
            ids        = batch_ids,
            metadatas  = batch_metadatas,
        )
        indexed += len(batch_texts)

    log.info("Indexed %s trades", indexed)
    return indexed


def index_signals(full_reindex: bool = False) -> int:
    from database import SessionLocal, Signal as SignalModel

    collection = get_signals_collection()

    with SessionLocal() as db:
        signals = db.query(SignalModel).filter(
            SignalModel.outcome.in_(["win", "loss"])
        ).all()

    if not signals:
        log.info("No closed signals to index")
        return 0

    existing_ids = set()
    if not full_reindex:
        try:
            results      = collection.get()
            existing_ids = set(results["ids"])
        except Exception:
            pass

    texts     = []
    ids       = []
    metadatas = []

    for s in signals:
        doc_id = f"signal_{s.id}"
        if doc_id in existing_ids:
            continue

        ts_str = "--"
        if s.timestamp:
            ts = s.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")

        factor_str = ""
        if s.factor_scores:
            try:
                factors    = json.loads(s.factor_scores)
                top        = sorted(factors.items(), key=lambda x: x[1], reverse=True)[:5]
                factor_str = " | ".join(f"{k}:{v}" for k, v in top)
            except Exception:
                pass

        pnl     = _safe_float(s.pnl)
        pnl_str = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"

        text = (
            f"Signal #{s.id} | {_safe_str(s.coin)} | {_safe_str(s.direction)} | Grade {_safe_str(s.grade)}\n"
            f"Timestamp: {ts_str}\n"
            f"Score: {_safe_float(s.score)}/100\n"
            f"Session: {_safe_str(s.session)} | Regime: {_safe_str(s.regime)}\n"
            f"Entry: {_safe_float(s.entry)} | SL: {_safe_float(s.sl)} | TP: {_safe_float(s.tp1)}\n"
            f"SL%: {_safe_float(s.sl_pct)} | Risk amount: ${_safe_float(s.risk_amt)}\n"
            f"Sweep score: {_safe_float(s.sweep_score)} | Displacement: {_safe_float(s.disp_score)}\n"
            f"BTC score: {_safe_float(s.btc_score)} | Market score: {_safe_float(s.market_score)}\n"
            f"Top factors: {factor_str}\n"
            f"Outcome: {_safe_str(s.outcome)} | PnL: {pnl_str}\n"
            f"Funding: {_safe_float(s.funding)} | OI signal: {_safe_str(s.oi_signal)}"
        )

        metadata = {
            "signal_id": s.id,
            "coin":      _safe_str(s.coin),
            "direction": _safe_str(s.direction),
            "grade":     _safe_str(s.grade),
            "outcome":   _safe_str(s.outcome),
            "session":   _safe_str(s.session),
            "regime":    _safe_str(s.regime),
            "score":     _safe_float(s.score),
            "pnl":       pnl,
            "type":      "signal",
        }

        texts.append(text)
        ids.append(doc_id)
        metadatas.append(metadata)

    if not texts:
        log.info("No new signals to index")
        return 0

    batch_size = 50
    indexed    = 0
    for i in range(0, len(texts), batch_size):
        batch_texts     = texts[i:i + batch_size]
        batch_ids       = ids[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]
        embeddings      = _embed(batch_texts)
        collection.add(
            documents  = batch_texts,
            embeddings = embeddings,
            ids        = batch_ids,
            metadatas  = batch_metadatas,
        )
        indexed += len(batch_texts)

    log.info("Indexed %s signals", indexed)
    return indexed


def index_daily_summaries(full_reindex: bool = False) -> int:
    from database import SessionLocal, Trade as TradeModel

    collection = get_daily_collection()

    with SessionLocal() as db:
        trades = db.query(TradeModel).filter(
            TradeModel.outcome.in_(["win", "loss"]),
            TradeModel.opened_at.isnot(None),
        ).all()

    if not trades:
        return 0

    by_day: dict = {}
    for t in trades:
        opened = t.opened_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        day_key = opened.strftime("%Y-%m-%d")
        if day_key not in by_day:
            by_day[day_key] = []
        by_day[day_key].append(t)

    existing_ids = set()
    if not full_reindex:
        try:
            results      = collection.get()
            existing_ids = set(results["ids"])
        except Exception:
            pass

    texts     = []
    ids       = []
    metadatas = []

    for day_key, day_trades in by_day.items():
        doc_id = f"daily_{day_key}"
        if doc_id in existing_ids:
            continue

        wins      = [t for t in day_trades if t.outcome == "win"]
        losses    = [t for t in day_trades if t.outcome == "loss"]
        total_pnl = sum(_safe_float(t.binance_net_pnl or t.net_pnl or t.pnl) for t in day_trades)
        pnl_str   = f"+${total_pnl:.4f}" if total_pnl >= 0 else f"-${abs(total_pnl):.4f}"
        win_rate  = round(len(wins) / len(day_trades) * 100, 1) if day_trades else 0

        try:
            day_dt   = datetime.strptime(day_key, "%Y-%m-%d")
            day_name = day_dt.strftime("%A")
        except Exception:
            day_name = "--"

        sessions = list(set(t.session_at_entry for t in day_trades if t.session_at_entry))
        regimes  = list(set(t.regime_at_entry  for t in day_trades if t.regime_at_entry))
        coins    = list(set(t.coin             for t in day_trades if t.coin))

        best_trade  = max(day_trades, key=lambda t: _safe_float(t.binance_net_pnl or t.net_pnl or t.pnl))
        worst_trade = min(day_trades, key=lambda t: _safe_float(t.binance_net_pnl or t.net_pnl or t.pnl))

        best_pnl  = _safe_float(best_trade.binance_net_pnl  or best_trade.net_pnl  or best_trade.pnl)
        worst_pnl = _safe_float(worst_trade.binance_net_pnl or worst_trade.net_pnl or worst_trade.pnl)

        text = (
            f"Daily Summary | {day_key} | {day_name}\n"
            f"Total trades: {len(day_trades)} | Wins: {len(wins)} | Losses: {len(losses)}\n"
            f"Win rate: {win_rate}% | Total PnL: {pnl_str}\n"
            f"Sessions: {', '.join(sessions)}\n"
            f"Regimes: {', '.join(regimes)}\n"
            f"Coins traded: {', '.join(coins)}\n"
            f"Best trade: {best_trade.coin} {best_trade.direction} +${best_pnl:.4f}\n"
            f"Worst trade: {worst_trade.coin} {worst_trade.direction} ${worst_pnl:.4f}"
        )

        metadata = {
            "date":       day_key,
            "day_name":   day_name,
            "trades":     len(day_trades),
            "wins":       len(wins),
            "losses":     len(losses),
            "win_rate":   win_rate,
            "total_pnl":  total_pnl,
            "type":       "daily_summary",
        }

        texts.append(text)
        ids.append(doc_id)
        metadatas.append(metadata)

    if not texts:
        log.info("No new daily summaries to index")
        return 0

    batch_size = 50
    indexed    = 0
    for i in range(0, len(texts), batch_size):
        batch_texts     = texts[i:i + batch_size]
        batch_ids       = ids[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]
        embeddings      = _embed(batch_texts)
        collection.add(
            documents  = batch_texts,
            embeddings = embeddings,
            ids        = batch_ids,
            metadatas  = batch_metadatas,
        )
        indexed += len(batch_texts)

    log.info("Indexed %s daily summaries", indexed)
    return indexed


def index_coin_performance(full_reindex: bool = False) -> int:
    from database import SessionLocal, Trade as TradeModel

    collection = get_coins_collection()

    with SessionLocal() as db:
        trades = db.query(TradeModel).filter(
            TradeModel.outcome.in_(["win", "loss"])
        ).all()

    if not trades:
        return 0

    by_coin: dict = {}
    for t in trades:
        coin = t.coin or "UNKNOWN"
        if coin not in by_coin:
            by_coin[coin] = []
        by_coin[coin].append(t)

    existing_ids = set()
    if not full_reindex:
        try:
            results      = collection.get()
            existing_ids = set(results["ids"])
        except Exception:
            pass

    texts     = []
    ids       = []
    metadatas = []

    for coin, coin_trades in by_coin.items():
        doc_id = f"coin_{coin}"

        wins      = [t for t in coin_trades if t.outcome == "win"]
        losses    = [t for t in coin_trades if t.outcome == "loss"]
        total_pnl = sum(_safe_float(t.binance_net_pnl or t.net_pnl or t.pnl) for t in coin_trades)
        win_rate  = round(len(wins) / len(coin_trades) * 100, 1) if coin_trades else 0
        pnl_str   = f"+${total_pnl:.4f}" if total_pnl >= 0 else f"-${abs(total_pnl):.4f}"

        by_session: dict = {}
        for t in coin_trades:
            s = t.session_at_entry or "Unknown"
            if s not in by_session:
                by_session[s] = {"wins": 0, "total": 0}
            by_session[s]["total"] += 1
            if t.outcome == "win":
                by_session[s]["wins"] += 1

        session_lines = []
        for s, data in by_session.items():
            swr = round(data["wins"] / data["total"] * 100, 1) if data["total"] > 0 else 0
            session_lines.append(f"{s}: {swr}% WR ({data['total']} trades)")

        by_regime: dict = {}
        for t in coin_trades:
            r = t.regime_at_entry or "Unknown"
            if r not in by_regime:
                by_regime[r] = {"wins": 0, "total": 0}
            by_regime[r]["total"] += 1
            if t.outcome == "win":
                by_regime[r]["wins"] += 1

        regime_lines = []
        for r, data in by_regime.items():
            rwr = round(data["wins"] / data["total"] * 100, 1) if data["total"] > 0 else 0
            regime_lines.append(f"{r}: {rwr}% WR ({data['total']} trades)")

        best_trade  = max(coin_trades, key=lambda t: _safe_float(t.binance_net_pnl or t.net_pnl or t.pnl))
        worst_trade = min(coin_trades, key=lambda t: _safe_float(t.binance_net_pnl or t.net_pnl or t.pnl))

        text = (
            f"Coin Performance | {coin}\n"
            f"Total trades: {len(coin_trades)} | Wins: {len(wins)} | Losses: {len(losses)}\n"
            f"Win rate: {win_rate}% | Total PnL: {pnl_str}\n"
            f"Best trade: {best_trade.direction} Grade {best_trade.grade} "
            f"+${_safe_float(best_trade.binance_net_pnl or best_trade.net_pnl or best_trade.pnl):.4f}\n"
            f"Worst trade: {worst_trade.direction} Grade {worst_trade.grade} "
            f"${_safe_float(worst_trade.binance_net_pnl or worst_trade.net_pnl or worst_trade.pnl):.4f}\n"
            f"Performance by session:\n" + "\n".join(session_lines) + "\n"
            f"Performance by regime:\n" + "\n".join(regime_lines)
        )

        metadata = {
            "coin":      coin,
            "trades":    len(coin_trades),
            "wins":      len(wins),
            "losses":    len(losses),
            "win_rate":  win_rate,
            "total_pnl": total_pnl,
            "type":      "coin_performance",
        }

        if doc_id in existing_ids:
            try:
                collection.update(
                    documents  = [text],
                    embeddings = _embed([text]),
                    ids        = [doc_id],
                    metadatas  = [metadata],
                )
            except Exception as e:
                log.warning("Update coin %s: %s", coin, e)
        else:
            texts.append(text)
            ids.append(doc_id)
            metadatas.append(metadata)

    if texts:
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch_texts     = texts[i:i + batch_size]
            batch_ids       = ids[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            embeddings      = _embed(batch_texts)
            collection.add(
                documents  = batch_texts,
                embeddings = embeddings,
                ids        = batch_ids,
                metadatas  = batch_metadatas,
            )

    log.info("Indexed %s coin performance chunks", len(by_coin))
    return len(by_coin)


def index_documentation(full_reindex: bool = False) -> int:
    collection   = get_docs_collection()
    existing_ids = set()

    if not full_reindex:
        try:
            results      = collection.get()
            existing_ids = set(results["ids"])
        except Exception:
            pass

    doc_files = [
        ("README.md",  "readme"),
        ("WORKING.md", "working"),
    ]

    texts     = []
    ids       = []
    metadatas = []

    for filename, prefix in doc_files:
        if not os.path.exists(filename):
            continue

        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()

        chunk_size    = 500
        overlap       = 50
        words         = content.split()
        chunk_index   = 0

        for i in range(0, len(words), chunk_size - overlap):
            chunk  = " ".join(words[i:i + chunk_size])
            doc_id = f"doc_{prefix}_{chunk_index}"

            if doc_id not in existing_ids:
                texts.append(chunk)
                ids.append(doc_id)
                metadatas.append({
                    "source":      filename,
                    "chunk_index": chunk_index,
                    "type":        "documentation",
                })

            chunk_index += 1

    if not texts:
        log.info("No new documentation to index")
        return 0

    batch_size = 50
    indexed    = 0
    for i in range(0, len(texts), batch_size):
        batch_texts     = texts[i:i + batch_size]
        batch_ids       = ids[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]
        embeddings      = _embed(batch_texts)
        collection.add(
            documents  = batch_texts,
            embeddings = embeddings,
            ids        = batch_ids,
            metadatas  = batch_metadatas,
        )
        indexed += len(batch_texts)

    log.info("Indexed %s documentation chunks", indexed)
    return indexed


def run_full_index(full_reindex: bool = False) -> dict:
    log.info("Starting full index (full_reindex=%s)", full_reindex)
    results = {
        "trades":       index_trades(full_reindex),
        "signals":      index_signals(full_reindex),
        "daily":        index_daily_summaries(full_reindex),
        "coins":        index_coin_performance(full_reindex),
        "docs":         index_documentation(full_reindex),
    }
    total = sum(results.values())
    log.info("Full index complete — total chunks: %s | breakdown: %s", total, results)
    return results


def run_incremental_index() -> dict:
    return run_full_index(full_reindex=False)


import os