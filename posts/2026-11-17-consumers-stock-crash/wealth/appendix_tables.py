"""Rebuild every table in the online appendix (Tables A1-A20) from the outputs, exactly as the published page builds
them, and write their cells to output/appendix_tables.json for verify.py to compare with the published page
(expected_appendix_tables.csv). Run from the package folder after appendix_numbers.py. The literature (A1) and county
(A17) tables are typed from the papers and the county study, so they are carried over rather than rebuilt."""
import sys, json, re, html as H
from pathlib import Path
import pandas as pd

O = Path("output")
R = json.load(open(O / "r9_cf_results.json")); N = json.load(open(O / "a1_numbers.json"))
X = json.load(open(O / "r9_extras.json")); END = R["END"]
ser = pd.read_csv(O / "r9_series.csv", index_col=0)
POST_URL = "../"                     # the appendix sits at posts/<slug>/appendix/
MINUS = "−"

def f(v, d=1, plus=False):
    if v is None or (isinstance(v, float) and v != v): return "—"
    s = f"{v:,.{d}f}"
    if s.startswith("-"): s = MINUS + s[1:]
    if s in (MINUS + "0." + "0" * d, MINUS + "0"): s = s[1:]
    return ("+" + s) if plus and not s.startswith(MINUS) and v != 0 else s
def cse(v, se, d=2): return f'{f(v, d)}<br><span class="se">({f(se, d)})</span>'
def table(tid, title, head, rows, note=None, source=None, cls=""):
    """head: list of header rows (each a list of (text, colspan)); rows: list of lists of cell HTML."""
    out = [f'<div class="tblock" id="{tid}"><p class="tabletitle">{title}</p><div class="tw"><table class="{cls}">']
    out.append("<thead>")
    for hr in head:
        out.append("<tr>" + "".join(f'<th colspan="{c}">{t}</th>' if c > 1 else f"<th>{t}</th>" for t, c in hr) + "</tr>")
    out.append("</thead><tbody>")
    for r in rows:
        if isinstance(r, str): out.append(r); continue
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    if note: out.append(f'<p class="cap"><i>Note:</i> {note}</p>')
    if source: out.append(f'<p class="cap"><i>{"Sources" if ";" in source else "Source"}:</i> {source}</p>')
    out.append("</div>")
    return "\n".join(out)
def h(cols): return [[(c, 1) for c in cols]]
SRC = "BEA; Federal Reserve Board, Financial Accounts of the United States; author’s calculations."
T = {}

# ------------------------------------------------------------------ A1 literature (numbers from the papers)
lit = [
    ("Poterba (2000)", "Survey of the U.S. evidence", "About 3 in the long run (range 1–5); 1–2 in the first year", "—", "About 3"),
    ("Ludvigson and Steindel (1999)", "U.S. quarterly, 1953–1997", "4.0 (2.1–10.6 across subperiods)", "—", "4.6"),
    ("Davis and Palumbo (2001)", "U.S. quarterly, 1960–2000", "3.8–5.7", "—", "3–6"),
    ("Carroll, Otsuka and Slacalek (2011)", "U.S. quarterly, 1960–2007", "Financial: 0.8 in the first quarter, 4.1 eventually", "1.8 first quarter, 8.7 eventually", "0.9 first quarter, 4.8 eventually"),
    ("Fair (2017, 2024)", "U.S. quarterly, 1954–2023", "About 4 (financial wealth)", "About 5", "About 4"),
    ("Duca, Muellbauer and Murphy (2017)", "U.S. quarterly, 1972–2017, with credit conditions", "1.4 (illiquid financial)", "About 1 (1980s) to 3.75 (mid-2000s); below 2 (2015)", "—"),
    ("Aladangady and Feiveson (2018)", "U.S. quarterly, 1960–2007", "—", "—", "3.5"),
    ("Beach, Gamber and Moran (2025)", "U.S. quarterly, 1964–2011, tested through 2019", "Slightly above 1", "Just over 5", "3.5; with a break, 3.3 before 2012 and 2.7 after"),
    ("Slacalek (2009)", "16 countries, quarterly; U.S. 1965–2003", "5.3 (financial)", "7.0 (imprecise)", "5.4–6.0"),
    ("Calomiris, Longhofer and Miles (2013)", "U.S. states, annual, 1985–2009", "0–1.8", "5.5–8.1", "—"),
    ("Chodorow-Reich, Nenov and Simsek (2021)", "U.S. counties, quarterly; dividend data 1989–2015", "3.2", "—", "—"),
    ("Andersen, Johannesen and Sheridan (2024)", "Danish investors, 2009–2016", "About 4 in the first year (4.4 published)", "—", "—"),
    ("Di Maggio, Kermani and Majlesi (2020)", "Swedish households, 1999–2007", "2.8 (top 5 percent) to 23 (bottom half)", "—", "—"),
    ("Mian, Rao and Sufi (2013)", "U.S. counties, 2006–2009", "—", "5.4–7.2", "—"),
    ("Guren, McKay, Nakamura and Steinsson (2021)", "U.S. metropolitan areas, 1978–2017", "—", "2.4 (3.3 for 1990–2017)", "—"),
    ("This appendix: consumption function", "U.S. quarterly, 1955–2019", f"{f(R['main']['1955Q1-2019Q4']['Sy'])}", f"{f(R['main']['1955Q1-2019Q4']['Hy'])}",
     f"{f([s for s in R['sens'] if s['spec'].startswith('Total net worth')][0]['S_2019'])}"),
]
T["lit"] = table("tA1", "Table A1. Selected Estimates of How Much Spending Rises per Dollar of Wealth",
                 h(["Study", "Data", "Stock wealth", "Housing wealth", "Total wealth"]), [list(r) for r in lit],
                 note="Cents of annual consumer spending per dollar of wealth, long run unless stated. Studies define wealth, spending and "
                      "income differently, so the numbers are not strictly comparable. Fair’s 2024 re-estimate dummies out 2020–2021.",
                 source="The studies listed; author’s calculations for the last row.")

# ------------------------------------------------------------------ A2 variables
vars_ = [("C", "Personal consumption expenditures", "BEA, NIPA Table 2.1, nominal, seasonally adjusted annual rate"),
         ("Y", "Disposable personal income", "BEA, NIPA Table 2.1, nominal, seasonally adjusted annual rate"),
         ("S", "Stock wealth", "Corporate equities held directly and indirectly (through mutual funds and defined-contribution and "
                               "retirement accounts) by households and nonprofits; Financial Accounts Table B.101.e, series LM153064475"),
         ("H", "Housing wealth", "Owner-occupied real estate at market value, before subtracting mortgages; Table B.101, LM155035015"),
         ("O", "Other net wealth", "Net worth (FL152090005) minus S and H: deposits, bonds, noncorporate business, pension "
                                   "entitlements and the rest, net of all liabilities including mortgages"),
         ("TR", "Transfers", "Personal current transfer receipts (NIPA Table 2.1), as a share of Y"),
         ("U", "Unemployment rate", "BLS civilian unemployment rate, quarterly average"),
         ("r", "Real interest rate", "Three-month Treasury bill rate minus four-quarter PCE inflation"),
         ("G", "Income relative to its recent average", "100 × (log real disposable income per person minus its average over the previous eight quarters)")]
T["vars"] = table("tA2", "Table A2. Variables in the Consumption Function", h(["Symbol", "Variable", "Source and definition"]),
                  [[f"<i>{a}</i>", b, c] for a, b, c in vars_],
                  note="Wealth is measured at the end of the quarter and not seasonally adjusted; the regressions use the value at the end of "
                       "the previous quarter. The data run from 1951Q4; regressions start in 1955Q1.")

# ------------------------------------------------------------------ A3 regression in five samples
M = R["main"]; samp = ["1955Q1-2019Q4", "1955Q1-2026Q3", "1989Q1-2015Q4", "1990Q1-2019Q4", "2010Q1-2019Q4"]
labs = ["1955–2019", f"1955–{END[:4]}", "1989–2015", "1990–2019", "2010–2019"]
k0 = M[samp[0]]
def coef(m, k):
    v = m.get(k); se = m.get(k + "_se")
    return v, se
rows = []
for k, lab, sc in (("Sy", "Stock wealth / income (cents)", 1), ("Hy", "Housing wealth / income (cents)", 1), ("Oy", "Other net wealth / income (cents)", 1),
                   ("tr_share", "Transfers / income (points per point)", 1), ("unrate", "Unemployment rate (points per point)", 1),
                   ("rr", "Real bill rate (points per point)", 1), ("ygap", "Income relative to its two-year average (points per percent)", 1),
                   ("const", "Constant (percent of income)", 1)):
    sc_ = 0.01 if k == "tr_share" else 1
    rows.append([lab] + [cse(coef(M[s], k)[0] * sc_, coef(M[s], k)[1] * sc_, d=1 if k == "const" else 2) for s in samp])
def stat(k, d=3, fn=None): return [fn(M[s]) if fn else f(M[s][k], d) for s in samp]
rows.append(['<span class="rule"></span>Observations'] + [str(M[s]["n"]) for s in samp])
rows.append(["R² / adjusted R²"] + [f"{f(M[s]['r2'], 3)} / {f(M[s]['r2a'], 3)}" for s in samp])
rows.append(["Standard error of regression (points)"] + stat("se_reg", 2))
rows.append(["Durbin–Watson"] + stat("dw", 2))
rows.append(["ADF test on the residuals (p)"] + [f"{f(M[s]['adf'], 2)} ({f(M[s]['adf_p'], 3)})" for s in samp])
rows.append(["Engle–Granger statistic (p)"] + [f"{f(M[s]['eg'], 2)} ({f(M[s]['eg_p'], 3)})" for s in samp])
rows.append(["Engle–Granger 5 percent critical value"] + [f(M[s]["eg_crit5"], 2) for s in samp])
T["reg"] = table("tA3", "Table A3. The Consumption Function in Five Samples", h(["", *labs]), rows,
                 note="Dependent variable: consumer spending as a percent of disposable income. Newey–West standard errors (eight lags) in "
                      "parentheses. The 1955–2026 sample (through the third quarter of 2026) includes six dummies for 2020Q1–2021Q2, not shown. "
                      "Points are percentage points of the spending share. The Engle–Granger test regresses the spending share on the three "
                      "wealth ratios alone and tests the residual for a unit root (critical values from MacKinnon).",
                 source=SRC, cls="reg")

# ------------------------------------------------------------------ A4 speed of adjustment
def ecm_path(d, H_=12):
    bS, lam, phi, ds = d["bS"], d["lam"], d["phi"], d["dS_short"]
    c = [0.0, 0.0]; out = []
    for t in range(1, H_ + 1):
        tgt_lag = bS if t >= 2 else 0.0
        dc = -lam * (c[-1] - tgt_lag) + phi * (c[-1] - c[-2]) + (ds if t == 1 else 0.0)
        c.append(c[-1] + dc); out.append(c[-1] / bS * 100)
    return out
rows = []
for s, lab in (("1955Q1-2019Q4", "1955–2019"), ("1955Q1-2026Q3", f"1955–{END[:4]}")):
    d = R["dyn"][s]; ep = ecm_path(d); rho = d["pa_rho"]
    import math
    rows.append([lab, "Error correction", f"{f(d['lam'], 3)} ({f(d['lam_se'], 3)})", f(math.log(0.5) / math.log(1 - d["lam"]), 1),
                 *[f(ep[q - 1], 0) for q in (1, 4, 8, 12)], f(d["bS"], 2)])
    rows.append([lab, "Partial adjustment", f"{f(1 - rho, 3)} ({f(d['pa_rho_se'], 3)})", f(math.log(0.5) / math.log(rho), 1),
                 *[f(100 * (1 - rho ** q), 0) for q in (1, 4, 8, 12)], f(d["pa_long"], 2)])
T["speed"] = table("tA4", "Table A4. How Fast Spending Adjusts to a Permanent Change in Stock Wealth",
                   [[("Sample", 1), ("Model", 1), ("Share of the gap closed each quarter (SE)", 1), ("Half-life (quarters)", 1),
                     ("Share of the long-run effect reached (percent)", 4), ("Long-run effect (cents)", 1)],
                    [("", 1), ("", 1), ("", 1), ("", 1), ("Quarter 1", 1), ("Quarter 4", 1), ("Quarter 8", 1), ("Quarter 12", 1), ("", 1)]],
                   rows,
                   note="Quarter 1 is the quarter of the change. Error correction: the quarterly change in the spending share on last quarter’s "
                        "residual from the levels regression, last quarter’s change in the share and the current changes in the wealth ratios and "
                        "controls; its long-run effect is the levels coefficient, and its large first-quarter share comes from the current change "
                        f"in stock wealth ({f(R['dyn']['1955Q1-2019Q4']['dS_short'], 2)} cents through 2019). Partial adjustment: the levels "
                        "regression with last quarter’s spending share added; the speed is one minus that coefficient and the long-run effect is "
                        "the short-run coefficient divided by the speed. Newey–West standard errors, four lags.",
                   source=SRC)

# ------------------------------------------------------------------ A5 specification sensitivity
rows = []
for s in R["sens"]:
    lab = s["spec"]
    def g(k):
        v = s.get(k)
        return "—" if v is None or (isinstance(v, float) and v != v) else cse(v, s.get(k.replace("_", "se_", 1)) if False else s.get({"S_2019": "Sse_2019", "S_2026": "Sse_2026", "H_2019": "Hse_2019", "H_2026": "Hse_2026"}[k]))
    rows.append([lab, g("S_2019"), g("S_2026"), g("H_2019"), g("H_2026")])
T["sens"] = table("tA5", "Table A5. How the Wealth Coefficients Change With the Specification",
                  [[("Specification", 1), ("Stock wealth", 2), ("Housing wealth", 2)],
                   [("", 1), ("1955–2019", 1), (f"1955–{END[:4]}", 1), ("1955–2019", 1), (f"1955–{END[:4]}", 1)]], rows,
                  note="Cents per dollar; Newey–West standard errors in parentheses. “Leads and lags” is dynamic ordinary least squares. The "
                       "home-equity row reports home equity (housing minus mortgages) in the housing columns, with mortgages moved out of other "
                       "wealth. The net-worth row reports the single net-worth coefficient in the stock columns.", source=SRC, cls="reg")

# ------------------------------------------------------------------ A6 year by year (points of income)
an19 = N["anchors"]["2019"]["anchor_pp"]; an1519 = N["anchors"]["2015–2019"]["anchor_pp"]
ser["res"] = ser["cy"] - ser["fit19"]
ser["gap19"] = ser["fit19"] + an19 - ser["cy"]; ser["gap1519"] = ser["fit19"] + an1519 - ser["cy"]
rows = []
for y in (2000, 2005, 2007, 2010, 2012, 2013, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, END):
    sl = ser.loc[f"{y}Q1":f"{y}Q4"] if isinstance(y, int) else ser.loc[[END]]
    lab = str(y) if isinstance(y, int) else END.replace("Q", " Q")
    pre = y if isinstance(y, int) else 2026
    rows.append([lab, f(sl["cy"].mean(), 1), f(sl["fit19"].mean(), 1), f(sl["res"].mean(), 1),
                 f(sl["gap19"].mean(), 1) if pre >= 2019 else "—", f(sl["gap1519"].mean(), 1) if pre >= 2019 else "—"])
T["yearly"] = table("tA6", "Table A6. The 1955–2019 Consumption Function, Year by Year",
                    [[("Year", 1), ("Actual spending share", 1), ("Fitted share", 1), ("Actual minus fitted", 1),
                      ("Predicted minus actual, anchored to:", 2)], [("", 1), ("", 1), ("", 1), ("", 1), ("2019", 1), ("2015–2019", 1)]], rows,
                    note="Percent of disposable income (spending share) and percentage points (the rest); annual averages of quarterly values. "
                         f"Fitted values are in sample through 2019. The anchored predictions add the average residual of the anchor period "
                         f"({f(an19, 2)} points for 2019, {f(an1519, 2)} for 2015–2019) and ignore the lockdowns, so 2020 and 2021 are dominated "
                         "by them.", source=SRC)

# ------------------------------------------------------------------ A7 decomposition
rows = []
for r in R["decomp"]:
    tr_ = r["var"] == "tr_share"
    coefv = r["coef"] * (1 if tr_ else 100)
    rows.append([r["label"], f(r["v2019"] * (100 if tr_ else 1), 2), f(r["vend"] * (100 if tr_ else 1), 2), f(coefv, 2 if r["var"] in ("Sy", "Hy", "Oy") else 3), f(r["contrib_pp"], 2, plus=True), f(r["contrib_bn"], 0, plus=True)])
tot_pp = sum(r["contrib_pp"] for r in R["decomp"]); tot_bn = sum(r["contrib_bn"] for r in R["decomp"])
rows.append(['<b>Predicted change</b>', "", "", "", f"<b>{f(tot_pp, 2, plus=True)}</b>", f"<b>{f(tot_bn, 0, plus=True)}</b>"])
rows.append(['<b>Actual change</b>', f(N["anchors"]["2019"]["anchor_pp"] * 0 + R["levels"]["2019avg"]["cy"], 1), f(R["levels"][END]["cy"], 1), "",
             f"<b>{f(R['actual_share_change_pp'], 2, plus=True)}</b>", f"<b>{f(R['actual_share_change_bn'], 0, plus=True)}</b>"])
rows.append(['<b>Predicted minus actual</b>', "", "", "", f"<b>{f(tot_pp - R['actual_share_change_pp'], 2, plus=True)}</b>", f"<b>{f(tot_bn - R['actual_share_change_bn'], 0, plus=True)}</b>"])
T["decomp"] = table("tA7", f"Table A7. Why the Model Expected Spending to Rise Faster Than Income, 2019 to {END.replace('Q', ' Q')}",
                    h(["Variable", "2019 average", END.replace("Q", " Q"), "Coefficient", "Contribution to the spending share (points)",
                       "Contribution ($ billions)"]), rows,
                    note="Wealth ratios are multiples of income; transfers and the spending share are percent of income. Coefficients on wealth "
                         "are cents per dollar, on transfers points per point, on the others points per unit. Contribution = coefficient × change; "
                         f"dollars multiply points of income by disposable income in {END.replace('Q', ' Q')} (${f(N['dpi_end_bn'] / 1000, 1)} trillion, annual rate).",
                    source=SRC)

# ------------------------------------------------------------------ A8 anchor sensitivity (points of income)
rows = []
sr = {2015: 5.9, 2016: 5.4, 2017: 5.8, 2018: 6.4, 2019: 7.3, 2022: 3.5, 2023: 6.1, 2024: 6.2}
for r in N["anchor_sens_income"]:
    rows.append([str(r["year"]), f(r["saving"], 1), f(r["anchor_pp"], 2), f(r["gap_pp_income"], 1), f(r["gap_bn"], 0), f(r["stock_effect_bn"], 0), f(r["shown_bn"], 0)])
a = N["anchors"]["2015–2019"]
rows.insert(5, ['<b>2015–2019 average</b>', "—", f"<b>{f(a['anchor_pp'], 2)}</b>", f"<b>{f(a['gap_pp'], 1)}</b>", f"<b>{f(a['gap_bn'], 0)}</b>",
                f"<b>{f(a['stock_exp_bn'], 0)}</b>", f"<b>{f(a['stock_visible_bn'], 0)}</b>"])
T["anchor"] = table("tA8", f"Table A8. The Projection’s Miss in {END.replace('Q', ' Q')} Depends on the Anchor",
                    h(["Anchor", "Saving rate that year (percent)", "Anchor (points of income)", "Predicted minus actual (percent of income)",
                       "Predicted minus actual ($ billions)", "What stocks were expected to add ($ billions)", "What is visible ($ billions)"]), rows,
                    note="The 1955–2019 estimates, shifted by the average residual of the anchor period. “Expected” is the stock coefficient times "
                         "the rise in stock wealth above its anchor-period ratio to income; “visible” is expected minus the miss, i.e., how far "
                         "actual spending is above a version of the model with stock wealth held at the anchor ratio. A negative visible effect "
                         "means actual spending is below even that version. Saving rates are annual averages (BEA).", source=SRC)

# ------------------------------------------------------------------ A9 estimation sample and specification
rows = []
for r in N["est_sens_income"]:
    rows.append([r["sample"], f(r["S"], 2), f(r["anchor_pp"], 2), f(r["gap_pp_income"], 1), f(r["gap_bn"], 0), f(r["stock_effect_bn"], 0), f(r["shown_pct"], 0)])
T["est"] = table("tA9", "Table A9. The Projection’s Miss Under Other Samples and Specifications (All Anchored to 2019)",
                 h(["Estimated on", "Stock coefficient (cents)", "Anchor (points of income)", "Predicted minus actual (percent of income)",
                    "Predicted minus actual ($ billions)", "What stocks were expected to add ($ billions)", "Share of that visible (percent)"]), rows,
                 note=f"All in {END.replace('Q', ' Q')}. A negative share means actual spending is below the version with stock wealth held at its 2019 ratio.",
                 source=SRC)

# ------------------------------------------------------------------ A10 out-of-sample record (27 quarters, as in Figure A3)
oo = pd.read_csv(O / "r9_oos_rolling_origin.csv").set_index("anchor")
rows = []
for an in (1975, 1980, 1985, 1990, 1995, 1999, 2003, 2007, 2009, 2010, 2011, 2012, 2019):
    r = oo.loc[an]; path = [float(v) for v in str(r["path"]).split(";")]
    lab = f"<b>{an}</b>" if an == 2019 else str(an)
    rows.append([lab, f"1955–{an}", f"{an + 1} Q1–{r['target'].replace('Q', ' Q')}", f(r["gap_pct"], 1), f(r["stock_part_pct"], 1),
                 f(max(path, key=abs), 1) if an != 2019 else "—", f(sum(path) / len(path), 1) if an != 2019 else "—"])
T["oos"] = table("tA10", "Table A10. How Far Off the Same Method Was Six and Three-Quarter Years Later",
                 h(["Anchor year", "Estimated on", "Window", "Error at end of window (percent)", "What the model expected stocks to add (percent of spending)",
                    "Largest error in window (percent)", "Average error in window (percent)"]),
                 rows,
                 note="Error = predicted minus actual spending, percent of actual spending, 27 quarters after the anchor year (the distance from "
                      f"2019 Q4 to {END.replace('Q', ' Q')}). Across all {X['ro_n']} anchor years from 1970 to 2012 (windows ending before 2020), "
                      f"the absolute error at that point had a median of {f(float(X['ro_abs_median']), 1)} percent, a 75th percentile of "
                      f"{f(float(X['ro_abs_p75']), 1)}, a 90th percentile of {f(float(X['ro_abs_p90']), 1)} and a maximum of "
                      f"{f(float(X['ro_abs_max']), 1)}, and its correlation with what the model expected stocks to add was "
                      f"{f(float(X['ro_corr_gap_stockpart']), 2)}. For the 2019 run the largest errors are in the lockdown quarters, so the window "
                      "columns are not shown.", source=SRC)

# ------------------------------------------------------------------ A11-A13 gains and losses
A = R["asym"]
rows = [["1955–2019", cse(A["1955–2019"]["Gy"], A["1955–2019"]["Gy_se"]), cse(A["1955–2019"]["Ly"], A["1955–2019"]["Ly_se"]), f(A["1955–2019"]["diff_t"], 2), "—", cse(A["1955–2019"]["Hy"], A["1955–2019"]["Hy_se"])],
        [f"1955–{END[:4]}", cse(A["1955–2026"]["Gy"], A["1955–2026"]["Gy_se"]), cse(A["1955–2026"]["Ly"], A["1955–2026"]["Ly_se"]), f(A["1955–2026"]["diff_t"], 2), "—", cse(A["1955–2026"]["Hy"], A["1955–2026"]["Hy_se"])],
        [f"1955–{END[:4]}, gains since 2019 separate", cse(A["post"]["Gy"], A["post"]["Gy_se"]), cse(A["post"]["Ly"], A["post"]["Ly_se"]), f(A["post"]["diff_t"], 2), cse(A["post"]["gp"], A["post"]["gp_se"]), cse(A["post"]["Hy"], A["post"]["Hy_se"])]]
T["asym_levels"] = table("tA11", "Table A11. Accumulated Stock Gains and Losses Entered Separately",
                         h(["Sample", "Accumulated gains (cents)", "Accumulated losses (cents)", "t-statistic, gains minus losses", "Gains since 2019 (cents)", "Housing (cents)"]),
                         rows, note="The consumption function with stock wealth relative to income split into accumulated real holding gains since 1952, "
                                    "accumulated real holding losses since 1952 (a negative number) and the remainder (the 1952 stock plus net purchases). "
                                    "In the last row, gains are split into those through 2019 and those from 2020 on. Newey–West standard errors in parentheses.",
                         source=SRC, cls="reg")
rows = []
for v in R["asym_variants"]:
    parts = []
    for lk, gk in (("Ln", None), ("L8", "G8"), ("L12", "G12"), ("short", None)):
        if v.get(lk) is not None: parts.append(f"losses {f(v[lk], 2)} (t = {f(v[lk + '_t'], 1)})")
        if gk and v.get(gk) is not None: parts.append(f"gains {f(v[gk], 2)} (t = {f(v[gk + '_t'], 1)})")
    extra = "; ".join(parts)
    rows.append([v["variant"], "1955–2019" if v["sample"] == "2019" else f"1955–{END[:4]}", f(v["S"], 2), extra])
T["asym_extra"] = table("tA12", "Table A12. Extra Effects of Losses and Gains on Top of Stock Wealth",
                        h(["Variant", "Sample", "Stock wealth (cents)", "Extra terms (cents)"]), rows,
                        note="Each extra term enters alongside total stock wealth, so it measures the effect beyond the average. Losses are negative "
                             "numbers, so a positive coefficient means losses lower spending by more than the average. The shortfall from the previous "
                             "peak is real stock wealth per person below its previous high, scaled by income.", source=SRC)
rows = []
for r in R["asym_changes"]:
    if r["start"][:4] != "1955" or r["end"][:4] not in ("2019", END[:4]): continue     # the two samples the text discusses
    rows.append([f"{r['start'][:4]}–{r['end'][:4]}", str(r["h"]), cse(r["up"], r["up_se"]), cse(r["down"], r["down_se"]), f(r["t"], 2)])
T["asym_changes"] = table("tA13", "Table A13. The Changes Model: Cumulative Response of Spending to Real Gains and Losses",
                          h(["Sample", "Quarters after", "Gains (cents)", "Losses (cents)", "t-statistic, gains minus losses"]), rows,
                          note="The quarterly change in real spending per person regressed on the current and eight lagged quarterly real holding gains "
                               "on stocks, housing and other wealth (stocks split by sign), with income growth and changes in unemployment and the real "
                               "interest rate. Cents of spending per dollar of gain or loss, summed over the current and following quarters. Newey–West "
                               "standard errors (four lags) in parentheses.", source=SRC, cls="reg")

# ------------------------------------------------------------------ A14 rolling and expanding
ro = pd.read_csv(O / "r9_rolling_all.csv"); ep = pd.read_csv(O / "r9_expanding_path.csv", index_col=0)
SX_EXP = float(pd.read_csv(O / "part3_r10_expanding.csv", index_col=0).loc[END, "Sx"])     # from AI-Bubble-Aftermath (part3_r10_expanding.py)
SX_R20 = float(pd.read_csv(O / "part3_r11_rolling20.csv", index_col=0).loc[END, "Sx"])     # (part3_r11_images.py)
def rget(W_, q):
    s = ro[(ro["W"] == W_) & (ro["end"] == q)]
    return cse(float(s["Sy"].iloc[0]), float(s["Sy_se"].iloc[0])) if len(s) else "—"
def eget(q, k="Sy"):
    fr = R["expanding"].get(q)
    if fr: return cse(fr[k], fr[k + "_se"])
    return cse(float(ep.loc[q, "Sy"]), float(ep.loc[q, "Sy_se"])) if k == "Sy" and q in ep.index else "—"
rows = []
for q in ("1999Q4", "2007Q4", "2012Q4", "2015Q4", "2019Q4", "2021Q4", "2023Q4", "2024Q4", "2025Q4", END):
    rows.append([q.replace("Q", " Q"), eget(q), rget(80, q), rget(60, q), rget(40, q), eget(q, "Hy")])
T["roll"] = table("tA14", "Table A14. The Stock Coefficient Estimated on Different Samples",
                  [[("Sample ends", 1), ("Stock wealth (cents)", 4), ("Housing (cents)", 1)],
                   [("", 1), ("From 1955", 1), ("Last 20 years", 1), ("Last 15 years", 1), ("Last 10 years", 1), ("From 1955", 1)]], rows,
                  note="The consumption function (Table A3) on samples ending at the date shown. Newey–West standard errors in parentheses. Samples "
                       "that reach 2020 include the lockdown dummies. Dropping 2020–2021 entirely instead, the estimate through "
                       f"{END.replace('Q', ' Q')} is {f(SX_EXP, 2)} from 1955 and {f(SX_R20, 2)} over the last 20 years.", source=SRC, cls="reg")

# ------------------------------------------------------------------ A15-A16 break tests
bt = R["breaks"]
rows = []
for b in bt:
    if not b["test"].startswith("levels"): continue
    rows.append(["Stocks" if b["test"].endswith("Sy") else "Housing", b["sample"], f"{b['first_candidate'].replace('Q', ' Q')}–{b['last_candidate'].replace('Q', ' Q')}",
                 b["break_date"].replace("Q", " Q"), f(b["sup_wald"], 1), f"{f(b['cv10'], 2)} / {f(b['cv5'], 2)} / {f(b['cv1'], 2)}", f(b["coef_before"], 2), f(b["coef_after"], 2)])
T["breaks"] = table("tA15", "Table A15. Tests for One Unknown Break in a Wealth Coefficient",
                    h(["Coefficient", "Sample", "Dates searched", "Most likely break", "Sup-Wald statistic", "Critical values (10 / 5 / 1 percent)", "Before (cents)", "After (cents)"]),
                    rows, note="Every coefficient may change at the break; the statistic is the largest Wald statistic for a change in the named "
                               "coefficient over all candidate dates, compared with Andrews (1993, corrected 2003) critical values. The share of the "
                               "sample trimmed from each end sets how close to the ends a break may fall; the critical values assume stationary "
                               "regressors, so they are approximate here.", source=SRC)
rows = []
for c in X["chow"] if isinstance(X["chow"], list) else json.loads(X["chow"].replace("'", '"')):
    pass
chow = X["chow"] if isinstance(X["chow"], list) else eval(X["chow"])
bydate = {}
for c in chow:
    bydate.setdefault(c["tau"], {})[c["end"]] = c
for tau, d in bydate.items():
    a19 = d.get("2019Q4"); aE = d.get(END)
    rows.append([tau.replace("Q", " Q"), f(a19["before"], 2), f"{f(a19['after'], 2)} ({a19['n_after']} quarters)", f(a19["wald"], 1),
                 f"{f(aE['after'], 2)} ({aE['n_after']} quarters)" if aE else "—", f(aE["wald"], 1) if aE else "—"])
T["chow"] = table("tA16", "Table A16. Breaks at Given Dates, With and Without the Years Since 2019",
                  h(["Break at", "Before (cents)", "After, data through 2019", "Wald", f"After, data through {END.replace('Q', ' Q')}", "Wald"]), rows,
                  note="All coefficients may change at the break date. For a date chosen in advance (2010 Q1 here) the 5 percent critical value is "
                       "3.84; for a date found by searching (2008 Q2 and 2013 Q4 were picked by the tests in Table A15), compare with the Andrews "
                       "values of 7 to 9 there.", source=SRC)

# ------------------------------------------------------------------ A17 county (from the county note, 2026-11-15)
county = [("Chodorow-Reich, Nenov and Simsek (2021), as published", "3.24 (1.01)", "2.18 (0.63)"),
          ("Rebuild, same years", "1.9 (0.9)", "1.9 (0.9)"),
          ("Rebuild, 1992–2018 moves", "1.7 (0.8)", "1.8 (0.8)"),
          ("&nbsp;&nbsp;First half, 1992–2004", "0.6 (0.9)", "0.5 (1.0)"),
          ("&nbsp;&nbsp;Second half, 2005–2018", "2.5 (1.3)", "2.6 (1.3)"),
          ("Rebuild, all years through mid-2024, 2020–2022 out", "1.6 (0.8)", "1.8 (0.7)"),
          ("Rebuild, the five clean quarters since COVID (2023Q2–2024Q2), pooled with 1992–2018", "1.6 (1.6)", "1.1 (1.2)"),
          ("Rebuild, 1992–2018: market up", "2.9 (1.3)", "2.3 (1.3)"),
          ("Rebuild, 1992–2018: market down (27 of 105 quarters)", "0.2 (1.2)", "1.3 (1.1)")]
T["county"] = table("tA17", "Table A17. The County Design: Local Payrolls Seven Quarters After a Stock Market Move",
                    h(["Sample", "Payroll in retail, restaurants and hotels (≈ cents per dollar)", "Total payroll"]), [list(r) for r in county],
                    note="Basis points of payroll per stock-market gain equal to 1 percent of a county’s annual labor income, which in the paper’s "
                         "calibration reads as cents of household spending per dollar of stock wealth. Standard errors, clustered by county and "
                         "quarter, in parentheses. Each row is its own regression, except the post-COVID row, which is estimated together with "
                         "the pre-COVID years (only the stock coefficient differs between the two periods), and the market-up and market-down rows, "
                         "which split the stock move by the sign of the quarter’s return in one regression.",
                    source="Chodorow-Reich, Nenov and Simsek (2021); IRS Statistics of Income county data; BLS Quarterly Census of Employment and "
                           "Wages; Survey of Consumer Finances; author’s calculations.")

# ------------------------------------------------------------------ A18 back-of-envelope
rows = []
boe = {(r["base"], r["end"]): r for r in N["boe"]}
for base in ("2000–2019", "2010–2019", "2015–2019", "2015", "2016", "2017", "2018", "2019", "2022", "2023", "2024"):
    a_, b_ = boe[(base, "2026Q1–Q3")], boe[(base, "2026Q3")]
    lab = f"<b>{base}</b>" if base == "2015–2019" else base
    rows.append([lab, f(a_["c0"], 1), f(a_["s0"], 2), f(a_["cents"], 1), f(b_["cents"], 1), f(a_["cents_net_housing"], 1)])
T["boe"] = table("tA18", "Table A18. The Back-of-the-Envelope Calculation From Different Starting Points",
                 [[("Base period", 1), ("Spending share in base (percent of income)", 1), ("Stock wealth in base (multiple of income)", 1),
                   ("Cents of spending per dollar of extra stock wealth", 3)],
                  [("", 1), ("", 1), ("", 1), ("To 2026 so far", 1), ("To 2026 Q3", 1), ("To 2026 so far, net of housing", 1)]], rows,
                 note="The rise in spending as a share of disposable income from the base period to 2026, divided by the rise in household stock "
                      f"wealth as a multiple of income. In the first three quarters of 2026 the spending share averaged {f(N['ratios']['2026Q1–Q3']['cy'], 1)} "
                      f"percent and stock wealth {f(N['ratios']['2026Q1–Q3']['Sy'], 2)} times income; in the third quarter alone, "
                      f"{f(N['ratios'][END]['cy'], 1)} and {f(N['ratios'][END]['Sy'], 2)}. “Net of housing” first takes off the rise in housing "
                      f"wealth times the consumption function’s housing coefficient ({f(R['main']['1955Q1-2019Q4']['Hy'], 1)} cents). Stock wealth is "
                      "measured at the start of each quarter.", source=SRC)

# ------------------------------------------------------------------ A19 models since 2019
t2 = pd.DataFrame(N["rules"]); q3 = t2[(t2["income"] == "all") & (t2["anchor"] == 2019) & (t2["end"] == END)].iloc[0]
q2 = t2[(t2["income"] == "all") & (t2["anchor"] == 2019) & (t2["end"] == "2026Q2")].iloc[0]
def bn(v): return f(v, 0, plus=True) if v == v else "—"
rows = [["Actual", f(q3["c_growth"], 1), "—", "—", "—"],
        ["Consumption function (estimated 1955–2019)", f(q3["cf_growth"], 1), bn(q3["cf_gap_bn"]), f(q3["cf_gap_bn"] / N["dpi_end_bn"] * 100, 1, plus=True), bn(q3["cf_cum_bn"])],
        ["Spend 1 cent per dollar of stock gains", f(q3["rule1_growth"], 1), bn(q3["rule1_gap_bn"]), f(q3["rule1_gap_bn"] / N["dpi_end_bn"] * 100, 1, plus=True), bn(q3["rule1_cum_bn"])],
        ["Spend 3 cents per dollar", f(q3["rule3_growth"], 1), bn(q3["rule3_gap_bn"]), f(q3["rule3_gap_bn"] / N["dpi_end_bn"] * 100, 1, plus=True), bn(q3["rule3_cum_bn"])],
        ["Spend 5 cents per dollar", f(q3["rule5_growth"], 1), bn(q3["rule5_gap_bn"]), f(q3["rule5_gap_bn"] / N["dpi_end_bn"] * 100, 1, plus=True), bn(q3["rule5_cum_bn"])],
        ["No wealth effect (2019 spending share)", f(q3["noeffect_growth"], 1), bn(q3["noeffect_gap_bn"]), f(q3["noeffect_gap_bn"] / N["dpi_end_bn"] * 100, 1, plus=True), bn(q3["noeffect_cum_bn"])],
        ["Fed’s model (FRB/US), through 2026 Q2*", f(q2["frbus_growth"], 1) + "*", bn(q2["frbus_gap_bn"]) + "*", "—", bn(q2["frbus_cum_bn"]) + "*"]]
T["rules"] = table("tA19", "Table A19. Consumer Spending Since 2019 Compared With What Six Models Predict",
                   h(["Model", "Spending growth since 2019 (percent)", "Predicted minus actual ($ billions, annual rate)",
                      "Predicted minus actual (percent of income)", "Cumulative since 2022 Q1 ($ billions)"]), rows,
                   note=f"2019 to {END.replace('Q', ' Q')}, current dollars. Disposable income rose {f(q3['y_growth'], 0)} percent and household stock "
                        f"wealth went from {f(q3['s_ratio_anchor'], 2)} to {f(q3['s_ratio_end'], 2)} times income. Each model starts from actual spending "
                        "in 2019 and is given what actually happened to income and wealth. The rules add the stated cents per dollar of stock wealth above "
                        "its 2019 ratio to income, immediately, to spending that otherwise keeps its 2019 share of income; a rule of "
                        f"{f(q3['mpc_fit'], 1)} cents matches spending exactly. *FRB/US ends in the second quarter of 2026, the last quarter in the Fed’s "
                        f"data (actual growth to then: {f(q2['c_growth'], 1)} percent).",
                   source="BEA; Federal Reserve Board, Financial Accounts and FRB/US; author’s calculations.")

# ------------------------------------------------------------------ A20 GDP
t1 = N["table1"]; rows = []
for pct in ("25", "35", "50"):
    r = t1[pct]
    rows.append([f"{pct} percent (${f(r['lost_bn'] / 1000, 1)} trillion)", f(r["frbus_earn_4"], 2), f(r["frbus_ret_4"], 2), f(r["r1"], 2),
                 f(r["cf_4"], 2), f(r["r3"], 2)])
rows.append('<tr class="sub"><td colspan="6"><i>25 percent fall, by horizon</i></td></tr>')
r = t1["25"]
for hq, lab in ((4, "After 1 year"), (8, "After 2 years"), (12, "After 3 years"), (20, "After 5 years")):
    rows.append([lab, f(r[f"frbus_earn_{hq}"], 2), f(r[f"frbus_ret_{hq}"], 2), f(r["r1"], 2), f(r[f"cf_{hq}"], 2), f(r["r3"], 2)])
T["gdp"] = table("tA20", "Table A20. The Arithmetic Behind the Post’s Table 1",
                 [[("Fall in the stock market", 1), ("FRB/US", 2), ("Spend 1 cent per dollar", 1), ("Consumption function (2.2 cents, phased in)", 1), ("Spend 3 cents per dollar", 1)],
                  [("", 1), ("Lower earnings", 1), ("Higher required return", 1), ("", 1), ("", 1), ("", 1)]], rows,
                 note="Reduction in the level of real GDP relative to a world without the fall, percent; the post reads the one-year number as the cut "
                      f"in growth over the next year. Household stock wealth is ${f(N['S_NOW'] / 1000, 1)} trillion (Financial Accounts, 2026 Q2) and "
                      f"GDP ${f(N['GDP_NOW'] / 1000, 1)} trillion (2026 Q3, annual rate). The rules divide the cut in annual spending by GDP; the "
                      f"consumption function phases {f(R['main']['1955Q1-2019Q4']['Sy'], 2)} cents in at its estimated partial-adjustment speed "
                      f"({f(100 * (1 - N['rho19']), 0)} percent of the remaining gap each quarter, {f(100 * N['share4'], 0)} percent within a year). "
                      "FRB/US is the Econvitals Macroeconomic Simulator’s permanent 30 percent fall, scaled to 25 percent and to today’s stock wealth, "
                      "with the Fed responding and imports absorbing part of the spending cut; the 35 and 50 percent rows scale it proportionally.",
                 source="Federal Reserve Board, Financial Accounts and FRB/US; BEA; author’s calculations.")


# ------------------------------------------------------------------ cells
cells = {}
for k, v in T.items():
    tid = re.search(r'id="(tA\d+)"', v).group(1)
    rows_ = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", v, re.S):
        rows_.append([re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                      for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)])
    cells[tid] = rows_
json.dump(cells, open(O / "appendix_tables.json", "w"), indent=0, ensure_ascii=False)
print("appendix tables rebuilt:", len(cells), "tables,", sum(len(r) for t in cells.values() for r in t), "cells")
