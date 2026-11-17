"""Question 1: has the MPC out of wealth changed over time?

    python 02_rolling.py <out dir>

Two estimators, each run over fixed periods and over rolling windows:
  LEVELS   PCE/income on start-of-quarter wealth/income by type + controls (long-run relationship)
  CHANGES  quarterly change in spending on current and lagged real holding gains (short-run response),
           cumulated over 4 and 8 quarters
Writes q1_periods.csv, q1_rolling.csv, q1_breaks.csv and fig01-fig04.
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *

OUT = Path(sys.argv[1])
d = load(OUT)
x = add_basics(d)
START, END = "1955Q1", str(x["cy"].last_valid_index())
print("sample", START, END)

# ---- fixed periods -----------------------------------------------------------------------------
periods = [("1955Q1", "2019Q4"), ("1955Q1", END), ("1955Q1", "1979Q4"), ("1980Q1", "1999Q4"),
           ("2000Q1", "2019Q4"), ("2000Q1", END), ("1955Q1", "1989Q4"), ("1990Q1", "2019Q4"), ("1990Q1", END)]
rows = []
for a, b in periods:
    for label, kw in [("levels", {}), ("levels, no controls", {"ctl": []}), ("levels, leads and lags", {"dols": 2}),
                      ("levels, total net worth", {"wealth": ["nwy"]})]:
        m = levels_fit(x, a, b, **kw)
        for k in kw.get("wealth", WEALTH3):
            rows.append(dict(start=a, end=b, spec=label, asset=k, horizon="long run", coef=100 * m.params[k],
                             se=100 * m.bse[k], n=int(m.nobs), r2=m.rsquared))
    m = dl_fit(x, a, b, J=8)
    for k in ["gS", "gH", "gO"]:
        for h in [0, 1, 2, 4, 8]:
            est, se = cum(m, k, h)
            rows.append(dict(start=a, end=b, spec="changes", asset=k, horizon=f"{h}q", coef=100 * est, se=100 * se,
                             n=int(m.nobs), r2=m.rsquared))
    m = dl_fit(x, a, b, J=8, kinds=("gNW",))
    for h in [0, 1, 2, 4, 8]:
        est, se = cum(m, "gNW", h)
        rows.append(dict(start=a, end=b, spec="changes, total net worth", asset="gNW", horizon=f"{h}q", coef=100 * est,
                         se=100 * se, n=int(m.nobs), r2=m.rsquared))
# robustness: is the post-2019 decline the pandemic years or the recent boom? Drop 2020Q1-2022Q4 entirely.
drop = pd.period_range("2020Q1", "2022Q4", freq="Q")
LASTWIN = str(pd.Period(END, "Q") - 79)          # first quarter of the latest 20-year window
for a in ["1955Q1", "1990Q1", "2000Q1", LASTWIN]:
    X = x[WEALTH3 + CTL].copy()
    for q in drop:
        X[f"X{q}"] = (x.index == q).astype(float)
    m = ols(x["cy"].loc[a:END], X.loc[a:END], lags=8)
    for k in WEALTH3:
        rows.append(dict(start=a, end=END, spec="levels, 2020–2022 dropped", asset=k, horizon="long run", coef=100 * m.params[k],
                         se=100 * m.bse[k], n=int(m.nobs) - len(drop), r2=m.rsquared))
    X = dl_design(x, J=8)
    for q in drop:
        X[f"X{q}"] = (x.index == q).astype(float)
    m = ols(x["dc"].loc[a:END], X.loc[a:END], lags=4)
    for k in ["gS", "gH", "gO"]:
        for h in [0, 1, 2, 4, 8]:
            est, se = cum(m, k, h)
            rows.append(dict(start=a, end=END, spec="changes, 2020–2022 dropped", asset=k, horizon=f"{h}q", coef=100 * est, se=100 * se,
                             n=int(m.nobs) - len(drop), r2=m.rsquared))
# direct test: do gains since 2023 pass through to spending at the old rate? Separate stock-gain coefficients
# for spending quarters 2023Q1 onward, with 2020Q1-2022Q4 dropped.
late = (x.index >= pd.Period("2023Q1", "Q")).astype(float)
for a in ["1955Q1", "1990Q1"]:
    X = dl_design(x, J=4)
    for q in drop:
        X[f"X{q}"] = (x.index == q).astype(float)
    X["late"] = late
    for j in range(5):
        X[f"gSlate_{j}"] = X[f"gS_{j}"] * late
    m = ols(x["dc"].loc[a:END], X.loc[a:END], lags=4)
    for h in [1, 2, 4]:
        base = lincom(m, [f"gS_{j}" for j in range(h + 1)])
        extra = lincom(m, [f"gSlate_{j}" for j in range(h + 1)])
        tot = lincom(m, [f"gS_{j}" for j in range(h + 1)] + [f"gSlate_{j}" for j in range(h + 1)])
        rows.append(dict(start=a, end=END, spec="changes, before 2020", asset="gS", horizon=f"{h}q", coef=100 * base[0], se=100 * base[1], n=int(m.nobs) - len(drop), r2=m.rsquared))
        rows.append(dict(start=a, end=END, spec="changes, 2023 on", asset="gS", horizon=f"{h}q", coef=100 * tot[0], se=100 * tot[1], n=int(late[x.index <= pd.Period(END, "Q")].sum()), r2=m.rsquared))
        rows.append(dict(start=a, end=END, spec="changes, 2023 on minus before", asset="gS", horizon=f"{h}q", coef=100 * extra[0], se=100 * extra[1], n=int(m.nobs) - len(drop), r2=m.rsquared))
# a short specification (4 lags of stock and housing gains, income lags 0-2) that can be estimated on short eras
for a, b in [("1955Q1", "1989Q4"), ("1990Q1", "2008Q4"), ("2009Q1", "2019Q4"), ("2021Q3", END), ("1955Q1", "2019Q4"), ("1955Q1", END)]:
    X = dl_design(x, J=4, kinds=("gS", "gH"), ylags=2, extra=False)
    if b >= "2020Q1" and a < "2020Q1":
        X[DUMS] = x[DUMS]
    m = ols(x["dc"].loc[a:b], X.loc[a:b], lags=4)
    for k in ["gS", "gH"]:
        for h in [1, 2, 4]:
            est, se = cum(m, k, h)
            rows.append(dict(start=a, end=b, spec="changes, short specification", asset=k, horizon=f"{h}q", coef=100 * est, se=100 * se,
                             n=int(m.nobs), r2=m.rsquared))
# the long-run regression on the decade between the financial crisis and the pandemic, on its own
m = levels_fit(x, "2009Q1", "2019Q4")
for k in WEALTH3:
    rows.append(dict(start="2009Q1", end="2019Q4", spec="levels", asset=k, horizon="long run", coef=100 * m.params[k], se=100 * m.bse[k], n=int(m.nobs), r2=m.rsquared))
per = pd.DataFrame(rows)
per.to_csv(OUT / "q1_periods.csv", index=False)
show = per[(per.spec.isin(["levels", "changes"])) & (per.horizon.isin(["long run", "4q", "8q"]))]
print(show.pivot_table(index=["start", "end"], columns=["spec", "asset", "horizon"], values="coef").round(2).to_string())
print(per[per.spec.str.contains("short spec")].round(2).to_string())

# ---- expanding sample: start fixed at 1955Q1, end moved forward a year at a time --------------------
rows = []
for b in ["1999Q4", "2007Q4", "2012Q4", "2016Q4", "2019Q4", "2021Q4", "2022Q4", "2023Q4", "2024Q4", "2025Q4", END]:
    m = levels_fit(x, "1955Q1", b)
    r_ = dict(end=b, n=int(m.nobs))
    for k in WEALTH3:
        r_[k], r_[k + "_se"] = 100 * m.params[k], 100 * m.bse[k]
    m = levels_fit(x, "1955Q1", b, wealth=["nwy"])
    r_["nwy"], r_["nwy_se"] = 100 * m.params["nwy"], 100 * m.bse["nwy"]
    rows.append(r_)
expand = pd.DataFrame(rows)
expand.to_csv(OUT / "q1_expanding.csv", index=False)
print(expand.round(2).to_string())

# ---- rolling windows ---------------------------------------------------------------------------
rows = []
ends = x.loc["1955Q1":END].index
for W in [60, 80, 120]:
    for i in range(W - 1, len(ends)):
        a, b = ends[i - W + 1], ends[i]
        m = levels_fit(x, a, b)
        for k in WEALTH3:
            rows.append(dict(window=W, end=str(b), spec="levels", asset=k, coef=100 * m.params[k], se=100 * m.bse[k]))
        m = levels_fit(x, a, b, wealth=["nwy"])
        rows.append(dict(window=W, end=str(b), spec="levels", asset="nwy", coef=100 * m.params["nwy"], se=100 * m.bse["nwy"]))
        m = dl_fit(x, a, b, J=8)
        for k in ["gS", "gH"]:
            for h in [1, 4, 8]:
                est, se = cum(m, k, h)
                rows.append(dict(window=W, end=str(b), spec=f"changes {h}q", asset=k, coef=100 * est, se=100 * se))
roll = pd.DataFrame(rows)
roll.to_csv(OUT / "q1_rolling.csv", index=False)

# ---- break tests: one unknown break in the stock or housing coefficient -------------------------
def supwald(kind, trim, end):
    """Largest Wald statistic, over candidate break dates, for a change in one wealth coefficient.
    EVERY coefficient is allowed to change at the break (a regression that holds the other coefficients
    fixed manufactured a break in the changes model that separate regressions do not show). `trim` is the
    share of the sample excluded at each end, so it also sets the latest date the test can pick."""
    idx = x.loc[START:end].index
    lo, hi = int(trim * len(idx)), int((1 - trim) * len(idx))
    dums = DUMS if end >= "2020Q1" else []
    best = dict(w=0)
    for t in range(lo, hi):
        tau = idx[t]
        post = pd.Series((x.index >= tau).astype(float), index=x.index)
        if kind[0] == "levels":
            k = kind[1]
            base = x[WEALTH3 + CTL]
            X = pd.concat([base, base.mul(post, axis=0).add_suffix("_post"), post.rename("post"), x[dums]], axis=1)
            m = ols(x["cy"].loc[START:end], X.loc[START:end], lags=8)
            before, shift, se = m.params[k], m.params[f"{k}_post"], m.bse[f"{k}_post"]
        else:
            k, h = kind[1], kind[2]
            base = dl_design(x, J=4, kinds=("gS", "gH"), ylags=2, extra=False)
            X = pd.concat([base, base.mul(post, axis=0).add_suffix("_post"), post.rename("post"), x[dums]], axis=1)
            m = ols(x["dc"].loc[START:end], X.loc[START:end], lags=4)
            shift, se = lincom(m, [f"{k}_{j}_post" for j in range(h + 1)])
            before = cum(m, k, h)[0]
        wstat = (shift / se) ** 2
        if wstat > best["w"]:
            best = dict(w=wstat, tau=str(tau), before=100 * before, after=100 * (before + shift))
    best["first"], best["last"] = str(idx[lo]), str(idx[hi - 1])
    return best

# Andrews (1993) critical values as corrected in Andrews (2003), one restriction: 10 / 5 / 1 percent
CV = {0.10: (7.58, 9.11, 12.59), 0.15: (7.12, 8.68, 12.16), 0.20: (6.73, 8.28, 11.71)}
brows = []
for kind, trim, end, label in [(("levels", "Sy"), 0.10, END, "full sample"), (("levels", "Hy"), 0.10, END, "full sample"),
                               (("levels", "Sy"), 0.20, END, "full sample, 20% trimming"), (("levels", "Hy"), 0.20, END, "full sample, 20% trimming"),
                               (("levels", "Sy"), 0.15, "2019Q4", "through 2019"), (("levels", "Hy"), 0.15, "2019Q4", "through 2019"),
                               (("changes", "gS", 4), 0.20, END, "full sample"), (("changes", "gH", 4), 0.20, END, "full sample")]:
    b_ = supwald(kind, trim, end)
    brows.append(dict(test=" ".join(map(str, kind)), sample=label, trim=trim, first_candidate=b_["first"], last_candidate=b_["last"],
                      sup_wald=b_["w"], break_date=b_["tau"], coef_before=b_["before"], coef_after=b_["after"],
                      cv10=CV[trim][0], cv5=CV[trim][1], cv1=CV[trim][2]))
    print(brows[-1])
pd.DataFrame(brows).to_csv(OUT / "q1_breaks.csv", index=False)

# ---- charts ------------------------------------------------------------------------------------
t = qdates(d.loc["1952Q1":].index)
fig, ax = plt.subplots(figsize=(8, 5))
s = d.loc["1952Q1":]
for k, lab, col in [("S", "Stocks (direct and indirect)", "primary"), ("H", "Owner-occupied housing", "secondary"),
                    ("O", "Everything else, net of all debt", "gray")]:
    ax.plot(t, s[k] / s["dpi"], color=C[col], lw=1.8, label=lab)
ax.legend(loc="upper left", fontsize=9)
ax.set_ylim(0, None)
finish(fig, ax, "Household Wealth by Type", "Years of disposable personal income", OUT / "fig01_wealth_by_type.png",
       note=f"Note: End of quarter, through {d['S'].last_valid_index()}. Households and nonprofit organizations.")

def roll_chart(asset_l, asset_c, title, path, ylim):
    fig, ax = plt.subplots(figsize=(8, 5))
    r = roll[roll.window == 80]
    for spec, asset, lab, col in [("levels", asset_l, "Long-run relationship (levels)", "primary"),
                                  ("changes 4q", asset_c, "Response to gains within four quarters (changes)", "secondary")]:
        q = r[(r.spec == spec) & (r.asset == asset)]
        tt = qdates(pd.PeriodIndex(q.end, freq="Q"))
        ax.plot(tt, q.coef, color=C[col], lw=1.8, label=lab)
        ax.fill_between(tt, q.coef - 1.645 * q.se, q.coef + 1.645 * q.se, color=C[col], alpha=0.15, lw=0)
    ax.axhline(0, color=C["ink"], lw=0.8)
    ax.set_ylim(*ylim)
    ax.legend(loc="upper left", fontsize=9)
    finish(fig, ax, title, "Cents of annual spending per dollar of wealth; 20-year windows, dated by the last quarter", path,
           note="Note: Shaded bands are 90 percent confidence intervals. Windows that include 2020Q1–2021Q2 carry a dummy for each of those quarters.")

roll_chart("Sy", "gS", "Rolling Estimates of the Spending Response to Stock Wealth", OUT / "fig02_rolling_stocks.png", (-6, 10))
roll_chart("Hy", "gH", "Rolling Estimates of the Spending Response to Housing Wealth", OUT / "fig03_rolling_housing.png", (-15, 25))

fig, ax = plt.subplots(figsize=(8, 5))
for W, col in [(60, "gold"), (80, "primary"), (120, "burgundy")]:
    q = roll[(roll.window == W) & (roll.spec == "levels") & (roll.asset == "nwy")]
    ax.plot(qdates(pd.PeriodIndex(q.end, freq="Q")), q.coef, color=C[col], lw=1.8, label=f"{W // 4}-year windows")
ax.axhline(0, color=C["ink"], lw=0.8)
ax.legend(loc="upper right", fontsize=9)
finish(fig, ax, "Rolling Estimates of the Spending Response to Total Net Worth",
       "Cents of annual spending per dollar of net worth; levels regression, dated by the last quarter of the window",
       OUT / "fig04_rolling_networth.png")
print("done")
