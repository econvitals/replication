# Licensed inputs (not included)

The S&P 500 index is licensed data, so it is not in this package. Three numbers in the post rest on it and are skipped
without it: the correlation below, the market’s rise of “nearly 40 percent” in 1987 before the crash (the whole market
from public data rose 35 percent from the end of 1986 to its August peak, computed as a check) and the S&P 500’s falls
of “just under 20 percent” marked in Figure 1. Put the file here under the name given to rebuild the correlation; the
other two are recorded from the S&P 500 and not recomputed.

| File | What the code expects | Where the post’s came from | Used for |
|:---:|:---:|:---:|:---:|
| `sp500_daily.csv` | `date`, `close`: S&P 500 daily closes, 1975 to 2026 | S&P Dow Jones Indices (read from Yahoo Finance, ^GSPC, and FRED’s SP500 for the last ten years) | the correlation of yearly changes in real stock prices and real house prices since 1976 (0.16) |

The same correlation with the whole U.S. market from public data (Ken French’s file) is computed anyway, as a check, and
comes out at 0.15; it is not the number in the post. The S&P 500’s 20.5 percent fall on October 19, 1987 is a matter of
record and is listed in `expected.csv` as a quotation.

The files in this folder other than this README are ignored by git, so a reader’s licensed data cannot be committed by
accident.
