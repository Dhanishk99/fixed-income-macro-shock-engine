# Fixed Income Macro Shock Risk Engine

A Python stress-testing tool that measures how a $100M multi-asset fixed income
portfolio behaves under non-parallel yield curve shifts and credit spread
widening. Built to answer a specific question: when the curve steepens and
spreads reprice at the same time, where does the capital actually go?

Market inputs are retrieved at runtime. No investment characteristics are
hardcoded.

---

## The portfolio

| Holding | Weight | Capital | Asset class | Risk exposure |
|---------|--------|---------|-------------|---------------|
| TLT | 40% | $40M | Long-dated US Treasuries | Interest rate only |
| LQD | 45% | $45M | US investment grade credit | Interest rate + credit spread |
| HYG | 15% | $15M | US high yield credit | Interest rate + credit spread |

Each holding is mapped to the segment of the curve that drives it — high yield
to the short end, investment grade to the belly, long Treasuries to the long
end — so a steepening curve hits the three positions unevenly.

## The scenarios

Shock sizes are analyst assumptions calibrated to the realised curve move
between the July 29, 2026 FOMC decision and August 14, 2026: the front end
rallied 9bp while the 30Y sold off 16bp to 5.25%, steepening 2s30s by 25bp.

| | Short end | Belly | Long end | IG spread | HY spread |
|---|---|---|---|---|---|
| **Moderate** | +10bp | +15bp | +25bp | +25bp | +75bp |
| **Adverse** | +25bp | +40bp | +60bp | +75bp | +250bp |
| **Severe** | +75bp | +100bp | +120bp | +125bp | +400bp |

Spread shocks are differentiated by credit quality: high yield spreads
historically move three to four times investment grade in risk-off episodes.
LQD's option-adjusted spread was approximately 84bp on August 13, 2026 against
a long-run average near 160bp, so the Adverse IG shock represents reversion to
that average rather than a crisis.

## Results

| Scenario | Portfolio return | Closing value | TLT | LQD | HYG |
|----------|-----------------|---------------|-----|-----|-----|
| Moderate | −3.27% | $96.7M | −3.73% | −3.10% | −2.53% |
| Adverse | −8.82% | $91.2M | −8.95% | −8.90% | −8.20% |
| Severe | −17.12% | $82.9M | −17.90% | −17.42% | −14.16% |

Three observations worth drawing out:

**Diversification across asset classes did not help.** In the Adverse case all
three holdings land within 75bp of each other despite completely different risk
profiles. When rates and spreads move together, credit quality offers no
shelter — only the mechanism of loss differs.

**The mechanisms differ entirely.** TLT's loss is pure duration. LQD's splits
roughly evenly between rate and spread. HYG's is almost entirely spread, with
its 2.98-year duration absorbing the rate shock.

**Position size drives dollar risk.** LQD posts the largest dollar loss in the
Adverse case (−$4.0M) despite a smaller percentage move than TLT, because it is
the largest holding and takes both shocks.

## Methodology

Return is a first-order duration approximation applied as two independent legs:

```
return = -(effective duration × rate shock) - (effective duration × spread shock)
```

The spread leg is zero for Treasuries. Dollar P&L is applied to each holding's
opening capital; closing weights are recomputed against the reduced portfolio,
which shows how a shock passively rebalances a book — holdings that lose least
gain weight without a single trade.

See `METHODOLOGY.md` for the full assumptions and limitations register.

## Data sourcing

**Prices** — latest close per holding via `yfinance`.

**Effective duration** — resolved through three layers, in order:

1. **Manual override.** The iShares product pages publish duration daily but
   render it client-side, so it is unreachable by a `requests`-based scraper.
   Values read from those pages are recorded in code with their source and
   as-of date, and are subject to the same validation as scraped values.
2. **Official fact sheet PDF.** Parsed at runtime from BlackRock's literature
   server, which serves the document without bot protection. Quarterly vintage.
3. **Product page HTML.** Anchors on the visible "Effective Duration" label
   rather than CSS classes, which change more often than label text.

Every resolved duration is checked against a plausible range before it can
enter the calculation (TLT 12–20, LQD 6–11, HYG 2–5.5 years). A value outside
its range halts the run. A silent bad input is worse than a failed run.

The reference Treasury curve used in reporting is the official US Treasury
daily par yield curve for July 28 and August 14, 2026.

## Running it

```bash
pip install -r requirements.txt
python fixed_income_risk_engine.py
```

Outputs a scenario-by-scenario terminal report plus two charts:
`LI_1_curve.png` (reference and stressed yield curves) and `LI_2_portfolio.png`
(closing portfolio value by scenario).

## Files

```
fixed_income_risk_engine.py   the engine
METHODOLOGY.md                assumptions and limitations register
IC_MEMO.md                    investment committee brief
requirements.txt              dependencies
LI_1_curve.png                yield curve chart
LI_2_portfolio.png            portfolio impact chart
```

## Limitations

The model is deliberately first-order. Convexity is excluded, which modestly
overstates losses on the largest shocks. Effective duration proxies spread
duration. Each holding maps to a single curve node. Shocks are instantaneous,
with no carry or coupon income offsetting the capital loss. These are documented
in full in `METHODOLOGY.md` rather than buried.

This is a scenario stress test, not a forecast and not a value-at-risk model.
It attaches no probabilities to any scenario.
