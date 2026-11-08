# Term Premium

**On econvitals.org:** the [Interest Rate Decomposer](https://econvitals.org/tools/interest-rate-decomposer/) — layer 3 (expected policy path and term premium) for every economy, and the base of layer 4 for the United States. Method note: [Methods](https://econvitals.org/methods/#term-premium).

**What it is.** A bond yield is what investors expect short rates to average over the bond’s life (the expected policy path) plus extra compensation for holding a long bond (the term premium). Neither piece is observable, so both are estimated. This is Econvitals’ own estimate, by the method of Adrian, Crump and Moench (“Pricing the term structure with linear regressions,” *Journal of Financial Economics*, 2013), run on each economy’s own curve of zero-coupon yields (the yields on bonds that pay only at maturity):

1. the curve at maturities of 1 to 120 months, on the last trading day of each month, is summarized by five factors (its first five principal components: level, slope, curvature and two more);
2. a one-step-ahead forecasting model (a VAR(1)) on the factors gives their forecasts and forecast errors;
3. one-month excess returns on bonds of 6, 12, …, 120 months are regressed on a constant, the forecast errors and the lagged factors; the prices of risk come from those coefficients;
4. bond prices follow from the standard recursion twice — with the prices of risk (fitted yields) and without them (risk-neutral yields, what a bond would yield if investors demanded no extra compensation for risk).

The model is **re-estimated monthly**; each day’s values apply that month’s coefficients to the day’s curve. The **term premium is the observed yield minus the model’s risk-neutral yield**, and the expected policy path is the risk-neutral yield, so the two pieces add up to the yield exactly. The 30-year is priced by the model beyond the 10-year range it is fit on. It is an Econvitals estimate, not the New York Fed’s or the Federal Reserve Board’s; the page shows those two published series beside it for the United States.

**Run it.** `python replicate.py` (keyless) rebuilds the United States, Germany, Japan and Canada in about a minute (the Board’s curve file alone is 16 MB); `python replicate.py us` does one. It writes `output/<cc>.csv`: daily yields, expected policy path and term premium at 2, 5, 10 and 30 years, in percent. To rebuild the numbers the site shows today, each economy is fit on the same months as the site’s current fit — the sample is read from the decomposer’s published index file. `output/site_<cc>.csv` holds the published values laid out flat, for the nightly comparison.

**Data.**

| economy | curve | from |
|:---:|:---:|:---:|
| United States | Federal Reserve Board, Gürkaynak–Sack–Wright zero curve from its daily Svensson parameters ([feds200628.csv](https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv)); the Board updates it weekly, so the days after its last row come from Treasury’s [daily par yield curve](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve), bootstrapped to zero-coupon yields and shifted maturity by maturity by the average gap to the Board’s curve over their last 20 common days | June 1961 |
| Germany (the euro-area model) | Bundesbank, Svensson parameters of the term structure of listed Federal securities (statistics API, `BBSIS/D.I.ZST.{B0…T2}.EUR.S1311.B.A604._Z.R.A.A._Z._Z.A`) | August 1997 |
| Japan | Ministry of Finance JGB par yield curve ([jgbcme_all.csv](https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv) and the current month’s file), bootstrapped to zero-coupon yields with annual coupons, flat below one year | January 1990 |
| Canada | Bank of Canada zero-coupon curve (quarter-year maturities, one CSV since 1986); its two-week lag is filled from the Bank’s daily benchmark bond and bill yields (Valet), joined the same way as the U.S. tail | January 1986 |

**How close.** Germany and Japan reproduce the published values exactly: every difference over the last year is within the site’s rounding to three decimals (the check allows 0.001 percentage point). The United States and Canada are within about 0.001 pp, and the check allows 0.003 pp. The cause is understood: the site re-estimates on the first run of each month, and for the U.S. and Canada the last month of that sample is a day filled from the same-day par curve, joined to the official curve as it stood that evening. This script fits on the same months, but it fills that day from the official curve as it stands now — and once the official file covers the day itself, from the official number. A few hundredths of a point on one of 786 months (490 for Canada) moves the premium by up to about 0.002 pp (tested: shifting that one month by 3 basis points moves the 10-year premium by 0.0017 pp). The comparison covers the official curve’s days only; the filled days after it are rebuilt by the site every evening, and the two runs can see different weeks of the official file.

**What is not rebuilt here.**

- **The United Kingdom’s fit** (on the Bank of England’s nominal spot curve, published as a bundle of zipped spreadsheets). The method is identical; it needs only a reader for those workbooks.
- **France, Italy and the euro area** carry Germany’s model plus their spread over Germany as a separate piece, never a fit of their own; their path and premium are Germany’s, rebuilt above.
- **Layer 4** for the United States (expected real rate, real term premium, expected inflation and inflation risk premium), which adds the Board’s TIPS curve, a CPI forecast on the model’s factors and the Philadelphia Fed’s Survey of Professional Forecasters.
- **The site’s check against the New York Fed’s published series** (a 0.996 correlation of daily changes over the last ten years, about 0.2 pp lower in level), which the site runs before every publish.
