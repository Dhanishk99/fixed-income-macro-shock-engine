"""
Fixed Income Macro Shock Risk Engine
====================================

Deterministic scenario stress test of a $100M multi-asset fixed income
portfolio under non-parallel yield curve shifts and credit spread widening.

Portfolio proxies:
    TLT  40%  long-dated US Treasuries       (rate risk only)
    LQD  45%  US investment grade credit     (rate + spread risk)
    HYG  15%  US high yield credit           (rate + spread risk)

Market inputs are retrieved at runtime; no investment characteristics are
hardcoded. Scenario shock sizes are analyst assumptions, documented below.

Usage:
    python fixed_income_risk_engine.py

Author: Dhanish Kandhari
"""

import re
import sys

import requests
import yfinance as yf
from bs4 import BeautifulSoup

# =============================================================================
# 1. PORTFOLIO DEFINITION
# =============================================================================

PORTFOLIO_VALUE = 100_000_000

# curve_node maps each holding to the segment of the curve that drives it.
# has_credit_risk gates the spread leg of the return calculation.
PORTFOLIO = {
    "TLT": {
        "name": "iShares 20+ Year Treasury Bond ETF",
        "allocation": "Long-Term US Treasuries",
        "weight": 0.40,
        "curve_node": "long",
        "has_credit_risk": False,
    },
    "LQD": {
        "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
        "allocation": "US Investment Grade Credit",
        "weight": 0.45,
        "curve_node": "belly",
        "has_credit_risk": True,
    },
    "HYG": {
        "name": "iShares iBoxx $ High Yield Corporate Bond ETF",
        "allocation": "US High Yield Credit",
        "weight": 0.15,
        "curve_node": "short",
        "has_credit_risk": True,
    },
}

# =============================================================================
# 2. SCENARIO DEFINITIONS
# =============================================================================
# Shock sizes are analyst assumptions, not market data. They are calibrated to
# the realised curve move between the July 29 2026 FOMC decision and Aug 14
# 2026, during which the front end rallied 9bp while the 30Y sold off 16bp to
# 5.25% and 2s30s steepened 25bp. Each scenario extends that dynamic.
#
# Spread shocks are differentiated: high yield spreads historically move three
# to four times investment grade in risk-off episodes. LQD's option-adjusted
# spread was ~84bp on Aug 13 2026, against a long-run average near 160bp, so
# the Adverse IG shock represents reversion to that average rather than crisis.

SCENARIOS = {
    "Moderate": {
        "description": "Current steepening drift persists; credit stays orderly",
        "rate_shock": {"short": 0.0010, "belly": 0.0015, "long": 0.0025},
        "spread_shock": {"TLT": 0.0, "LQD": 0.0025, "HYG": 0.0075},
    },
    "Adverse": {
        "description": "Inflation risk re-priced; IG spreads revert to long-run average",
        "rate_shock": {"short": 0.0025, "belly": 0.0040, "long": 0.0060},
        "spread_shock": {"TLT": 0.0, "LQD": 0.0075, "HYG": 0.0250},
    },
    "Severe": {
        "description": "Policy credibility shock with broad credit dislocation",
        "rate_shock": {"short": 0.0075, "belly": 0.0100, "long": 0.0120},
        "spread_shock": {"TLT": 0.0, "LQD": 0.0125, "HYG": 0.0400},
    },
}

# US Treasury par yields used as the reference curve for reporting.
# Source: US Treasury daily par yield curve.
CURVE_MATURITIES = [2, 3, 5, 7, 10, 20, 30]
CURVE_PRE_FOMC = [4.26, 4.31, 4.35, 4.47, 4.61, 5.11, 5.09]   # Jul 28 2026
CURVE_CURRENT = [4.17, 4.24, 4.36, 4.51, 4.68, 5.25, 5.25]    # Aug 14 2026
CURVE_NODE_BY_MATURITY = {2: "short", 3: "short", 5: "belly", 7: "belly",
                          10: "long", 20: "long", 30: "long"}

# =============================================================================
# 3. MARKET DATA INGESTION
# =============================================================================

ISHARES_URLS = {
    "TLT": "https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf",
    "LQD": "https://www.ishares.com/us/products/239566/ishares-iboxx-investment-grade-corporate-bond-etf",
    "HYG": "https://www.ishares.com/us/products/239565/ishares-iboxx-high-yield-corporate-bond-etf",
}

FACT_SHEET_URLS = {
    "TLT": "https://www.ishares.com/us/literature/fact-sheet/tlt-ishares-20-year-treasury-bond-etf-fund-fact-sheet-en-us.pdf",
    "LQD": "https://www.ishares.com/us/literature/fact-sheet/lqd-ishares-iboxx-investment-grade-corporate-bond-etf-fund-fact-sheet-en-us.pdf",
    "HYG": "https://www.ishares.com/us/literature/fact-sheet/hyg-ishares-iboxx-high-yield-corporate-bond-etf-fund-fact-sheet-en-us.pdf",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

# Plausible ranges per holding. A scraped value outside its range indicates the
# wrong field was captured, which halts the run rather than corrupting the P&L.
DURATION_BOUNDS = {"TLT": (12.0, 20.0), "LQD": (6.0, 11.0), "HYG": (2.0, 5.5)}

# The iShares product pages publish duration daily but render it client-side,
# so it is not reachable by a requests-based scraper. Values read from those
# pages are recorded here with their source and as-of date; set an entry to
# None to fall back to the automated fact sheet route.
DURATION_OVERRIDES = {
    "TLT": (14.92, "iShares product page, as of Aug 13, 2026"),
    "LQD": (7.74, "iShares product page, as of Aug 13, 2026"),
    "HYG": (2.98, "iShares product page, as of Aug 13, 2026"),
}


def fetch_prices():
    """Return the latest close for each holding."""
    prices = {}
    for ticker in PORTFOLIO:
        history = yf.Ticker(ticker).history(period="5d")
        if history.empty:
            raise RuntimeError(f"No price data returned for {ticker}")
        prices[ticker] = float(history["Close"].iloc[-1])
    return prices


def _get(url, binary=False):
    """HTTP GET impersonating Chrome's TLS fingerprint.

    iShares fingerprints the TLS handshake, so a plain requests call is served
    an empty shell page regardless of headers. curl_cffi ships with yfinance.
    """
    try:
        from curl_cffi import requests as browser
        response = browser.get(url, impersonate="chrome", timeout=30)
    except ImportError:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
    response.raise_for_status()
    return response.content if binary else response.text


def _duration_from_fact_sheet(ticker):
    """Parse effective duration and as-of date from the official fact sheet."""
    from io import BytesIO
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(_get(FACT_SHEET_URLS[ticker], binary=True)))
    text = " ".join((page.extract_text() or "") for page in reader.pages[:2])

    match = re.search(r"Effective\s+Duration\s*:?\s*(\d+\.\d+)", text)
    if not match:
        raise RuntimeError(f"{ticker}: duration not found in fact sheet")

    as_of = re.search(r"as of\s+([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    return float(match.group(1)), as_of.group(1) if as_of else "unknown date"


def _duration_from_product_page(ticker):
    """Parse effective duration from the product page HTML.

    Anchors on the visible label rather than CSS classes, which change more
    often than the label text does.
    """
    html = _get(ISHARES_URLS[ticker])
    label = BeautifulSoup(html, "html.parser").find(
        string=re.compile(r"Effective\s+Duration", re.I))
    if label is None:
        raise RuntimeError(f"{ticker}: duration label not present in page HTML")

    node = label.parent
    for _ in range(4):
        if node is None:
            break
        after_label = re.split(r"Effective\s+Duration", node.get_text(" ", strip=True),
                               flags=re.I)[-1]
        value = re.search(r"(\d+\.\d+)", after_label)
        if value:
            return float(value.group(1))
        node = node.parent
    raise RuntimeError(f"{ticker}: no value found adjacent to duration label")


def _validate(ticker, value, source):
    low, high = DURATION_BOUNDS[ticker]
    if not low <= value <= high:
        raise RuntimeError(
            f"{ticker}: duration {value} from {source} falls outside the "
            f"plausible range [{low}, {high}]; halting rather than using it")
    return value, source


def fetch_duration(ticker):
    """Resolve effective duration: manual override, then fact sheet, then HTML."""
    override = DURATION_OVERRIDES.get(ticker)
    if override:
        return _validate(ticker, override[0], f"manual override — {override[1]}")

    try:
        value, as_of = _duration_from_fact_sheet(ticker)
        return _validate(ticker, value, f"fact sheet, as of {as_of}")
    except Exception as exc:
        print(f"  {ticker}: fact sheet unavailable ({exc}); trying product page")

    return _validate(ticker, _duration_from_product_page(ticker), "product page HTML")


def fetch_market_data():
    print("MARKET DATA")
    print("-" * 78)
    prices = fetch_prices()
    durations, sources = {}, {}
    for ticker in PORTFOLIO:
        durations[ticker], sources[ticker] = fetch_duration(ticker)
        print(f"  {ticker}   ${prices[ticker]:>7,.2f}   duration {durations[ticker]:>5.2f} yrs"
              f"   [{sources[ticker]}]")
    print()
    return {"prices": prices, "durations": durations, "sources": sources}


# =============================================================================
# 4. RISK ENGINE
# =============================================================================

def run_scenario(durations, scenario):
    """Apply one scenario to the portfolio.

    Return is a first-order duration approximation with two independent legs:

        return = -(duration x rate shock) - (duration x spread shock)

    The spread leg is zero for Treasuries. Effective duration proxies spread
    duration; for fixed-coupon cash bonds the two are close enough that the
    simplification is immaterial at these shock sizes.
    """
    results = {}
    for ticker, holding in PORTFOLIO.items():
        duration = durations[ticker]
        rate_shock = scenario["rate_shock"][holding["curve_node"]]
        spread_shock = (scenario["spread_shock"][ticker]
                        if holding["has_credit_risk"] else 0.0)

        rate_return = -(duration * rate_shock)
        spread_return = -(duration * spread_shock)
        total_return = rate_return + spread_return
        opening_value = PORTFOLIO_VALUE * holding["weight"]

        results[ticker] = {
            "duration": duration,
            "rate_shock_bp": rate_shock * 10_000,
            "spread_shock_bp": spread_shock * 10_000,
            "rate_return": rate_return,
            "spread_return": spread_return,
            "total_return": total_return,
            "opening_value": opening_value,
            "pnl": opening_value * total_return,
            "closing_value": opening_value * (1 + total_return),
        }

    closing_total = sum(r["closing_value"] for r in results.values())

    # Holdings that lose least gain weight as the portfolio shrinks around them.
    for result in results.values():
        result["closing_weight"] = result["closing_value"] / closing_total

    summary = {
        "closing_value": closing_total,
        "pnl": closing_total - PORTFOLIO_VALUE,
        "total_return": (closing_total - PORTFOLIO_VALUE) / PORTFOLIO_VALUE,
        "opening_duration": sum(durations[t] * PORTFOLIO[t]["weight"] for t in PORTFOLIO),
        # Same holding durations, post-shock weights: captures the allocation
        # effect only, not duration drift within each fund.
        "closing_duration": sum(durations[t] * results[t]["closing_weight"]
                                for t in PORTFOLIO),
    }
    return results, summary


def run_all_scenarios(market_data):
    return {name: run_scenario(market_data["durations"], scenario)
            for name, scenario in SCENARIOS.items()}


# =============================================================================
# 5. REPORTING
# =============================================================================

INK, BLUE, GOLD, CRIMSON, GREY = "#12203A", "#4A7FB5", "#C08A1E", "#A4243B", "#9AA5B1"
SCENARIO_COLOURS = {"Moderate": BLUE, "Adverse": GOLD, "Severe": CRIMSON}


def print_positions():
    print("PORTFOLIO")
    print("-" * 78)
    for ticker, holding in PORTFOLIO.items():
        print(f"  {ticker}   {holding['allocation']:<32}{holding['weight']:>6.0%}"
              f"{PORTFOLIO_VALUE * holding['weight']:>15,.0f}")
    print(f"  {'':<5}{'Total':<32}{1:>6.0%}{PORTFOLIO_VALUE:>15,.0f}\n")


def print_scenario(name, results, summary):
    scenario = SCENARIOS[name]
    print(f"{name.upper()}  —  {scenario['description']}")
    print("-" * 78)
    print(f"  {'':<5}{'Dur':>6}{'Rate':>8}{'Sprd':>8}{'RateRet':>10}"
          f"{'SprdRet':>10}{'Return':>9}{'P&L ($)':>14}")
    for ticker, r in results.items():
        print(f"  {ticker:<5}{r['duration']:>6.2f}{r['rate_shock_bp']:>7.0f}bp"
              f"{r['spread_shock_bp']:>7.0f}bp{r['rate_return']:>10.2%}"
              f"{r['spread_return']:>10.2%}{r['total_return']:>9.2%}"
              f"{r['pnl']:>14,.0f}")
    print(f"  {'Portfolio':<44}{summary['total_return']:>9.2%}{summary['pnl']:>14,.0f}")
    print(f"  Closing value ${summary['closing_value']:,.0f}   "
          f"duration {summary['opening_duration']:.2f} → "
          f"{summary['closing_duration']:.2f} yrs\n")


def chart_realised_move(filename="LI_0_twist.png"):
    """Change in yield by tenor over the reference period."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#4A5568"})
    changes = [(c - p) * 100 for p, c in zip(CURVE_PRE_FOMC, CURVE_CURRENT)]
    labels = [f"{m}Y" for m in CURVE_MATURITIES]
    x = np.arange(len(labels))
    colours = ["#2F855A" if v < 0 else CRIMSON for v in changes]

    fig, ax = plt.subplots(figsize=(11, 4.6))
    bars = ax.bar(x, changes, width=.62, color=colours)
    for bar, value in zip(bars, changes):
        offset = 1.1 if value >= 0 else -1.1
        ax.text(bar.get_x() + bar.get_width() / 2, value + offset,
                f"{value:+.0f}", ha="center",
                va="bottom" if value >= 0 else "top",
                fontweight="bold", fontsize=12,
                color="#2F855A" if value < 0 else CRIMSON)

    ax.axhline(0, color="#2D3748", lw=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=12.5, fontweight="bold")
    ax.set_ylim(-15, 22)
    ax.set_ylabel("Change in yield (bp)", fontsize=12)
    ax.grid(axis="y", alpha=.25, lw=.8)
    ax.spines[["top", "right", "bottom"]].set_visible(False)
    ax.set_title("One curve, two directions\n", fontsize=17, fontweight="bold",
                 loc="left", color=INK)
    ax.text(0, 1.03, "Change in US Treasury par yields by tenor, 28 July to 14 "
            "August 2026", transform=ax.transAxes, fontsize=12, color="#4A5568")
    ax.text(.985, .10, "front end rallied\nas hike odds fell", transform=ax.transAxes,
            fontsize=11, color="#2F855A", ha="right", va="bottom", linespacing=1.4)
    ax.text(.015, .93, "long end sold off\non supply pressure", transform=ax.transAxes,
            fontsize=11, color=CRIMSON, va="top", linespacing=1.4)
    fig.text(.012, .02, "Source: US Treasury daily par yield curve. The 5-year was the "
             "pivot of the move, effectively unchanged while both wings repriced in "
             "opposite directions.", fontsize=9.5, color="#718096")
    fig.tight_layout(rect=[0, .055, 1, 1])
    fig.savefig(filename, dpi=190)
    plt.close(fig)
    print(f"  {filename}")


def chart_yield_curve(filename="LI_1_curve.png"):
    """Reference curve and the three stressed curves."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#4A5568"})
    x = np.arange(len(CURVE_MATURITIES))
    fig, ax = plt.subplots(figsize=(11, 7))

    for name, scenario in SCENARIOS.items():
        stressed = [CURVE_CURRENT[i] + scenario["rate_shock"][CURVE_NODE_BY_MATURITY[m]] * 100
                    for i, m in enumerate(CURVE_MATURITIES)]
        ax.plot(x, stressed, color=SCENARIO_COLOURS[name], lw=2.4, ls="--",
                marker="^", ms=6, alpha=.92, zorder=3)
        ax.annotate(name, (x[-1], stressed[-1]), xytext=(10, 0),
                    textcoords="offset points", color=SCENARIO_COLOURS[name],
                    fontweight="bold", fontsize=12.5, va="center")

    ax.plot(x, CURVE_PRE_FOMC, color=GREY, lw=2.0, ls=":", marker="o", ms=5, zorder=4)
    ax.annotate("Jul 28 (pre-FOMC)", (x[-1], CURVE_PRE_FOMC[-1]), xytext=(10, -13),
                textcoords="offset points", color="#6B7280", fontsize=11, va="center")
    ax.plot(x, CURVE_CURRENT, color=INK, lw=3.4, marker="o", ms=7, zorder=5)
    ax.annotate("Aug 14 (actual)", (x[-1], CURVE_CURRENT[-1]), xytext=(10, 9),
                textcoords="offset points", color=INK, fontweight="bold",
                fontsize=12, va="center")

    ax.annotate("", xy=(0, CURVE_CURRENT[0] - .015), xytext=(0, CURVE_PRE_FOMC[0] + .015),
                arrowprops=dict(arrowstyle="->", color="#2F855A", lw=2.4))
    ax.annotate("", xy=(6, CURVE_CURRENT[-1] + .015), xytext=(6, CURVE_PRE_FOMC[-1] - .015),
                arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=2.4))

    rows = [("2Y yield", "−9 bp", "front end rallied"),
            ("30Y yield", "+16 bp", "long end sold off"),
            ("2s30s curve", "+25 bp", "steeper")]
    ax.text(0.12, 6.34, "Jul 28  →  Aug 14\n\n" + "\n".join(
        f"{a:<12}{b:>7}   {c}" for a, b, c in rows),
        fontsize=11.5, color=INK, va="top", linespacing=1.7, family="DejaVu Sans Mono",
        bbox=dict(boxstyle="round,pad=0.75", fc="#F7FAFC", ec="#CBD5E0", lw=1.1))

    ax.set_xticks(x)
    ax.set_xticklabels([f"{m}Y" for m in CURVE_MATURITIES], fontsize=12.5, fontweight="bold")
    ax.set_xlim(-0.3, 7.75)
    ax.set_ylabel("Yield (%)", fontsize=12.5)
    ax.set_xlabel("Maturity", fontsize=12.5)
    ax.grid(axis="y", alpha=.28, lw=.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("US Treasury yield curve: where it sits, and three ways it steepens\n",
                 fontsize=17, fontweight="bold", loc="left", color=INK)
    ax.text(0, 1.015, "Par yields around the July 29 FOMC decision, with stress "
            "scenarios applied to the current curve",
            transform=ax.transAxes, fontsize=12, color="#4A5568")
    fig.text(.012, .015, "Source: US Treasury daily par yield curve. Scenario shocks are "
             "analyst assumptions calibrated to the Jul 29 – Aug 14 move,\napplied at three "
             "curve nodes (short / belly / long), which is why the stressed lines move in "
             "parallel steps.", fontsize=9.5, color="#718096", linespacing=1.5)
    fig.tight_layout(rect=[0, .052, 1, 1])
    fig.savefig(filename, dpi=190)
    plt.close(fig)
    print(f"  {filename}")


def chart_portfolio_impact(all_results, filename="LI_2_portfolio.png"):
    """Closing portfolio value under each scenario."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#4A5568"})
    names = list(SCENARIOS)
    labels = ["Today"] + names
    values = [PORTFOLIO_VALUE / 1e6] + [all_results[n][1]["closing_value"] / 1e6
                                        for n in names]
    colours = [INK] + [SCENARIO_COLOURS[n] for n in names]

    fig, ax = plt.subplots(figsize=(11, 7))
    for i in range(1, len(labels)):
        ax.plot([i, i], [values[i], values[0]], color="#D8DEE6", lw=1.4, ls=":", zorder=1)
    ax.axhline(values[0], color="#B8C2CC", lw=1.3, ls="--", zorder=1)

    for i, (value, colour, label) in enumerate(zip(values, colours, labels)):
        ax.plot(i, value, "o", color=colour, ms=26, zorder=3)
        ax.annotate(f"${value:.1f}M", (i, value), xytext=(0, 26),
                    textcoords="offset points", ha="center", fontweight="bold",
                    fontsize=16, color=colour)
        if i:
            summary = all_results[label][1]
            ax.annotate(f"{summary['pnl'] / 1e6:+.1f}M\n{summary['total_return']:.1%}",
                        (i, value), xytext=(0, -46), textcoords="offset points",
                        ha="center", fontsize=12.5, color=colour, fontweight="bold",
                        linespacing=1.35)

    ax.text(0, 75.6, "$100M starting\n40 / 45 / 15", ha="center", fontsize=11,
            color="#6B7280", linespacing=1.45)
    for i, name in enumerate(names, start=1):
        s = SCENARIOS[name]
        ax.text(i, 75.6, f"long end +{s['rate_shock']['long'] * 1e4:.0f}bp\n"
                f"IG spread +{s['spread_shock']['LQD'] * 1e4:.0f}bp",
                ha="center", fontsize=11, color="#6B7280", linespacing=1.45)

    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, fontsize=14, fontweight="bold")
    ax.set_xlim(-.45, len(labels) - .55)
    ax.set_ylim(73.5, 106)
    ax.set_yticks([80, 85, 90, 95, 100, 105])
    ax.set_ylabel("Portfolio value (USD millions)", fontsize=12.5)
    ax.grid(axis="y", alpha=.28, lw=.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("What a steepening curve does to $100M\n",
                 fontsize=17, fontweight="bold", loc="left", color=INK)
    ax.text(0, 1.015, "40% long Treasuries (TLT) · 45% investment grade (LQD) · "
            "15% high yield (HYG) — three independent scenarios",
            transform=ax.transAxes, fontsize=12, color="#4A5568")
    fig.text(.012, .015, "Effective durations sourced from iShares, as of Aug 13, 2026. "
             "First-order duration model; convexity excluded,\nwhich modestly overstates "
             "losses on the largest shocks. Rate and spread shocks applied simultaneously.",
             fontsize=9.5, color="#718096", linespacing=1.5)
    fig.tight_layout(rect=[0, .052, 1, 1])
    fig.savefig(filename, dpi=190)
    plt.close(fig)
    print(f"  {filename}")


# =============================================================================
# 6. ENTRY POINT
# =============================================================================

def validate_portfolio():
    total = sum(h["weight"] for h in PORTFOLIO.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Portfolio weights sum to {total:.4f}, not 1.0")
    for ticker, holding in PORTFOLIO.items():
        for name, scenario in SCENARIOS.items():
            if holding["curve_node"] not in scenario["rate_shock"]:
                raise ValueError(f"{ticker}: node '{holding['curve_node']}' "
                                 f"missing from scenario '{name}'")


def main():
    print("\n" + "=" * 78)
    print("FIXED INCOME MACRO SHOCK RISK ENGINE".center(78))
    print("=" * 78 + "\n")

    validate_portfolio()
    print_positions()

    market_data = fetch_market_data()
    all_results = run_all_scenarios(market_data)

    for name in SCENARIOS:
        print_scenario(name, *all_results[name])

    print("CHARTS")
    print("-" * 78)
    chart_realised_move()
    chart_yield_curve()
    chart_portfolio_impact(all_results)
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit(f"Run failed: {error}")
