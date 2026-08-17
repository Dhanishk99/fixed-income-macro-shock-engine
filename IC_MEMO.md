# Investment Committee Memorandum

**To:** Investment Committee
**From:** Dhanish Kandhari, Portfolio Analytics
**Date:** 17 August 2026
**Subject:** Macro shock stress test — $100M multi-asset fixed income portfolio

---

## Recommendation

The portfolio carries a weighted duration of 9.90 years against a book in which
60% of capital sits in spread product. Under an adverse repricing of rates and
credit together, the estimated capital loss is **8.8% ($8.8M)**; under a severe
policy-credibility shock, **17.1% ($17.1M)**.

The exposure is not diversified in any meaningful sense against this class of
shock. I recommend the Committee consider (i) reducing long-end duration in the
Treasury allocation, and (ii) recognising that the high yield allocation is
carrying spread risk that its size understates.

## Position

| Holding | Asset class | Weight | Capital | Effective duration |
|---------|-------------|--------|---------|--------------------|
| TLT | Long-dated US Treasuries | 40% | $40.0M | 14.92 yrs |
| LQD | US investment grade credit | 45% | $45.0M | 7.74 yrs |
| HYG | US high yield credit | 15% | $15.0M | 2.98 yrs |
| | **Portfolio** | **100%** | **$100.0M** | **9.90 yrs** |

Durations sourced from iShares as at 13 August 2026.

## Market context

Between the 29 July FOMC decision and 14 August, the curve twist-steepened. The
2-year yield fell 9bp as September hike expectations receded following a
negative July payrolls print (−23,000 against +83,000 expected, with 103,000 of
prior-month downward revisions). The 30-year rose 16bp to 5.25%, having touched
a nineteen-year high of 5.28% on 31 July. 2s30s widened 25bp.

The material point for this portfolio: the long end is no longer trading
inflation expectations alone. It is absorbing Treasury supply and the withdrawal
of a large foreign buyer, with Japan selling Treasuries to fund yen
intervention. Front-end relief has not transmitted to the long end, and our
duration is concentrated there.

Credit has not participated. LQD's option-adjusted spread stands at
approximately 84bp against a long-run average near 160bp. The portfolio is
therefore long spread risk at historically tight levels.

## Stress results

| Scenario | TLT | LQD | HYG | Portfolio | Closing value |
|----------|-----|-----|-----|-----------|---------------|
| Moderate | −3.73% | −3.10% | −2.53% | **−3.27%** | $96.7M |
| Adverse | −8.95% | −8.90% | −8.20% | **−8.82%** | $91.2M |
| Severe | −17.90% | −17.42% | −14.16% | **−17.12%** | $82.9M |

## Findings

**1. Asset-class diversification provides no protection against this shock.**
Under the Adverse scenario the three holdings land within 75bp of one another
despite entirely different credit profiles. Diversification helps when risk
factors move independently; here rates and spreads move together, and every
holding is exposed to at least one of them.

**2. The loss mechanisms are entirely different, which matters for hedging.**
TLT's loss is pure duration. LQD's divides roughly evenly between the rate and
spread legs. HYG's is almost entirely spread — its 2.98-year duration absorbs
the rate shock almost completely. A duration hedge would protect TLT and half of
LQD, and would do nothing for HYG.

**3. Position size, not volatility, determines dollar risk.** LQD produces the
largest dollar loss in the Adverse case at $4.0M, exceeding TLT's $3.6M despite
a smaller percentage move, because it is the largest allocation and absorbs both
shocks.

**4. The portfolio does not self-correct.** Weighted duration moves only from
9.90 to 9.89 years under the Adverse scenario. Losses are sufficiently uniform
that the risk profile emerges from the shock essentially unchanged — the book
does not passively de-risk. Any reduction in duration must be deliberate.

**5. The high yield allocation is the most spread-sensitive per dollar.** At 15%
of capital, HYG contributes $1.2M of the Adverse loss, 94% of which comes from
the spread leg. Its short duration is protective on rates and irrelevant on
credit.

## Model limitations

The model is first-order: convexity is excluded, which overstates losses on the
largest shocks. On the Severe scenario, published convexity figures imply a true
loss nearer 15.3% than the 17.1% reported — a cushion for TLT and LQD, but not
for HYG, whose convexity is negative. Effective duration proxies spread
duration. Shocks are instantaneous, with no coupon income offsetting the capital
loss. Each holding maps to a single curve node.

Scenario shock sizes are analyst assumptions, calibrated to the observed
July–August curve move and to current spread levels. They carry no probability
weighting. Full detail in `METHODOLOGY.md`.

## Suggested follow-up

- Key-rate duration decomposition to locate the exposure precisely along the
  curve rather than at three nodes
- Historical scenario replay (2013 taper, March 2020, full-year 2022) as a
  cross-check on the assumed shock sizes
- Assessment of whether the Treasury allocation's long-end concentration is
  intentional or an artifact of proxy selection
