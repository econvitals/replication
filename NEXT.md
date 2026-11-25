# NEXT

## Next
- term-premium, Canada: stop the monthly red. The site fits on a sample ending on a day it FILLED from Valet benchmark yields (2026-10-30 this month); once the Bank of Canada's zero-coupon file covers that day (~3 weeks later), `measures/term-premium/replicate.py` refits on the official number instead and Canada's path/premium drift up to 0.012 pp (2026-11-20 onward; 0.005 allowed). Widening the tolerance was already done once (55800ff) — don't do it again. Fix: have the site record the fit-end day's filled curve in its published index (`tools/interest-rate-decomposer` meta, beside `model_sample`) and have replicate.py fit on that row; done = `tools/check_all.py` shows term-premium MATCHES in the weeks after the BoC file passes the fit-end day.
