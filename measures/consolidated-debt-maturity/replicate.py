"""Consolidated Debt Maturity — rebuilds the cross-country maturity chart on econvitals.org/fiscal/.

    python replicate.py        # no key needed; writes output/debt_maturity.csv

For 18 economies at the end of 2025: the average maturity of the government's marketable debt
(gross), and the same with the central bank's holdings of that debt counted as overnight money —
the maturity of the consolidated government-plus-central-bank balance sheet:

    net = (D x WAM - CB x WAM_CB) / D

where D is the debt and WAM its average maturity, CB the central bank's holdings and WAM_CB theirs.
The denominator stays D. Sources by row:
  United States    computed here, security by security (Treasury + New York Fed).
  euro area (11)   computed here from the European Central Bank's published files.
  the other six    recorded inputs (inputs/recorded_inputs.csv), assembled from each debt office's
                   and central bank's own lists; see the README for why.
"""
import csv
import datetime as dt
import io
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import get, save  # noqa: E402
from common.finance import soma_asof_dates, soma_asof_for, treasury_securities  # noqa: E402

YEAR_END = dt.date(2025, 12, 31)
DAY = 1 / 365.25


def net_maturity(debt, wam, cb, wam_cb):
    return (debt * wam - cb * wam_cb) / debt


# ------------------------------------------------------------------ United States
def united_states():
    """Par-weighted years to maturity of every marketable Treasury security at end-2025; net of
    the Fed, its holdings are replaced by overnight reserves (one day)."""
    secs = treasury_securities(YEAR_END, soma_asof_for(YEAR_END, soma_asof_dates()))
    secs["t"] = [(m - YEAR_END).days / 365.25 for m in secs["maturity"]]
    secs = secs[secs["t"] > 0]                       # drop matured-but-unredeemed securities
    par, fed = secs["par"].sum(), secs["fed_par"].sum()
    gross = (secs["par"] * secs["t"]).sum() / par
    net = (((secs["par"] - secs["fed_par"]) * secs["t"]).sum() + fed * DAY) / par
    return dict(country="United States", gross_exact=gross, net_exact=net, decimals=2,
                basis="computed: Treasury MSPD + New York Fed SOMA")


# ------------------------------------------------------------------ euro area
ECB_API = "https://data-api.ecb.europa.eu/service/data/GFS/"
GFS_WAM = "M.N..W0.S13.S1.N.L.LE.F3.TT._Z.YR._T.F.V.A1._T"     # avg residual maturity, years
GFS_DEBT = "M.N..W0.S13.S1.N.L.LE.F3.T._Z.EUR._T.F.V.N._T"     # outstanding, EUR millions
ECB_FILES = "https://www.ecb.europa.eu/mopo/pdf/"
# Our country code: (name in the PSPP file, name in the PEPP file, chart label). I9 = euro area.
EA = {"DE": ("Germany", "Germany", "Germany"), "FR": ("France", "France", "France"),
      "IT": ("Italy", "Italy", "Italy"), "ES": ("Spain", "Spain", "Spain"),
      "NL": ("the Netherlands", "Netherlands", "Netherlands"), "BE": ("Belgium", "Belgium", "Belgium"),
      "AT": ("Austria", "Austria", "Austria"), "PT": ("Portugal", "Portugal", "Portugal"),
      "IE": ("Ireland", "Ireland", "Ireland"), "FI": ("Finland", "Finland", "Finland")}


def gfs(key):
    """Government debt securities by country, December 2025 (general government, face value)."""
    text = get(ECB_API + key, {"format": "csvdata", "startPeriod": "2025-12", "endPeriod": "2025-12"})
    return pd.read_csv(io.StringIO(text)).set_index("REF_AREA")["OBS_VALUE"]


def breakdown(file, month):
    """From an ECB PSPP/PEPP breakdown file: {issuer: (holdings at book value, WAM of holdings)} at
    `month` (the file's own column header). Holdings = monthly net purchases summed through `month`."""
    sections, title, header = {}, None, None
    for row in csv.reader(io.StringIO(get(ECB_FILES + file))):
        label, rest = (row[0].strip() if row else ""), [x.strip() for x in row[1:]]
        if not any(rest):
            title = label or title
            continue
        if not label:
            header = [x.strip() for x in row]
            continue
        sections.setdefault(title, {})[label] = {
            h: float(v.replace(",", "")) for h, v in zip(header[1:], rest) if h and v not in ("", "-")}
    purchases = next(v for k, v in sections.items() if "et purchases" in k)
    wam = next(v for k, v in sections.items() if k.startswith("WAM") and "eligible" not in k)
    out = {}
    for issuer, cols in purchases.items():
        months = [h for h in cols if not h.lower().startswith("cumulative")]
        held = sum(cols[h] for h in months[:months.index(month) + 1])
        out[issuer] = (held, wam.get(issuer, {}).get(month))
    return out


def amortized_holdings(file, programme, year, month):
    """End-of-month holdings at amortized cost ("Holdings*") of one programme, EUR millions."""
    rows = list(csv.reader(io.StringIO(get(ECB_FILES + file))))
    measure, cols = None, []
    for top, prog in zip(rows[1], rows[2]):         # a measure heads a block of programme columns
        measure = top.strip() or measure
        cols.append((measure, prog.strip()))
    col = cols.index(("Holdings*", programme))
    current_year = None
    for r in rows[3:]:
        if not r:
            continue
        current_year = r[0].strip() or current_year       # the year is written on January only
        if len(r) > col and current_year == str(year) and r[1].strip() == month:
            return float(r[col])
    raise RuntimeError(f"{file}: no {programme} holdings for {month} {year}")


def euro_area():
    wam, debt = gfs(GFS_WAM), gfs(GFS_DEBT)
    pspp = breakdown("PSPP_breakdown_history.csv", "31/12/2025")
    pepp = breakdown("PEPP_public_sector_securities_breakdown_history.csv", "Dec-25")
    # The breakdown files give holdings at acquisition cost less redemptions; scale each programme to
    # amortized cost with its own end-2025 ratio, from the ECB's programme-level holdings files.
    k_pspp = amortized_holdings("APP_breakdown_history.csv", "Public sector purchase programme",
                                2025, "December") / pspp["Total"][0]
    k_pepp = amortized_holdings("PEPP_breakdown_history.csv", "Public Sector Securities",
                                2025, "December") / pepp["Total"][0]

    def holdings(pspp_names, pepp_names):
        hp = [(pspp[n][0] * k_pspp, pspp[n][1]) for n in pspp_names]
        hq = [(pepp[n][0] * k_pepp, pepp[n][1]) for n in pepp_names]
        cb = sum(h for h, _ in hp + hq)
        return cb, sum(h * w for h, w in hp + hq) / cb

    rows = []
    issuers = [("I9", [n for n in pspp if n not in ("Total", "Supranationals")],
                [n for n in pepp if n not in ("Total", "Supranationals")], "Euro area")]
    issuers += [(cc, [p], [q], label) for cc, (p, q, label) in EA.items()]
    for cc, pspp_names, pepp_names, label in issuers:
        cb, wam_cb = holdings(pspp_names, pepp_names)
        rows.append(dict(country=label, gross_exact=wam[cc],
                         net_exact=net_maturity(debt[cc], wam[cc], cb, wam_cb), decimals=2,
                         basis="computed: ECB government finance statistics + PSPP/PEPP holdings"))
    return rows


# ------------------------------------------------------------------ the recorded rows
def recorded():
    rec = pd.read_csv(HERE / "inputs" / "recorded_inputs.csv")
    return [dict(country=r.country, gross_exact=r.gross_wam,
                 net_exact=net_maturity(r.debt, r.gross_wam, r.cb_holdings, r.cb_wam),
                 decimals=int(r.decimals), basis="recorded inputs") for r in rec.itertuples()]


out = pd.DataFrame([united_states()] + euro_area() + recorded()).set_index("country")
# Shown as the chart shows them: two decimals, one for Switzerland, whose debt office publishes
# its average maturity to one decimal.
out["gross"] = [round(v, d) for v, d in zip(out["gross_exact"], out["decimals"])]
out["net_cb"] = [round(v, d) for v, d in zip(out["net_exact"], out["decimals"])]
out = out[["gross", "net_cb", "gross_exact", "net_exact", "basis"]].sort_values("net_cb")
save(out, HERE, "debt_maturity")
print(out[["gross", "net_cb", "basis"]].to_string())
