import os
import logging
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

CHART_DIR = "content/charts"


def _ensure_chart_dir():
    Path(CHART_DIR).mkdir(parents=True, exist_ok=True)


def generate_signal_chart(signal_id: int) -> str | None:
    """
    Generate a signal chart PNG for a given signal_id.
    Reads Signal from DB, reads last 50 4H candles from Candle table.
    Returns file path or None on failure.
    """
    try:
        import mplfinance as mpf
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.lines import Line2D
        import pandas as pd
        from database import SessionLocal, Signal as SignalModel, Candle

        _ensure_chart_dir()

        with SessionLocal() as db:
            signal = db.query(SignalModel).filter(
                SignalModel.id == signal_id
            ).first()

            if not signal:
                log.error(f"Signal {signal_id} not found")
                return None

            candles = db.query(Candle).filter(
                Candle.coin      == signal.coin,
                Candle.timeframe == "4h"
            ).order_by(Candle.timestamp.desc()).limit(60).all()

        if not candles or len(candles) < 10:
            log.error(f"Not enough candles for {signal.coin}")
            return None

        candles = list(reversed(candles))

        df = pd.DataFrame([{
            "Date":   pd.Timestamp(c.timestamp, unit="ms"),
            "Open":   c.open,
            "High":   c.high,
            "Low":    c.low,
            "Close":  c.close,
            "Volume": c.volume
        } for c in candles])
        df = df.set_index("Date")

        is_long    = signal.direction == "LONG"
        entry      = signal.entry
        sl         = signal.sl
        tp1        = signal.tp1
        tp2        = signal.tp2
        grade      = signal.grade
        score      = signal.score
        coin       = signal.coin
        direction  = signal.direction

        # Color scheme
        bg_color     = "#0d1117"
        grid_color   = "#21262d"
        text_color   = "#e6edf3"
        entry_color  = "#0071e3"
        sl_color     = "#ff3b30"
        tp1_color    = "#34c759"
        tp2_color    = "#30d158"
        up_color     = "#34c759"
        down_color   = "#ff3b30"
        volume_color = "#21262d"

        grade_colors = {
            "A+": "#34c759",
            "A":  "#0071e3",
            "B":  "#ff9500",
            "C":  "#7d5a00",
            "F":  "#6e6e73"
        }
        grade_color = grade_colors.get(grade, "#6e6e73")

        # mplfinance style
        mc = mpf.make_marketcolors(
            up       = up_color,
            down     = down_color,
            edge     = "inherit",
            wick     = "inherit",
            volume   = volume_color,
        )

        style = mpf.make_mpf_style(
            marketcolors = mc,
            facecolor    = bg_color,
            edgecolor    = grid_color,
            figcolor     = bg_color,
            gridcolor    = grid_color,
            gridstyle    = "--",
            gridaxis     = "both",
            y_on_right   = True,
            rc           = {
                "axes.labelcolor":  text_color,
                "xtick.color":      text_color,
                "ytick.color":      text_color,
                "text.color":       text_color,
                "font.family":      "monospace",
                "font.size":        9,
            }
        )

        # Horizontal lines
        hlines_prices = []
        hlines_colors = []
        hlines_styles = []
        hlines_widths = []

        if entry:
            hlines_prices.append(entry)
            hlines_colors.append(entry_color)
            hlines_styles.append("--")
            hlines_widths.append(1.5)

        if sl:
            hlines_prices.append(sl)
            hlines_colors.append(sl_color)
            hlines_styles.append("-")
            hlines_widths.append(1.5)

        if tp1:
            hlines_prices.append(tp1)
            hlines_colors.append(tp1_color)
            hlines_styles.append("-")
            hlines_widths.append(1.5)

        if tp2:
            hlines_prices.append(tp2)
            hlines_colors.append(tp2_color)
            hlines_styles.append("--")
            hlines_widths.append(1.0)

        hlines_dict = dict(
            hlines = hlines_prices,
            colors = hlines_colors,
            linestyle = hlines_styles,
            linewidths = hlines_widths
        )

        # Sweep zone shading — find sweep candle
        sweep_patches = []
        try:
            sweep_idx = None
            for i in range(len(df) - 1, max(len(df) - 15, 0), -1):
                row = df.iloc[i]
                if is_long and row["Low"] < entry * 0.995:
                    sweep_idx = i
                    break
                elif not is_long and row["High"] > entry * 1.005:
                    sweep_idx = i
                    break

            if sweep_idx is not None:
                start = max(0, sweep_idx - 1)
                end   = min(len(df) - 1, sweep_idx + 2)
                sweep_patches.append({
                    "start": start,
                    "end":   end,
                    "color": "#ffcc00",
                    "alpha": 0.15
                })
        except Exception:
            pass

        fig, axes = mpf.plot(
            df,
            type        = "candle",
            style       = style,
            volume      = True,
            figsize     = (12, 6.75),
            hlines      = hlines_dict,
            returnfig   = True,
            panel_ratios = (4, 1),
            tight_layout = True,
        )

        ax_main = axes[0]
        ax_vol  = axes[2] if len(axes) > 2 else axes[1]

        # Sweep zone shading
        for patch in sweep_patches:
            ax_main.axvspan(
                patch["start"] - 0.5,
                patch["end"]   + 0.5,
                color = patch["color"],
                alpha = patch["alpha"],
                zorder = 0
            )

        # Price labels on lines
        price_labels = []
        if entry: price_labels.append((entry, f"ENTRY {entry:.4f}", entry_color))
        if sl:    price_labels.append((sl,    f"SL {sl:.4f}",       sl_color))
        if tp1:   price_labels.append((tp1,   f"TP1 {tp1:.4f}",     tp1_color))
        if tp2:   price_labels.append((tp2,   f"TP2 {tp2:.4f}",     tp2_color))

        xlim = ax_main.get_xlim()
        for price, label, color in price_labels:
            ax_main.text(
                xlim[1] * 0.98, price, label,
                color     = color,
                fontsize  = 8,
                fontweight = "bold",
                ha        = "right",
                va        = "center",
                bbox      = dict(
                    boxstyle  = "round,pad=0.2",
                    facecolor = bg_color,
                    edgecolor = color,
                    alpha     = 0.8
                )
            )

        # Grade badge — top left
        grade_badge_text = f"Grade {grade}  {score}/100"
        ax_main.text(
            0.02, 0.97, grade_badge_text,
            transform  = ax_main.transAxes,
            color      = grade_color,
            fontsize   = 13,
            fontweight = "bold",
            va         = "top",
            ha         = "left",
            bbox       = dict(
                boxstyle  = "round,pad=0.4",
                facecolor = bg_color,
                edgecolor = grade_color,
                alpha     = 0.9,
                linewidth = 2
            )
        )

        # Coin + direction — top center
        dir_emoji  = "▲ LONG" if is_long else "▼ SHORT"
        dir_color  = up_color if is_long else down_color
        title_text = f"{coin}USDT  {dir_emoji}"
        ax_main.text(
            0.5, 0.97, title_text,
            transform  = ax_main.transAxes,
            color      = dir_color,
            fontsize   = 14,
            fontweight = "bold",
            va         = "top",
            ha         = "center",
            bbox       = dict(
                boxstyle  = "round,pad=0.4",
                facecolor = bg_color,
                edgecolor = dir_color,
                alpha     = 0.9,
                linewidth = 2
            )
        )

        # Timeframe label — top right
        ax_main.text(
            0.98, 0.97, "4H",
            transform  = ax_main.transAxes,
            color      = text_color,
            fontsize   = 10,
            fontweight = "bold",
            va         = "top",
            ha         = "right",
            alpha      = 0.7
        )

        # Timestamp — bottom left
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        ax_main.text(
            0.02, 0.02, ts,
            transform = ax_main.transAxes,
            color     = text_color,
            fontsize  = 7,
            va        = "bottom",
            ha        = "left",
            alpha     = 0.5
        )

        # Signal Engine watermark — bottom right
        ax_main.text(
            0.98, 0.02, "Signal Engine v5",
            transform  = ax_main.transAxes,
            color      = text_color,
            fontsize   = 8,
            fontweight = "bold",
            va         = "bottom",
            ha         = "right",
            alpha      = 0.4
        )

        # Legend
        legend_elements = []
        if entry: legend_elements.append(Line2D([0], [0], color=entry_color, linewidth=1.5, linestyle="--", label=f"Entry {entry:.4f}"))
        if sl:    legend_elements.append(Line2D([0], [0], color=sl_color,    linewidth=1.5, linestyle="-",  label=f"SL {sl:.4f}"))
        if tp1:   legend_elements.append(Line2D([0], [0], color=tp1_color,   linewidth=1.5, linestyle="-",  label=f"TP1 {tp1:.4f}"))
        if tp2:   legend_elements.append(Line2D([0], [0], color=tp2_color,   linewidth=1.0, linestyle="--", label=f"TP2 {tp2:.4f}"))

        if legend_elements:
            ax_main.legend(
                handles   = legend_elements,
                loc       = "upper left",
                fontsize  = 8,
                facecolor = bg_color,
                edgecolor = grid_color,
                labelcolor = text_color,
                framealpha = 0.9,
                bbox_to_anchor = (0.02, 0.88)
            )

        # Save
        chart_path = os.path.join(CHART_DIR, f"{signal_id}.png")
        fig.savefig(
            chart_path,
            dpi         = 150,
            bbox_inches = "tight",
            facecolor   = bg_color,
            edgecolor   = "none"
        )
        plt.close(fig)

        log.info(f"Chart saved: {chart_path}")
        return chart_path

    except Exception as e:
        log.error(f"Chart generation error signal {signal_id}: {e}")
        import traceback
        log.error(traceback.format_exc())
        return None