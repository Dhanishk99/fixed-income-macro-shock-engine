# Methodology, Assumptions and Limitations

## 1. What this model is

A deterministic scenario stress test. It answers one question: if a specified
shock hit the portfolio instantaneously, what would happen to the capital?

It is **not** a value-at-risk model — no probabilities are attached to any
scenario. It is **not** a forecast. It is **not** a pricing model — no
individual bond cash flows are discounted.

## 2. The pricing relationship

For a bond or bond fund, price sensitivity to yield is conventionally expressed
as a Taylor expansion:

```
%ΔP ≈ −D_eff × Δy  +  ½ × C × (Δy)²
```

This model retains only the first-order term. For a credit instrument the yield
decomposes into a benchmark rate and an option-adjusted spread, each of which
can move independently, giving two sensitivity terms:

```
%ΔP ≈ −D_eff × Δ(benchmark)  −  D_spread × Δ(OAS)
```

This two-leg form is what the engine implements. The spread leg is zero for
Treasury holdings.

Effective duration is used rather than modified duration because the underlying
holdings contain embedded options — the majority of US high yield bonds are
callable, and call features are present across investment grade. Effective
duration is computed by the fund provider by repricing under up and down curve
shifts while allowing cash flows to change, which is the correct measure when
optionality is present. Consistently, the spread shocks are expressed as
option-adjusted spread movements.

## 3. Assumptions register

| # | Assumption | Rationale | Effect if wrong |
|---|-----------|-----------|-----------------|
| 1 | ETFs proxy their asset classes cleanly | Highly liquid, index-tracking, published characteristics | Tracking error and expense ratios ignored; immaterial over an instantaneous horizon |
| 2 | First-order pricing only; convexity excluded | Scope decision; keeps the model transparent | Losses overstated on large shocks. Under the Severe scenario, published convexity figures imply a true loss nearer 15.3% versus the 17.1% reported — a cushion for TLT and LQD, but not for HYG, whose convexity is negative |
| 3 | Effective duration proxies spread duration | For fixed-coupon cash bonds a 1bp move hurts identically whether it originates in rates or spread | Minor. Divergence is larger for high yield, where realised rate sensitivity runs below stated duration |
| 4 | Shocks are instantaneous | Isolates the capital effect | No carry or coupon income offsets the loss; the model is conservative |
| 5 | Rates and spreads shock adversely together | Deliberate correlation-breakdown stress, consistent with an inflation-shock regime such as 2022 | Harsher than a typical growth scare, where Treasuries rally as spreads widen. This is the point of the scenario |
| 6 | Each holding maps to one curve node | Three-node key-rate simplification | Real funds span maturities; stressed curves therefore move in parallel steps within each node |
| 7 | Durations held constant through the shock | Point-in-time characteristics | Duration would drift as yields move; second-order effect |
| 8 | Closing duration uses opening durations with closing weights | Isolates the allocation effect | Does not capture duration drift within each fund |
| 9 | yfinance prices treated as fair marks | Adequate for a proxy portfolio | Not institutional-grade pricing; a Bloomberg or index-provider feed would be used in production |
| 10 | Duration vintage may lag the reporting date | Daily figures are rendered client-side and unreachable by scraper; fact sheets are quarterly | Sensitivity is small — a 2% duration error moves the Adverse loss by roughly $90k on an $8.8M estimate |

## 4. Scenario calibration

Shock sizes are analyst judgment, not retrieved data. They are anchored to the
observed market episode between the July 29, 2026 FOMC decision and August 14,
2026, sourced from the US Treasury daily par yield curve:

| | Jul 28 | Aug 14 | Change |
|---|---|---|---|
| 2Y | 4.26% | 4.17% | −9bp |
| 5Y | 4.35% | 4.36% | +1bp |
| 10Y | 4.61% | 4.68% | +7bp |
| 30Y | 5.09% | 5.25% | +16bp |
| 2s30s | +83bp | +108bp | +25bp steeper |

The episode was a twist steepener: the front end rallied as September hike odds
fell following a negative payrolls print, while the long end sold off on supply
and term-premium pressure. The scenarios extend this shape rather than imposing
a parallel shift.

Spread calibration references LQD's option-adjusted spread of approximately
84bp as at August 13, 2026 — historically tight against a long-run average near
160bp. The Adverse IG shock of +75bp therefore represents mean reversion. For
context, investment grade spreads reached approximately 400bp in March 2020 and
600bp in 2008, so the Severe scenario sits between a 2022-style repricing and a
genuine liquidity crisis.

High yield spread shocks are set at roughly 3.2 times the investment grade
shock, consistent with historical beta in risk-off episodes.

## 5. Data validation controls

- Portfolio weights must sum to 1.0 or the run aborts.
- Every holding's curve node must exist in every scenario definition.
- Every resolved duration is range-checked (TLT 12–20, LQD 6–11, HYG 2–5.5
  years) before entering the calculation. An out-of-range value halts the run.
- Duration source and as-of date are printed for every holding on every run, so
  the vintage of every input is visible in the output.

## 6. Known extensions not implemented

- Convexity as a second-order term
- Separate spread duration inputs
- Full key-rate duration vector rather than three nodes
- Carry and roll-down over a defined horizon
- Historical scenario replay (2013 taper, 2020 March, 2022 full year)
- Probability weighting across scenarios
