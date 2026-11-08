# Market-Implied Expectations

**On econvitals.org:** [What Forecasters Expect](https://econvitals.org/tools/forecasts/) (the market tiles, the Next releases table, the charts and the Markets column), the Kalshi market card on [Home › GDP](https://econvitals.org/#gdp) and [GDP](https://econvitals.org/gdp/#gdp), the Kalshi tile and line on [GDP Trackers](https://econvitals.org/tools/gdp-trackers/), and [Financial › Prediction Markets](https://econvitals.org/financial/#predictions) (Macro forecasts). Method note: [Methods](https://econvitals.org/methods/#market-implied-expectations).

**What it is.** Kalshi lists each economic release as a ladder of yes/no markets (“real GDP growth above 2.5%”, “above 3.0%” …) or as a set of ranges. The prices across the ladder are a probability distribution over the print, and the number shown is its mean, computed by Econvitals’ own rules:

- each market is priced at the **midpoint of its bid and ask** when the two are within 10 cents of each other, and otherwise at its **last trade**;
- a ladder whose rungs are out of order is forced back into order by **pooling neighboring rungs**; in the daily history, one out of order by more than 15 cents is discarded as not a distribution at all;
- the probability between two rungs is placed at the **midpoint of the prints it covers**. Kalshi settles on a print rounded to one decimal (or to the nearest thousand jobs) and pays on a print strictly greater than the strike, so “above 2.0%” less “above 2.5%” is spread over 2.1 to 2.5. The two open tails sit half a rung beyond the end strikes;
- a ladder with **no rung between 10% and 90%** that has a two-sided book within 10 cents is treated as having no view, and no number is shown;
- the **daily history** uses only firm prices (a trade, or a book within 10 cents, at that day’s close), carrying a rung’s last firm price forward for up to seven days; a day counts only when some rung between 10% and 90% was firm that day. The **one-week change** is today’s mean less the history’s point on or before seven days earlier.

It is a market reading, not an Econvitals forecast: prices at which people are willing to bet, as of the minute they were read. Thin markets move it — a one-cent change on one rung can move the second decimal, and the tail rule alone moves a GDP mean by a few hundredths.

**Run it.** `python replicate.py`. No key: Kalshi’s public market data needs no account, and nothing here can place an order. Downloads are cached for six hours like everything else in this repository; `ECONVITALS_CACHE_HOURS=0 python replicate.py` forces a fresh read of the order books. It covers the six cards the site shows: real GDP growth for the next quarter BEA has not yet published (Kalshi series `KXGDP`) and for this calendar year (`KXGDPYEAR`), the next CPI and core CPI monthly changes (`KXCPI`, `KXCPICORE`), the unemployment rate (`KXU3`) and the monthly change in payrolls (`KXPAYROLLS`). It writes:

- `output/expected.csv` — each market’s expected print right now, the one-week change and the time it was read;
- `output/distribution.csv` — the probability on each possible print;
- `output/path_<id>.csv` — the daily history (120 days), ending with today’s live reading;
- `output/check_history.csv` and `output/site_history.csv` — for the nightly check (below).

**Data.** Kalshi’s public REST API, `https://api.elections.kalshi.com/trade-api/v2`: `events` (which event is next), `markets` (each rung’s strike, bid, ask and last trade) and `series/<series>/markets/<ticker>/candlesticks` (daily candles: the closing bid, ask and trade, and the day’s volume).

**How close, and why the check works this way.** A live order book cannot be fetched again later, so tomorrow’s run cannot see the prices behind today’s published number. What Kalshi does keep is every market’s daily closing candle. The nightly check therefore takes each card on the published site (`data/predictions-macro.json`), the event it names and the time it was built, rebuilds that card’s daily history from the candles over the same window (120 days for the quarter’s GDP, 45 for the rest), and compares every closed day. On November 8, 2026 all 239 card-days matched exactly; the check allows 0.0001, one unit of the fourth decimal the site publishes. The newest point on each card is the live book at the minute the site was built and is not compared.

**Three pages, one market.** The home page, GDP Trackers and What Forecasters Expect all read the GDP card from the same published file, so they agree; the other cards on What Forecasters Expect are priced on that page’s own schedule, so a value there can differ slightly from the Financial page’s at the same moment. The time printed beside each is the reconciliation.

**No track record yet.** Econvitals does not keep a published history of the market’s expectation for releases that have already happened: each card carries the daily history for the print it is waiting on, and is replaced when that print comes out. So there is no file of past market expectations to download here.
