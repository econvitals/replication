"""Real Wage Growth — rebuilds the two real-wage charts on econvitals.org/labor/#wages.

    python replicate.py        # needs FRED_API_KEY; writes output/real_ahe.csv and output/real_atlanta.csv
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, save  # noqa: E402

# Consumer price index, all items, seasonally adjusted (BLS series CUSR0000SA0).
cpi = fred("CPIAUCSL")

# 1. Real average hourly earnings, all private employees (BLS series CES0500000003).
ahe = fred("CES0500000003")
real = (ahe / cpi).dropna()
real = real.asfreq("MS")        # keeps a month with no CPI (October 2025) as a blank
real_ahe = (100 * ((real / real.shift(1)) ** 12 - 1)).to_frame("change")
real_ahe["avg3m"] = 100 * ((real / real.shift(3)) ** 4 - 1)
save(real_ahe.dropna(how="all"), HERE, "real_ahe")

# 2. The Atlanta Fed Wage Growth Tracker (3-month average of the 12-month change, overall),
#    deflated by the CPI put on the same basis: its 12-month change, averaged over 3 months.
wgt = fred("FRBATLWGT3MMAUMHWGO")
cpi_m = cpi.asfreq("MS")
cpi_basis = (100 * (cpi_m / cpi_m.shift(12) - 1)).rolling(3).mean()
real_wgt = (100 * ((1 + wgt / 100) / (1 + cpi_basis / 100) - 1)).dropna().to_frame("value")
save(real_wgt, HERE, "real_atlanta")
print(real_ahe.tail(3).round(3).to_string(), "\n", real_wgt.tail(3).round(3).to_string())
