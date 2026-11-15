# Replication package: “How Far Could Stocks Fall?”

This package rebuilds the numbers, tables and figures in “How Far Could Stocks Fall?,” an Occasional Post by Jason Furman on Econvitals (November 15, 2026), the second part of the series “The AI Boom and Its Risks.” It ends by checking each rebuilt number against the post.

**On econvitals.org:** [“How Far Could Stocks Fall?”](https://econvitals.org/posts/2026-11-15-how-far-could-stocks-fall/), one of Jason’s Occasional Posts. Part 1, [“The AI Boom’s Two Engines”](https://econvitals.org/posts/2026-11-09-ai-boom-two-engines/), has its own package in [`../2026-11-09-ai-boom-two-engines/`](../2026-11-09-ai-boom-two-engines/).

## This package is partial

Much of the post rests on licensed data or on data from websites whose terms do not allow it to be passed on: analysts’ expected earnings (FactSet; I/B/E/S, via the Federal Reserve Board; Yardeni Research), stock and option prices (S&P Dow Jones Indices, Cboe, Nasdaq), Goldman Sachs research and two financial websites. None of that is included. What is included:

* **All the code** for every number, table and figure in the post that comes from data.
* **The public data** it uses, frozen as used: Ken French’s daily stock market returns, Robert Shiller’s monthly stock market data, the Bureau of Economic Analysis’ GDP and corporate profits, the 10-year TIPS yield, the Federal Reserve Bank of Minneapolis’ option-implied probabilities, the Federal Reserve’s household wealth accounts (Z.1) and figures from companies’ SEC filings. Sources: [`data/SOURCES.md`](data/SOURCES.md).
* **A description of each licensed input** — what it is, where to get it and the exact file the code expects — in [`licensed/README.md`](licensed/README.md).

**How close.** On the public data alone, `python run_all.py` rebuilds 60 of the post’s 155 numbers and ends `verify: 60 PASS, 0 FAIL, 95 SKIPPED`. A reader who obtains the licensed inputs and puts them in `licensed/` can rebuild the rest; with the inputs used for the post, all 155 pass (November 15, 2026).

**Keys.** None. Nothing here uses the network.

## What is rebuilt from public data

| In the post | Rebuilt from |
|:---:|:---:|
| Figure 2, the Shiller ratio (40 today, the 99th percentile since 1881, the 1999–2000 peak of 44, the average since 1979 of 23.6) | Shiller’s monthly data, plus the November 13 reading of 39.95 (multpl.com), a single cited number |
| Table 2 and Table 3, the Shiller rows (−41, −47, −58 percent) | the same |
| Table 3, the excess-growth rows and what actually happened, 1996 and 2000 (−36, −57, −3, −51 percent; the December 16, 1996 low; October 9, 2002) | Ken French’s daily market returns, Shiller’s dividend yields, nominal GDP |
| Figure 3, profits as a share of GDP (7.9 percent in 1997, 6.0 at the 2000 peak, a record 11.9 now) | BEA via FRED |
| The 10-year TIPS yield (below 1 percent before COVID, above 2 percent for six months) | FRED |
| Nominal GDP growth of 6.2 percent a year since 2019; stock prices up roughly 7 percent a year over the long run | BEA via FRED; Shiller |
| Figure 4, the option-implied chance of a 20 percent fall (8.5 percent, lower than in 86 percent of weeks, 13 percent on average, below average in October 2007, February 2020 and February 2025) | Minneapolis Fed |
| Nvidia’s revenue more than ninefold in three years, Alphabet’s and Microsoft’s about 60 percent | SEC filings (XBRL) |
| A 25 percent fall wiping out about $19 trillion of household stock | Federal Reserve, Z.1 |
| The 18 percent expected return in the technology-explosion example | arithmetic |

Everything else — Figure 1, Table 1, Table 4, the forward-ratio and AI-company rows of Tables 2 and 3, the whole market’s move since September 30, Tesla, software stocks and the S&P 500’s record — needs a licensed input and is skipped without it.

## What the post does

The post asks how far U.S. stocks could fall if the AI boom turns out to be a bubble. Its yardsticks, each measured from the close on November 13, 2026:

1. **The AI companies alone.** Nvidia, Microsoft, Alphabet, Amazon, Meta, Broadcom and Oracle fall by half, the rest of the market unchanged. They were about 22 percent of the whole market, so the market falls 11 percent.
2. **The forward price-earnings ratio** (price over analysts’ expected earnings for the next 12 months) returns to its average since 1979: from 18.3 to 15.0, a fall of 18 percent; with expected earnings also 20 percent lower, 34 percent.
3. **The Shiller ratio** (price over ten years of inflation-adjusted earnings) returns to its average since 1979: from 40.0 to 23.6, a fall of 41 percent.
4. **The excess growth over nominal GDP is reversed.** The whole market falls back to where it would be had it grown with nominal GDP since the end of 2019: 34 percent.

“The whole market” is all NYSE, AMEX and Nasdaq stocks: Ken French’s daily value-weighted return, with the S&P 500’s dividend yield taken out day by day so that it measures prices alone, extended from October 1, 2026 with the Vanguard Total Stock Market ETF. The valuation ratios are the S&P 500’s, applied to the whole market.

Table 3 runs the same yardsticks on December 5, 1996 (“irrational exuberance”) and March 24, 2000 (the dot-com peak) and sets them beside what happened next. For those dates, “the excess growth” is measured over the same span as today’s case: the 6¾ years from the end of 2019 to the S&P 500’s record on October 6, 2026, so it starts in March 1990 and June 1993.

Table 4 turns the prices of S&P 500 put options expiring December 17, 2027 into risk-neutral probabilities of declines (the slope of put prices across strikes, times e^rT, at a 4 percent interest rate), beside how often the S&P 500 has been that far down 13 months later since 1946.

## What is in the package

```
run_all.py               one entry point: numbers, figures, then verify.py
verify.py                checks every rebuilt number against the post (expected.csv)
expected.csv             155 numbers from the post's text, tables and figures, each with its sentence or cell,
                         and the licensed file it needs, if any
howfar/numbers.py        every calculation; writes output/numbers.json (and output/skipped.json)
howfar/figures.py        Figures 1-4, plain matplotlib (not the post's house style); Figure 1 needs licensed data
howfar/common.py         paths, loaders and the two fixed inputs (the evaluation date and the Shiller ratio on it)
data/                    public data, as used; data/SOURCES.md documents each file
licensed/README.md       the licensed inputs: what, where from, and the file format the code expects
refresh/fetch_public.py  optional: re-download the public data into data_refreshed/ (never run by default)
requirements.txt         exact package versions (Python 3.14)
```

## How to run it

Python 3.14 (tested with 3.14.8 on macOS, Apple silicon); matplotlib is the only package needed, for the figures.

```
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run_all.py
```

It takes a few seconds. `python run_all.py --no-figures` skips the figures. Each step also runs alone: `python -m howfar.numbers`, `python -m howfar.figures`, `python verify.py`.

To rebuild the rest, put the licensed files described in `licensed/README.md` in `licensed/` and run it again; the rows that were skipped are then checked.

## How verify.py decides

`expected.csv` was typed from the post, never from the rebuilt output. A number passes when it rounds to what the post prints (half a unit of the last printed digit, plus 0.0005 for table cells and chart labels). Approximate statements carry an explicit range, written in the row’s note: “about 135 percent” is 132.5 to 137.5, “the 99th percentile” is above 98 and up to 99 percent of months, “more than ninefold” is at least 9.

## Notes on particular numbers

* **The Shiller ratio on November 13 (39.95)** is multpl.com’s daily reading, which extends Shiller’s monthly series with S&P’s latest prices and earnings. It is the one number from that site used here, cited in `howfar/common.py`. Shiller’s own monthly data run to October 2026, and they give the same averages as the post (23.6 since 1979; 14.8 and 18.1 up to the two earlier dates).
* **Tesla, “unless it falls about 96 percent or more.”** On market value — the post’s comparison is Tesla’s market value against Ford’s and General Motors’ in April 2017 — the fall that would take Tesla back to its value at the close on April 10, 2017 is 96.7 percent; on the share price alone, ignoring the shares issued since, it is 94.7 percent. `verify.py` accepts 95.5 to 97.
* **Table 3, December 5, 1996, forward ratio 15.9.** The post uses 15.9 for that date; the monthly forward-ratio series reads 15.97 for both November and December 1996, and the source of 15.9 was not recorded. With 15.97 the 1996 forward-ratio fall is 32 percent rather than 31 (`t3_fwd_1996_monthly` in `output/numbers.json`); the forward-plus-earnings fall is 45 percent either way.
* **Facts cited, not rebuilt:** Tesla’s 2016 deliveries (about 76,000; Tesla), Ford’s and General Motors’ 2016 sales (about 7 million and 10 million), the share of fiber lit in the early 2000s, the rise in the rental price of an Nvidia H100, The Economist’s estimate of AI developers’ revenue growth, and the S&P 500’s earnings growth since 2019 (about 125 percent: Shiller’s as-reported earnings through June 2026 plus FactSet’s third-quarter growth). Each is linked or sourced in the post.

## License

Code: MIT (see `LICENSE`). Data: each file keeps its publisher’s terms (`data/SOURCES.md`).
