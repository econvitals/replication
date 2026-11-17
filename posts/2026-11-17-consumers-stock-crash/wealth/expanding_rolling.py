"""The stock-wealth coefficient estimated from 1955 through each quarter (expanding) and over the 20 years ending in
each quarter (rolling), with and without 2020-2021: the post's Figure 6 and the appendix's “dropping 2020-2021”
numbers. Run from the package folder after build_panel.py.
Writes output/part3_r10_expanding.csv and output/part3_r11_rolling20.csv."""
import sys
sys.path.insert(0, "wealth")
from common import *
import warnings; warnings.filterwarnings("ignore")
d = load(Path("output")); x = add_basics(d); END = str(x["cy"].last_valid_index())
DROP = pd.period_range("2020Q1", "2021Q4", freq="Q")


def fit_pair(a, b):
    m = levels_fit(x, str(a), str(b))
    r = dict(S=100 * m.params["Sy"], Sse=100 * m.bse["Sy"])
    if pd.Period(b, "Q") >= pd.Period("2022Q1", "Q"):
        y = x["cy"].loc[str(a):str(b)]; X = x[WEALTH3 + CTL].loc[str(a):str(b)]
        keep = ~y.index.isin(DROP); mm = ols(y[keep], X[keep], lags=8)
        r.update(Sx=100 * mm.params["Sy"], Sxse=100 * mm.bse["Sy"])
    return r


rows = [dict(end=str(b), **fit_pair("1955Q1", b)) for b in pd.period_range("1985Q1", END, freq="Q")]
pd.DataFrame(rows).set_index("end").to_csv("output/part3_r10_expanding.csv")
rows = [dict(end=str(b), start=str(b - 79), **fit_pair(b - 79, b)) for b in pd.period_range("1995Q1", END, freq="Q")]
pd.DataFrame(rows).set_index("end").to_csv("output/part3_r11_rolling20.csv")
print("expanding and rolling 20-year estimates written")
