#!/usr/bin/env python3
"""Macroeconomic Simulator — build the response library the page reads.

Everything the page shows is precomputed here, with the Federal Reserve Board's own FRB/US model
(pyfrbus + LONGBASE.TXT, bundled in fed/; engine_paths.py), and written to ../data/ as JSON:

  meta.json            the menus (shocks, Fed responses, expectations, lower bound, financing,
                       durations, variables), the baseline values and the package vintages
  runs/<shock>_<exp>_<elb>_<fiscal>.json   the runs, keyed size|fed|duration, as deviations from baseline, 41 quarters
                       (14 shocks since 2026-10-31: the first nine plus reallocation, tariffs, immigration,
                       inflation expectations and credit spreads; business investment since 2026-11-07, stored as two
                       runs, `invest` all made at home and `investimp` all imported, which the page mixes; since
                       2026-11-08 a second stock-price shock, `stocks_earn` — higher expected earnings rather than a
                       lower required return — shown under the Stock prices tile)
  engine/solve_log.json   every build's count of model solves; meta.json "counts" = pre-solved scenarios, the
                       ones that did not solve, and the model runs it took (the page's last line prints them)

A "run" is one impulse response: shock × size × Fed response × duration × expectations × lower bound
× fiscal financing. The baseline is the Board's long-run extrapolation at 2040Q1 — a steady state
(output at potential, inflation at target, the funds rate at r* + target), the same starting point the
Board's own demo programs use — and every series is stored as the DIFFERENCE from that baseline, so
nothing here is a forecast. Tracking residuals (init_trac) make the model reproduce the baseline
exactly before a shock is applied.

Usage (from the folder above engine/, with requirements.txt installed):
  python engine/build.py --quick        # VAR only, a few sizes: minutes (development)
  python engine/build.py --exp var      # the backward-looking library: ~10 minutes on 8 cores
  python engine/build.py --exp mce      # the forward-looking library: hours (20-50 s a run, niced)
Every configuration's runs are written to its file as soon as it finishes, and a rerun skips what is already
there (--force reruns it), so a build can be stopped and resumed. Rebuild from scratch when the Board posts a
new data package (a few times a year): delete data/runs/, download the new packages, then this.
"""
import argparse, json, math, os, sys, time, traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
# Every path comes from engine_paths.py: the Board's packages (FRBUS_FED: a download folder outside the repo, or a
# replication package's bundled fed/) and the library (FRBUS_OUT, default ../data).
from engine_paths import FED, OUT
MODEL = str(FED / "pyfrbus" / "models" / "model.xml")
DATA = str(FED / "data_only_package" / "LONGBASE.TXT")
LOG = HERE / "build.log"

START = pd.Period("2040Q1")
H = 40                      # quarters shown: 0..40
VAR_END = START + H + 4
# Forward-looking (model-consistent) runs follow one set of rules (2026-11-08): they solve 200 quarters (50 years)
# out, since the 30-year expectations in stock wealth and long rates look far past the ten years shown (120 quarters
# left permanent shocks short of their end state), and the policy rule's r* learns from the real funds rate
# (drstar = 1, baseline_frame). Backward-looking runs are unchanged.
MCE_QUARTERS = 200
MCE_END = START + MCE_QUARTERS - 1
ELB_FLOOR_QUARTERS = 120     # the lower bound binds for 30 years at most (see config_task)

PI4 = "(( picxfe + picxfe(-1) + picxfe(-2) + picxfe(-3))/4)"
RULES = {
    # FRB/US's own rfftay is the Board's "balanced approach" (0.5 on the inflation gap, 1.0 on the output
    # gap); rffintay is that rule with 0.85 inertia, the Board's featured "inertial rule". Taylor (1993)
    # and the first-difference rule are written out from the Monetary Policy Report's definitions.
    "inertial": "rffintay",
    "balanced": "rfftay",
    "taylor93": f"(rstar + {PI4} + 0.5*({PI4} - pitarg) + 0.5*xgap2)",
    "firstdiff": f"(rff(-1) + 0.5*({PI4} - pitarg) + 0.5*(xgap2 - xgap2(-4)))",
}
RULE_IDS = list(RULES)
HOLDS = {"hold4": 4, "hold8": 8, "hold12": 12}       # the Fed holds the funds rate at baseline, then the inertial rule
FED_OPTIONS = ["hold4", "hold8", "hold12", "inertial", "balanced", "taylor93", "firstdiff"]
EXPS = ["var", "mce"]
ELBS = ["no", "yes"]
FISCALS = ["fixed", "debt"]          # both run for every shock; the page defaults to "fixed"
SIZES = [-2, -1, 1, 2]
# (expectations, lower bound, financing) combinations the engine never builds: forward-looking at the lower bound with
# the Board's debt rule converged in 86 of 680 runs (2026-10-27), so the page greys it out (meta.json "dropped").
# Built into the task list so a bare `build.py` cannot spend hours on it again (it started to, 2026-10-31).
DROPPED = {("mce", "yes", "debt")}
# Durations. "perm" = permanent: in force through the end of the solution, 45 quarters for backward-looking runs and 200
# for forward-looking ones, so no permanent shock ends inside the ten years shown and forward-looking agents never see
# it end. The page puts "1 year | Permanent" above the fold and the rest in Customize (2026-10-30).
PERM = 10_000                     # "permanent": in force through the end of the solution (capped in apply_shock)
DURS = {"q4": 4, "q8": 8, "q16": 16, "perm": PERM}
FED_DURS = {"q1": 1, "q4": 4, "q8": 8, "q12": 12, "perm": PERM}
MFP_DURS = {"q4": 4, "q8": 8, "q16": 16, "perm": PERM}   # q4 = the Board's one-time 1% level shift; longer = growth 1 point faster for that long

# ---- the shocks -----------------------------------------------------------------------------------
# unit = what size 1 means; exog = model variables taken out of the model and set by hand for the shock
# Labels name the variable, never a direction (2026-11-07: "Oil prices", not "Oil prices jump"): the size
# slider sets the direction. Sizes are in the ENGINE's units and signs (what data/runs stores and tools outside the page
# read); `page_sign` = -1 flips the page's slider for the three whose engine sign runs against the label
# (engine +1 = a tax CUT, stock prices FALLING 10%, a SMALLER working-age population), and `default_size` is the
# page's starting point, in page units (a tax cut, a stock-market fall, less immigration, as before the relabel).
SHOCKS = {
    "fed": dict(label="Federal funds rate", unit="1 percentage point", exog=[], fiscal=False,
                durs=FED_DURS, default_dur="q4", fed_options=RULE_IDS,
                slider=dict(min=-2, max=2, step=0.25), fmt="pp",
                blurb="The Fed moves the federal funds rate away from its baseline path by the amount chosen, then the chosen rule takes over."),
    "gov": dict(label="Government purchases", unit="1% of GDP", exog=["egfe"], fiscal=True,
                durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                slider=dict(min=-2, max=2, step=0.25), fmt="gdp",
                blurb="Federal purchases of goods and services change by the chosen share of GDP for the chosen period."),
    "tax": dict(label="Taxes", unit="1% of GDP (engine: +1 = a cut)", exog=[], fiscal=True,
                durs=DURS, default_dur="q4", fed_options=FED_OPTIONS, page_sign=-1, default_size=-1,
                slider=dict(min=-2, max=2, step=0.25), fmt="gdp",
                blurb="The average personal income tax rate moves by enough to change revenue by the chosen share of GDP, for the chosen period."),
    "transfers": dict(label="Transfers to households", unit="1% of GDP", exog=[], fiscal=True,
                      durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                      slider=dict(min=-2, max=2, step=0.25), fmt="gdp",
                      blurb="Government transfer payments to households change by the chosen share of GDP for the chosen period."),
    "oil": dict(label="Oil prices", unit="$25 a barrel", exog=["poil"], fiscal=False,
                durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                slider=dict(min=-2, max=2, step=0.25), fmt="oil",
                blurb="The price of imported oil moves by the chosen number of dollars a barrel for the chosen period."),
    "dollar": dict(label="The dollar", unit="10%", exog=["fpxr"], fiscal=False,
                   durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                   slider=dict(min=-2, max=2, step=0.25), fmt="pct10",
                   blurb="The real trade-weighted dollar moves by the chosen percentage for the chosen period."),
    "stocks": dict(label="Stock prices", unit="10% on impact (engine: +1 = a 10% FALL)", exog=["reqp"], fiscal=False,
                   durs=DURS, default_dur="q4", fed_options=FED_OPTIONS, page_sign=-1, default_size=-1,
                   sizes=[-3, -2, -1, 1, 2, 3], slider=dict(min=-3, max=3, step=0.25), fmt="pct10",
                   blurb="The equity premium moves by enough to move stock-market wealth by the chosen percentage on impact, for the chosen period."),
    # added 2026-11-08: the same move in stock prices for a different reason. `stocks` is investors accepting a
    # lower required return (the equity premium, which also sets half of businesses' cost of capital); `stocks_earn` is
    # investors expecting faster growth of real dividends (zdivgr, which enters only the stock-wealth equation). Its own id,
    # so every `stocks` link and stored run is unchanged; `variant_of` tells the page to show it as the second answer to
    # "why stock prices move" under the Stock prices tile, never as a tile of its own.
    "stocks_earn": dict(label="Stock prices (expected earnings)", unit="10% on impact, through expected earnings growth (engine: +1 = a 10% FALL)",
                        exog=[], fiscal=False, durs=DURS, default_dur="q4", fed_options=FED_OPTIONS, page_sign=-1, default_size=-1,
                        sizes=[-3, -2, -1, 1, 2, 3], slider=dict(min=-3, max=3, step=0.25), fmt="pct10", variant_of="stocks",
                        blurb="Investors’ expected growth of company earnings moves by enough to move stock-market wealth by the chosen percentage on impact, for the chosen period; unlike the required-return version, it does not shift businesses’ cost of capital."),
    "termprem": dict(label="Long-term rates", unit="1 point on the term premium", exog=["rg10p"], fiscal=False,
                     durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                     slider=dict(min=-2, max=2, step=0.25), fmt="pp",
                     blurb="The 10-year Treasury term premium moves by the chosen amount for the chosen period; a fall is what a bond-buying program does."),
    "mfp": dict(label="Productivity", unit="1%", exog=["hmfpt"], fiscal=False,
                durs=MFP_DURS, default_dur="q4", fed_options=FED_OPTIONS,
                slider=dict(min=-2, max=2, step=0.25), fmt="pct1",
                blurb="One year: the level of multifactor productivity moves by the chosen percentage, once and for all (the Board’s standard supply shock). Longer: productivity GROWTH is faster or slower by that many points a year for that long; permanent means for the whole horizon."),
    # added 2026-10-31: reallocation, tariffs, immigration, inflation expectations, credit spreads
    "realloc": dict(label="Labor market reallocation", unit="1 point on the natural rate of unemployment", exog=["lurnat"], fiscal=False,
                    durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                    slider=dict(min=-2, max=2, step=0.25), fmt="pp",
                    blurb="The natural rate of unemployment moves by the chosen amount for the chosen period: when workers moving between jobs and industries take longer to match, potential output is lower and wages respond to a smaller gap."),
    "tariff": dict(label="Tariffs", unit="a 10% tariff on non-oil goods imports", exog=[], fiscal=False,
                   durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                   slider=dict(min=-2, max=2, step=0.25), fmt="tariff",
                   blurb="A tariff on imported goods other than oil at the chosen rate for the chosen period: the duties go to the Treasury, consumers pay half of them through prices over about seven months, businesses pay half the duty on imported equipment, company profits absorb the rest, and the tariff-inclusive price holds imports down."),
    "immig": dict(label="Immigration", unit="1% of the working-age population (engine: +1 = 1% SMALLER)", exog=[], fiscal=False,
                  durs=DURS, default_dur="q4", fed_options=FED_OPTIONS, page_sign=-1, default_size=-1,
                  slider=dict(min=-2, max=2, step=0.25), fmt="pop",
                  blurb="The working-age population is larger or smaller by the chosen percentage (1 percent is about 3 million people) for the chosen period, so the labor force and potential output move with it."),
    "expect": dict(label="Inflation expectations", unit="1 point on long-run expected inflation", exog=["ptr"], fiscal=False,
                   durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                   slider=dict(min=-2, max=2, step=0.25), fmt="pp",
                   blurb="Long-run expected inflation (the 10-year expectation in the Survey of Professional Forecasters, which anchors price setting in the model) moves by the chosen amount for the chosen period."),
    "credit": dict(label="Credit spreads", unit="1 point on corporate bond spreads", exog=["rbbbp"], fiscal=False,
                   durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                   slider=dict(min=-2, max=2, step=0.25), fmt="pp",
                   blurb="The risk premium on BBB corporate bonds moves by the chosen amount for the chosen period; a widening is a financial-stress shock that raises business borrowing costs and the equity premium with it."),
    # added 2026-11-07: business investment, ±2% of GDP, with the share imported 0-100%. The data-center study's
    # split model (invest_model.py): the added investment is exogenous (edc) on top of the Board's own investment
    # equation, its imported part likewise on top of imports (emdc), GDP weights corrected (dcw = 1), and the new
    # capital NOT counted in capacity (kdcsw = 0: a demand shock). Two runs are stored, all made at home (`invest`) and all
    # imported (`investimp`, hidden from the menu); the page mixes them for 25, 50 and 75 percent imported, which is exact
    # up to the model's small nonlinearity (checked against direct runs, README).
    "invest": dict(label="Business investment", unit="1% of GDP, none of it imported", exog=[], fiscal=False, model="invest", imported=0.0,
                   durs=DURS, default_dur="q4", fed_options=FED_OPTIONS,
                   slider=dict(min=-2, max=2, step=0.25), fmt="gdp",
                   blurb="Business investment changes by the chosen share of GDP for the chosen period, with the share of the equipment that is imported set separately; the new capital is not counted as adding to productive capacity."),
    "investimp": dict(label="Business investment (all imported)", unit="1% of GDP, all of it imported", exog=[], fiscal=False, model="invest", imported=1.0,
                      durs=DURS, default_dur="q4", fed_options=FED_OPTIONS, hidden=True, mix_of="invest",
                      slider=dict(min=-2, max=2, step=0.25), fmt="gdp",
                      blurb="The business-investment shock with all of the equipment imported; the page mixes it with the all-domestic run."),
}
TARIFF = 0.10            # the unit tariff rate
# The tariff is on GOODS only (2026-11-09: "Yes, goods only").
# FRB/US's duty base, `emon`, is non-oil imports of goods AND services, so the duty is scaled by goods' share of it:
# E = TARIFF x size x GOODS_SHARE x baseline emon. GOODS_SHARE = non-petroleum goods imports / (non-petroleum goods +
# services imports), BEA NIPA Table 4.2.5B (LastRevised October 29, 2026; read 2026-11-09), 2024, the last full year
# before the 2025 tariffs and the year CAPITAL_SHARE in tariff.py is read for: imports of nonpetroleum goods (A187RC)
# $3,011.8 billion / ($3,011.8 + imports of services (B656RC) $835.0 billion) = 0.783 (2025: 3,133.1 / 4,048.9 = 0.774).
# Their sum is FRB/US's emon for 2024 in the Board's data package to the decimal ($3,846.8 billion). Duty base at the
# 2040Q1 baseline: 1.11 percent of GDP for a 10 percent tariff (1.43 before, when services were taxed too). The tariff
# construction itself, tariff.channels() and its parameters, is unchanged.
GOODS_SHARE = 0.78
NEW_SHOCKS = ("realloc", "tariff", "immig", "expect", "credit")

# ---- what is stored for every run -------------------------------------------------------------------
# kind: pp = percentage points (level difference); pct = percent difference; gdp = pp of GDP; usd = dollars
VARS = [
    ("xgdp", "Real GDP", "pct", "top"),
    ("lur", "Unemployment rate", "pp", "top"),
    ("picx4", "Core PCE inflation (4-quarter)", "pp", "top"),
    ("rff", "Federal funds rate", "pp", "top"),
    ("xgdpn", "Nominal GDP", "pct", "activity"),      # added 2026-11-11, at a reader's request
    ("xgap2", "Output gap", "pp", "activity"),
    ("ecnia", "Consumer spending", "pct", "activity"),
    ("ebfi", "Business investment", "pct", "activity"),
    ("eh", "Residential investment", "pct", "activity"),
    ("ex", "Exports", "pct", "activity"),
    ("em", "Imports", "pct", "activity"),
    ("xgdpt", "Potential GDP", "pct", "activity"),
    ("leh", "Employment", "pct", "labor"),
    ("lfpr", "Labor force participation rate", "pp", "labor"),
    ("realwage", "Real compensation per hour", "pct", "labor"),
    ("pic4", "PCE inflation (4-quarter)", "pp", "prices"),
    ("picxfe", "Core PCE inflation (quarterly, annualized)", "pp", "prices"),
    ("pgdp", "GDP price index", "pct", "prices"),      # added 2026-11-11, with nominal GDP
    ("ptr", "Long-run expected inflation", "pp", "prices"),
    ("poil", "Oil price", "usd", "prices"),
    ("rg10", "10-year Treasury yield", "pp", "rates"),
    ("rg10p", "10-year term premium", "pp", "rates"),
    ("rrff", "Real federal funds rate", "pp", "rates"),
    ("rme", "Mortgage rate", "pp", "rates"),
    ("rbbb", "BBB corporate bond yield", "pp", "rates"),
    ("wpsn", "Stock market wealth", "pct", "assets"),
    ("phouse", "House prices", "pct", "assets"),
    ("fpxr", "Real value of the dollar", "pct", "assets"),
    ("gov", "Federal purchases", "gdp", "fiscal"),
    ("transfers", "Government transfers", "gdp", "fiscal"),
    ("taxrate", "Personal tax rate", "pp", "fiscal"),
    ("surplus", "Federal budget balance", "gdp", "fiscal"),
    ("debt", "Federal debt held by the public", "gdp", "fiscal"),
    ("curacct", "Current account balance", "gdp", "fiscal"),
]
VAR_IDS = [v[0] for v in VARS]
NEEDED = ["xgdp", "lur", "picx4", "rff", "xgap2", "ecnia", "ebfi", "eh", "ex", "em", "xgdpt", "leh", "lfpr", "pl", "pcnia",
          "pic4", "picxfe", "ptr", "poil", "rg10", "rg10p", "rrff", "rme", "rbbb", "wpsn", "phouse", "fpxr", "egfen", "gtn",
          "trp", "gfsrpn", "gfdbtnp", "fcbn", "xgdpn", "trci", "egfe", "gtrt", "reqp", "mfpt", "pgdp", "ypn"]

def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")

# ---- model helpers (each worker process builds its own) -----------------------------------------------
_DATA = None
def data():
    global _DATA
    if _DATA is None:
        from pyfrbus.load_data import load_data
        _DATA = load_data(DATA)
    return _DATA

_COEF = None
def coef(name):
    """The coefficients of one equation, read from model.xml (an equation replaced through append_replace
    has to carry its numbers inline — the y_* names are not series in the data)."""
    global _COEF
    if _COEF is None:
        import xml.etree.ElementTree as ET
        _COEF = {}
        for v in ET.parse(MODEL).getroot().findall("variable"):
            n = (v.findtext("name") or "").strip()
            _COEF[n] = {c.findtext("cf_name").replace("(", "_").replace(")", ""): float(c.findtext("cf_value")) for c in v.iter("coeff")}
    return _COEF[name]

_MCE_COEF = {}
def mce_coef(name):
    """The coefficients of an equation's FORWARD-LOOKING (mce_equation) form. `coef()` cannot be used for these: an
    expectations equation numbers both forms y_<name>_1, y_<name>_2, ..., so its dict mixes the two."""
    if name not in _MCE_COEF:
        import xml.etree.ElementTree as ET
        for v in ET.parse(MODEL).getroot().findall("variable"):
            if (v.findtext("name") or "").strip() == name:
                me = v.find("mce_equation")
                _MCE_COEF[name] = {c.findtext("cf_name").replace("(", "_").replace(")", ""): float(c.findtext("cf_value")) for c in me.iter("coeff")}
                break
        else:
            raise KeyError(name)
    return _MCE_COEF[name]

def trp_equation():
    """The personal tax rate with a policy shift `evtax` (an exogenous series we add to the data). The shift enters as
    a shift to the TREND rate and is netted out of the lag terms, so trp = (its own path) + evtax in every quarter;
    added as a plain add factor it would compound through the 0.60 and 0.24 lag coefficients to about 6x."""
    c = coef("trp")
    return (f"trp - trp_aerr = {c['y_trp_1']}*(trpt + evtax) + {c['y_trp_2']}*((trp(-1)-evtax(-1))-trpt(-1))"
            f" + {c['y_trp_3']}*((trp(-2)-evtax(-2))-trpt(-2)) + {c['y_trp_4']}*xgap2")

def model_xml(shock):
    """The Board's model.xml, or for the investment shock the split model (invest_model.py), built on first use."""
    if SHOCKS.get(shock, {}).get("model") == "invest":
        import invest_model
        return invest_model.ensure()
    return MODEL

def make_model(rule, exog, exp, tax=False, xml=None, capital_price=False):
    from pyfrbus.frbus import Frbus
    f = Frbus(xml or MODEL, mce=("mcap+wp" if exp == "mce" else None))
    eqs = {"rffrule": f"rffrule - rffrule_aerr = dmpex*rfffix + (1-dmpex)*{RULES[rule]}"}
    if tax: eqs["trp"] = trp_equation()
    if capital_price:          # the tariff: the relative price of investment on its own path (tariff.PBFIR_EQUATION)
        import tariff
        eqs["pbfir"] = tariff.PBFIR_EQUATION
    f.append_replace(eqs)
    if exog: f.exogenize(list(exog))
    return f

def policy_off(d, s, e):
    for k in ["dmpintay", "dmptay", "dmpalt", "dmprr", "dmptlr", "dmptrsh"]:
        d.loc[s:e, k] = 0
    d.loc[s:e, "dmpex"] = 0
    d.loc[s:e, "rfffix"] = d.loc[s:e, "rff"]

def baseline_frame(elb, fiscal, end, shock=None, exp="var"):
    d = data().copy()
    if exp == "mce":           # forward-looking runs: the rule's r* learns from the real funds rate (the Board's option)
        d.loc[START:end, "drstar"] = 1
    if SHOCKS.get(shock, {}).get("model") == "invest":
        import invest_model
        d = invest_model.add_series(d)
    if shock == "tariff":
        import tariff
        d = tariff.prepare(d)
    d["evtax"] = 0.0
    policy_off(d, START, end)
    if elb == "yes":
        d.loc[START:end, "rffmin"] = d.loc[START:end, "rff"].values     # placeholder; config_task sets the exact floor after init_trac
    if fiscal == "fixed":
        d.loc[START:end, "dfpdbt"] = 0; d.loc[START:end, "dfpsrp"] = 0; d.loc[START:end, "dfpex"] = 1
        d.loc[START:end, "trptx"] = d.loc[START:end, "trpt"].values
    else:
        d.loc[START:end, "dfpdbt"] = 1; d.loc[START:end, "dfpsrp"] = 0; d.loc[START:end, "dfpex"] = 0
    return d

SOLVES = [0]             # model solves in this process (each worker counts its own and reports it)

def solve(f, s, e, frame, exp, retry=False):
    """Solve. A forward-looking run that does not converge in the default iterations is recorded as failed
    rather than retried: a retry with the trust-region solver took minutes per run and rarely helped
    (the 2026-10-27 overnight build stalled on exactly those retries)."""
    SOLVES[0] += 1
    if exp == "mce":
        if retry:          # --retry-failed: the patient solver, on the few runs the fast pass gave up on
            return f.solve(s, e, frame, {"newton": "trust", "maxiter": 100})
        return f.solve(s, e, frame, {"maxiter": 40})
    try:
        return f.solve(s, e, frame)
    except Exception:
        SOLVES[0] += 1
        return f.solve(s, e, frame, {"newton": "newton"})

def deviations(sim, wa, s, n):
    """The stored series: differences from baseline over quarters s .. s+n-1."""
    idx = pd.period_range(s, periods=n)
    A, B = sim.loc[idx], wa.loc[idx]
    out = {}
    pct = lambda v: (100 * (A[v] / B[v] - 1)).values
    pp = lambda v: (A[v] - B[v]).values
    gdp = lambda num: (100 * (A[num] / A["xgdpn"] - B[num] / B["xgdpn"])).values
    for v, _, kind, _ in VARS:
        if v == "realwage": x = 100 * ((A["pl"] / A["pcnia"]) / (B["pl"] / B["pcnia"]) - 1); x = x.values
        elif v == "gov": x = gdp("egfen")
        elif v == "transfers": x = gdp("gtn")
        elif v == "taxrate": x = 100 * pp("trp")
        elif v == "lfpr": x = 100 * pp("lfpr")    # FRB/US holds lfpr as a fraction (0.618); before 2026-11-11 it was stored unscaled
        elif v == "surplus": x = gdp("gfsrpn")
        elif v == "debt": x = gdp("gfdbtnp")
        elif v == "curacct": x = gdp("fcbn")
        elif kind == "pct": x = pct(v)
        elif kind == "usd": x = pp(v)
        else: x = pp(v)
        out[v] = [None if (isinstance(t, float) and not math.isfinite(t)) else round(float(t), 3) for t in x]
    return out

def apply_shock(shock, frame, wa, size, dur, fed, calib, end=None, exp="var"):
    """Put the shock (and the Fed's hold, if any) into a copy of the baseline-with-adds frame. A permanent shock
    (dur = PERM) runs through `end`, the last quarter solved. `exp` matters only for the tariff's price channel."""
    s = frame
    q0 = START
    n = dur if dur else 0
    if end is not None:
        n = min(n, (end - START).n + 1)
    q1 = START + max(n, 1) - 1
    # A peg must land the funds rate exactly on its target. rff = max(rffrule, rffmin) + rff_trac and, with dmpex = 1,
    # rffrule = rfffix + rffrule_trac (pyfrbus appends each equation's tracking residual to its right-hand side), so
    # rfffix nets both residuals out. Setting rfffix to the target itself let them leak through: 0.04 point in the
    # Board's baseline for the inertial rule, 0.3 point in the fifth quarter for the balanced, Taylor and
    # first-difference configurations (fixed 2026-10-31).
    def peg(a, b, target):
        return target - wa.loc[a:b, "rff_trac"].values - wa.loc[a:b, "rffrule_trac"].values
    if shock == "fed":
        s.loc[q0:q1, "dmpex"] = 1
        s.loc[q0:q1, "rfffix"] = peg(q0, q1, wa.loc[q0:q1, "rff"].values + size)
    else:
        if fed in HOLDS:
            h1 = START + HOLDS[fed] - 1
            s.loc[q0:h1, "dmpex"] = 1
            s.loc[q0:h1, "rfffix"] = peg(q0, h1, wa.loc[q0:h1, "rff"].values)
        if shock == "gov":
            s.loc[q0:q1, "egfe"] = wa.loc[q0:q1, "egfe"].values + size * 0.01 * wa.loc[q0:q1, "xgdp"].values
        elif shock == "tax":
            s.loc[q0:q1, "evtax"] = -size * 0.01 * (wa.loc[q0:q1, "xgdpn"] / (wa.loc[q0:q1, "ypn"] - wa.loc[q0:q1, "gtn"])).values
        elif shock == "transfers":
            s.loc[q0:q1, "gtrt"] = wa.loc[q0:q1, "gtrt"].values + size * 0.01
        elif shock == "oil":
            s.loc[q0:q1, "poil"] = wa.loc[q0:q1, "poil"].values + size * 25.0
        elif shock == "dollar":
            s.loc[q0:q1, "fpxr"] = wa.loc[q0:q1, "fpxr"].values * (1 + size * 0.10)
        elif shock == "stocks":
            # size n = stock wealth (1 - 0.1n) times baseline on impact, EXACTLY (+3 = a 30% fall, -3 = a 30% rise): the
            # equity-premium shift is linear in the LOG of wealth, so a linear scale would give -27% and +37% at ±3
            # (2026-11-07: sizes to ±30%). Size 1 is the calibration itself, unchanged.
            if 1 - 0.1 * size <= 0:
                raise ValueError(f"stocks size {size}: a fall of 100% or more")
            shift = calib["reqp_per_10pct"] * math.log(1 - 0.1 * size) / math.log(0.9)
            s.loc[q0:q1, "reqp"] = wa.loc[q0:q1, "reqp"].values + shift
        elif shock == "stocks_earn":
            # Investors expect faster (slower) growth of real dividends: zdivgr, shifted through its add factor with its
            # equation kept. zdivgr enters only the stock-wealth equation, log(wpsn) = ... - 0.25*(req - zdivgr), so this
            # version works through household wealth alone; the premium version (`stocks`) also moves req, half of the
            # business cost of capital rbfi. Same scale as the premium version: size n = stock wealth (1 - 0.1n) x
            # baseline on impact, exactly with backward-looking expectations (`calibrate_earnings`), in logs.
            if 1 - 0.1 * size <= 0:
                raise ValueError(f"stocks_earn size {size}: a fall of 100% or more")
            x = calib["zdivgr_per_10pct"] * math.log(1 - 0.1 * size) / math.log(0.9)   # points of expected dividend growth
            add = np.full(len(pd.period_range(q0, q1)), x)
            if exp == "mce":
                # Forward-looking, zdivgr = a*hgynid(+1) + b*zdivgr(+1) + add factor (b = 0.990): the recursion sums the
                # add factor over the future, so a plain x would be about 4x on impact for a year and 100x for good.
                # The add factor x_t - b*x_(t+1) makes expected dividend growth exactly x above the model's own
                # expectation in each quarter the shock is in force — the same belief as the backward-looking version.
                add[:-1] = x * (1 - mce_coef("zdivgr")["y_zdivgr_2"])
            s.loc[q0:q1, "zdivgr_aerr"] = wa.loc[q0:q1, "zdivgr_aerr"].values + add
        elif shock == "termprem":
            s.loc[q0:q1, "rg10p"] = wa.loc[q0:q1, "rg10p"].values + size * 1.0
        elif shock == "realloc":
            s.loc[q0:q1, "lurnat"] = wa.loc[q0:q1, "lurnat"].values + size * 1.0
        elif shock == "tariff":
            # The tariff construction in tariff.py (tariff.channels; 2026-11-08: companies bear half the duty; the
            # long run negative). E = the duty, the tariff rate x baseline non-oil GOODS imports ($bn a year; emon x
            # GOODS_SHARE, since emon includes services — 2026-11-09), while the tariff is in force: federal customs
            # receipts; consumers pay half through prices on the Fed staff's ~7-month schedule;
            # businesses buying equipment pay half the duty on capital goods (29% of it) through the price of investment,
            # which is also held on its own path; profits absorb the rest; the tariff-inclusive price holds imports down.
            # The import price pmo is NOT moved (it is measured before duties; moving it counts the duty twice).
            import tariff as RT
            last = end if end is not None else q1 + 8
            e = pd.Series(0.0, index=pd.period_range(q0, last))
            e.loc[q0:q1] = size * TARIFF * GOODS_SHARE * wa.loc[q0:q1, "emon"].values
            RT.channels(s, wa, e, sign=+1, forward=(exp == "mce"))
        elif shock == "immig":
            s.loc[q0:q1, "n16"] = wa.loc[q0:q1, "n16"].values * (1 - size * 0.01)
        elif shock == "expect":
            s.loc[q0:q1, "ptr"] = wa.loc[q0:q1, "ptr"].values + size * 1.0
        elif shock == "credit":
            s.loc[q0:q1, "rbbbp"] = wa.loc[q0:q1, "rbbbp"].values + size * 1.0
        elif SHOCKS[shock].get("model") == "invest":
            # the data-center construction (invest_model.py): `size` percent of baseline nominal GDP of added business
            # investment at baseline prices, and the imported share of it as added non-oil imports
            ngdp = wa.loc[q0:q1, "xgdpn"].values
            s.loc[q0:q1, "edc"] = size * 0.01 * ngdp / (0.01 * wa.loc[q0:q1, "pbfir"].values * wa.loc[q0:q1, "pxp"].values)
            s.loc[q0:q1, "emdc"] = SHOCKS[shock]["imported"] * size * 0.01 * ngdp / (0.01 * wa.loc[q0:q1, "pmo"].values)
        elif shock == "mfp":
            if n <= 4:      # one year: a one-time 1 percent rise in the level (the Board's standard shock)
                s.loc[q0, "mfpt_aerr"] = s.loc[q0, "mfpt_aerr"] + size * 0.01
            else:           # longer: trend MFP growth 1 point a year faster for n quarters (permanent = the whole horizon)
                s.loc[q0:q1, "hmfpt"] = wa.loc[q0:q1, "hmfpt"].values + size * 1.0
    return s

def run_key(size, fed, dur, exp, elb, fiscal):
    return f"{size:g}|{fed}|{dur}"

def file_key(shock, exp, elb, fiscal):
    return f"{shock}_{exp}_{elb}_{fiscal}"

def config_task(task):
    """One model configuration (shock, rule, exp, elb, fiscal) and all the runs it serves. Runs in a worker."""
    shock, rule, exp, elb, fiscal, sizes, durs, feds, calib = (task[k] for k in ["shock", "rule", "exp", "elb", "fiscal", "sizes", "durs", "feds", "calib"])
    out, failed = {}, []
    t0 = time.time()
    try:
        end = MCE_END if exp == "mce" else VAR_END
        f = make_model(rule, SHOCKS[shock]["exog"], exp, tax=(shock == "tax"), xml=model_xml(shock), capital_price=(shock == "tariff"))
        wa = f.init_trac(START, end, baseline_frame(elb, fiscal, end, shock, exp))
        if elb == "yes":
            # The floor must bind exactly at the baseline. rff = max(rffrule, rffmin) + rff_trac, and the Board's
            # baseline is not exactly on its own rule (rff_trac is -0.04 in one quarter), so a floor at the baseline
            # FUNDS RATE let that residual leak through as a small cut. The floor at the baseline's RULE rate,
            # rff - rff_trac, reproduces the baseline when nothing happens and holds the rate exactly there when
            # the rule wants to cut.
            wa.loc[START:end, "rffmin"] = (wa.loc[START:end, "rff"] - wa.loc[START:end, "rff_trac"]).values
            # The floor lasts ELB_FLOOR_QUARTERS (30 years, the length of the solve before 2026-11-08), then lifts: with the
            # forward-looking solve extended to 200 quarters, a floor for all 50 years left a third of these runs unsolved.
            wa.loc[START + ELB_FLOOR_QUARTERS:end, "rffmin"] = -99.0
    except Exception as e:
        return dict(task=task, runs={}, failed=[("config", repr(e))], secs=time.time() - t0)
    SOLVES[0] = 0
    wanted = task.get("only") or [(size, fed, dur_id) for fed in feds for dur_id in durs for size in sizes]
    for size, fed, dur_id in wanted:
        if True:
            if True:
                key = run_key(size, fed, dur_id, exp, elb, fiscal)
                try:
                    frame = apply_shock(shock, wa.copy(), wa, size, SHOCKS[shock]["durs"][dur_id], fed, calib, end=end, exp=exp)
                    sim = solve(f, START, end, frame, exp, retry=task.get("retry", False))
                    out[key] = deviations(sim, wa, START, H + 1)
                except Exception as e:
                    failed.append((key, repr(e).split("\n")[0][:200]))
    return dict(task=task, runs=out, failed=failed, secs=time.time() - t0, solves=SOLVES[0])

def calibrate_stocks():
    """The equity-premium shift that cuts stock-market wealth 10 percent on impact (VAR, 8 quarters, taxes fixed)."""
    f = make_model("inertial", ["reqp"], "var")
    wa = f.init_trac(START, VAR_END, baseline_frame("no", "fixed", VAR_END))
    s = wa.copy(); s.loc[START:START + 7, "reqp"] = wa.loc[START:START + 7, "reqp"].values + 0.4
    sim = f.solve(START, VAR_END, s)
    drop = 100 * (sim.loc[START, "wpsn"] / wa.loc[START, "wpsn"] - 1)
    return round(0.4 * (-10.0 / drop), 4), round(float(drop), 3)

def calibrate_earnings():
    """The shift in expected real dividend growth (zdivgr's add factor, percentage points; negative) that cuts
    stock-market wealth 10 percent on impact, in the premium calibration's setting (VAR, 8 quarters, inertial rule, taxes
    fixed). The wpsn equation alone gives 4 x log(0.9); two passes in logs take in the first quarter's other responses.
    Returns (shift, the move it gives in percent, solves made)."""
    f = make_model("inertial", [], "var")
    wa = f.init_trac(START, VAR_END, baseline_frame("no", "fixed", VAR_END))
    def impact(x):
        s = wa.copy()
        s.loc[START:START + 7, "zdivgr_aerr"] = wa.loc[START:START + 7, "zdivgr_aerr"].values + x
        sim = f.solve(START, VAR_END, s)
        return math.log(sim.loc[START, "wpsn"] / wa.loc[START, "wpsn"])
    x = 4 * math.log(0.9)
    for _ in range(2):
        x *= math.log(0.9) / impact(x)
    x = round(x, 5)
    return x, round(100 * (math.exp(impact(x)) - 1), 4), 3

def baseline_values():
    d = data().loc[START]
    return {k: round(float(v), 3) for k, v in {
        "rff": d["rff"], "lur": d["lur"], "picx4": d["picx4"], "pic4": d["pic4"], "rg10": d["rg10"], "rstar": d["rstar"],
        "lurnat": d["lurnat"], "pitarg": d["pitarg"], "poil": d["poil"], "debt": 100 * d["gfdbtnp"] / d["xgdpn"],
        "surplus": 100 * d["gfsrpn"] / d["xgdpn"], "gov": 100 * d["egfen"] / d["xgdpn"], "transfers": 100 * d["gtn"] / d["xgdpn"],
        "taxrate": 100 * d["trp"], "xgap2": d["xgap2"], "rffmin": d["rffmin"]}.items()}

# ---- counting the work (2026-10-31: the page's note says how many scenarios are pre-solved and how many
# model runs it took). Every solve the engine makes is counted per build into engine/solve_log.json (git-tracked);
# meta.json carries the totals. Builds before the counter existed (2026-10-26 to 2026-10-31) are an ESTIMATE,
# reconstructed from that week's builds: quick builds, two full builds, the lower-bound floor fix, the permanent
# shocks and the peg fix (every hold and Fed peg recomputed), the forward-looking rebuilds and the retry pass.
SOLVE_LOG = HERE / "solve_log.json"
LIBRARY_SOLVES_BEFORE_LOG = 13800      # approximate; see above

def record_solves(tally, args):
    log_ = json.loads(SOLVE_LOG.read_text()) if SOLVE_LOG.exists() else {"builds": []}
    if tally["library"]:
        log_["builds"].append({"date": time.strftime("%Y-%m-%d"), "time": time.strftime("%H:%M"),
                               "args": {k: v for k, v in vars(args).items() if v not in (False, "", None)},
                               "library_solves": tally["library"]})
    SOLVE_LOG.write_text(json.dumps(log_, indent=1) + "\n")
    if (OUT / "meta.json").exists():
        meta = json.loads((OUT / "meta.json").read_text())
        meta["counts"] = counts()
        (OUT / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")

def counts():
    """Pre-solved scenarios in the library, the ones that did not solve, and the model runs it took."""
    presolved = unsolved = 0
    for path in (OUT / "runs").glob("*.json"):
        body = json.loads(path.read_text())
        presolved += len(body["runs"]); unsolved += len(body["failed"])
    builds = json.loads(SOLVE_LOG.read_text())["builds"] if SOLVE_LOG.exists() else []
    logged = sum(b["library_solves"] for b in builds)
    return {"presolved": presolved, "unsolved": unsolved, "library_solves_logged": logged,
            "library_solves_before_log": LIBRARY_SOLVES_BEFORE_LOG,
            "library_solves_total_approx": logged + LIBRARY_SOLVES_BEFORE_LOG,
            "note": "Pre-solved = stored runs; unsolved = combinations attempted that did not converge. Solves are counted by the engine since 2026-10-31; the earlier 13,800 is an estimate reconstructed from that week's builds."}

# ---- orchestration -----------------------------------------------------------------------------------
# Which model made these runs. Every run in data/ comes from FRB/US on one Board package (`vintage`, copied from
# VINTAGE.json); the label is there so that runs from a second model, if one is ever added (it would get its
# own engine folder and its own files), can never be mixed with these.
MODEL_NAME = "FRB/US"

def build_meta(calib, vintage, stats):
    return {
        "built": time.strftime("%Y-%m-%d"),
        "model": MODEL_NAME,
        "vintage": vintage,
        "baseline": dict(start=str(START), horizon=H, **baseline_values()),
        "shocks": [dict(id=k, label=v["label"], unit=v["unit"], fmt=v["fmt"], blurb=v["blurb"], fiscal=True,
                        durations=[dict(id=d, quarters=(None if q == PERM else q)) for d, q in v["durs"].items()], default_dur=v["default_dur"],
                        fed_options=v["fed_options"], slider=v["slider"], sizes=v.get("sizes", SIZES),
                        page_sign=v.get("page_sign", 1), default_size=v.get("default_size", 1),
                        **{x: v[x] for x in ("hidden", "mix_of", "imported", "variant_of") if x in v}) for k, v in SHOCKS.items()],
        "sizes": sorted({z for v in SHOCKS.values() for z in v.get("sizes", SIZES)}),   # every stored size (stocks go to ±3)
        "fed": [dict(id="hold4", label="Holds the rate for 1 year", short="Holds 1 year"), dict(id="hold8", label="Holds the rate for 2 years", short="Holds 2 years"),
                dict(id="hold12", label="Holds the rate for 3 years", short="Holds 3 years"),
                dict(id="inertial", label="Inertial rule (FRB/US’s own rule)", short="Inertial rule"),
                dict(id="balanced", label="Balanced-approach rule", short="Balanced approach"),
                dict(id="taylor93", label="Taylor (1993) rule", short="Taylor (1993)"),
                dict(id="firstdiff", label="First-difference rule", short="First difference")],
        "exp": [dict(id="var", label="Backward-looking (VAR), the Board’s default", short="Backward-looking"),
                dict(id="mce", label="Forward-looking (model-consistent in financial markets and wage-price setting)", short="Forward-looking")],
        "elb": [dict(id="no", label="Normal times", short="Normal times"), dict(id="yes", label="At the lower bound: the Fed can raise but not cut", short="At the lower bound")],
        "fiscal": [dict(id="fixed", label="Taxes fixed: the shock is deficit-financed and nothing pays for it within the horizon", short="Taxes fixed"),
                   dict(id="debt", label="The Board’s debt rule: the personal tax rate rises to stabilize the debt ratio", short="Debt rule")],
        "vars": [dict(id=i, label=l, kind=k, group=g) for i, l, k, g in VARS],
        "top": ["xgdp", "lur", "picx4", "rff"],
        "calibration": calib,
        "unavailable": [dict(shock="fed", exp="mce", dur="perm",
                             why="Under forward-looking expectations a permanent rate peg has no unique answer: with the rate fixed forever, nothing pins down expected inflation (the textbook indeterminacy result), and the model’s answer flips sign with the financing assumption. The permanent Fed shock is backward-looking only.")],
        "stats": stats,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="VAR only, sizes ±1, default durations: a development build")
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4)))
    ap.add_argument("--shocks", default="", help="comma-separated subset of shock ids")
    ap.add_argument("--exp", default="", help="var, mce or both (default both)")
    ap.add_argument("--elb", default="", help="no, yes or both (default both)")
    ap.add_argument("--fiscal", default="", help="fixed, debt or both (default both)")
    ap.add_argument("--force", action="store_true", help="rerun configurations whose runs are already in their files")
    ap.add_argument("--retry-failed", action="store_true",
                    help="re-solve only the runs each file lists as failed, with the trust-region solver. Measured 2026-10-31: it "
                         "rescued 4 of 37 forward-looking permanent runs in two hours (20-90 minutes per configuration), so the "
                         "failures are the model's, not the fast solver's; do not run it again without a new idea")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    vintage = json.loads((FED / "VINTAGE.json").read_text()) if (FED / "VINTAGE.json").exists() else {}
    try:
        import multiprocess as mp
    except ImportError:
        import multiprocessing as mp
    t0 = time.time()
    tally = {"library": 0}
    if not args.quick:
        try:
            os.nice(10)  # a long CPU-saturating job yields to interactive work
        except OSError:  # already at the lowest priority (e.g. started under `nice -n 20`)
            pass
    log(f"build start quick={args.quick} workers={args.workers}")

    stats = {}
    reqp, drop = calibrate_stocks()
    tally["library"] += 1
    zd, zd_drop, zd_solves = calibrate_earnings()
    tally["library"] += zd_solves
    calib = {"reqp_per_10pct": reqp, "check_drop_at_0.4": drop, "zdivgr_per_10pct": zd, "check_earn_drop": zd_drop}
    log(f"stocks calibration: reqp +{reqp} per 10% fall (0.4 gave {drop}%); expected dividend growth {zd} per 10% fall (gives {zd_drop}%)")
    shocks = [s for s in SHOCKS if (not args.shocks or s in args.shocks.split(","))]
    exps = ["var"] if args.quick else [e for e in EXPS if (not args.exp or e in args.exp.split(","))]
    elbs = ["no"] if args.quick else [e for e in ELBS if (not args.elb or e in args.elb.split(","))]
    tasks = []
    for exp in exps:                       # backward-looking first (minutes), then forward-looking, the lower bound last
        for elb in elbs:
            for shock in shocks:
                sp = SHOCKS[shock]
                durs = [sp["default_dur"]] if args.quick else list(sp["durs"])
                if shock == "fed" and exp == "mce":
                    durs = [d for d in durs if d != "perm"]   # a permanent peg has no unique forward-looking answer
                fiscals = ["fixed"] if args.quick else [x for x in FISCALS if (not args.fiscal or x in args.fiscal.split(","))]
                for fiscal in fiscals:
                    if (exp, elb, fiscal) in DROPPED:
                        continue
                    for rule in RULE_IDS:
                        feds = [f for f in sp["fed_options"] if (f == rule) or (rule == "inertial" and f in HOLDS)]
                        if not feds: continue
                        sizes = [-1, 1] if args.quick else sp.get("sizes", SIZES)
                        # one task per Fed response, not per rule: the inertial rule also carries the three holds, and as
                        # one task it ran 64 forward-looking runs in a single worker (nearly two hours at the lower bound,
                        # 2026-11-08) while the other workers sat idle
                        for fed in feds:
                            tasks.append(dict(shock=shock, rule=rule, exp=exp, elb=elb, fiscal=fiscal, sizes=sizes, durs=durs, feds=[fed], calib=calib))
    if any(SHOCKS[t["shock"]].get("model") == "invest" for t in tasks):
        import invest_model
        log(f"split model for the investment shock: {invest_model.ensure()}")
    log(f"{len(tasks)} model configurations")
    (OUT / "runs").mkdir(exist_ok=True)
    def load_file(fk):
        path = OUT / "runs" / f"{fk}.json"
        if path.exists():
            try: return json.loads(path.read_text())
            except Exception: pass
        shock, exp, elb, fiscal = fk.rsplit("_", 3)      # rsplit: a shock id may hold an underscore (stocks_earn)
        return {"shock": shock, "exp": exp, "elb": elb, "fiscal": fiscal, "vars": VAR_IDS, "horizon": H, "runs": {}, "failed": []}
    def save_file(fk, body):
        path = OUT / "runs" / f"{fk}.json"
        path.write_text(json.dumps(body, separators=(",", ":")) + "\n")
        stats[fk] = {"runs": len(body["runs"]), "failed": len(body["failed"]), "bytes": path.stat().st_size}
    # resume: skip a configuration whose runs are all in its file already (--force reruns everything)
    if args.retry_failed:
        kept = []
        for t in tasks:
            body = load_file(file_key(t["shock"], t["exp"], t["elb"], t["fiscal"]))
            feds = set(t["feds"])
            again = [(int(k.split("|")[0]) if float(k.split("|")[0]).is_integer() else float(k.split("|")[0]), k.split("|")[1], k.split("|")[2])
                     for k, _ in body["failed"] if k.split("|")[1] in feds and k.split("|")[2] in t["durs"]]
            if again:
                kept.append(dict(t, only=again, retry=True))
        log(f"retrying {sum(len(t['only']) for t in kept)} failed runs in {len(kept)} configurations with the trust-region solver")
        tasks = kept
    elif not args.force:
        kept = []
        for t in tasks:
            body = load_file(file_key(t["shock"], t["exp"], t["elb"], t["fiscal"]))
            have = set(body["runs"]) | {k for k, _ in body["failed"]}
            missing = [(size, fed, dur) for fed in t["feds"] for dur in t["durs"] for size in t["sizes"]
                       if run_key(size, fed, dur, t["exp"], t["elb"], t["fiscal"]) not in have]
            if missing:
                t = dict(t, only=missing); kept.append(t)
        log(f"{len(tasks) - len(kept)} configurations already built, {len(kept)} to run ({sum(len(t['only']) for t in kept)} runs)")
        tasks = kept
    done = 0
    config_errors = []        # configurations that could not even be set up: none of their runs was attempted
    with mp.Pool(args.workers) as pool:
        for r in pool.imap_unordered(config_task, tasks):
            done += 1
            tally["library"] += r.get("solves", 0)
            t = r["task"]
            fk = file_key(t["shock"], t["exp"], t["elb"], t["fiscal"])
            body = load_file(fk)
            body["runs"].update(r["runs"])
            # A run that failed THIS time loses any result an earlier build stored under its key: under --force a run that
            # used to solve and now does not would otherwise keep its stale result beside the new failure (fixed 2026-11-09).
            for k, _ in r["failed"]: body["runs"].pop(k, None)
            failed = {k: e for k, e in body["failed"]}
            for k, e in r["failed"]: failed[k] = e
            for k in r["runs"]: failed.pop(k, None)
            body["failed"] = sorted(failed.items())
            save_file(fk, body)
            log(f"[{done}/{len(tasks)}] {t['shock']} {t['rule']} {t['exp']} elb={t['elb']} fiscal={t['fiscal']}: {len(r['runs'])} runs, {len(r['failed'])} failed, {r['secs']:.0f}s -> runs/{fk}.json")
            for k, e in r["failed"][:3]:
                log(f"    failed {k}: {e}")
            if any(k == "config" for k, _ in r["failed"]):
                config_errors.append(fk)
    for path in sorted((OUT / "runs").glob("*.json")):          # every file's counts, built now or earlier
        fk = path.stem
        if fk not in stats:
            body = json.loads(path.read_text())
            stats[fk] = {"runs": len(body["runs"]), "failed": len(body["failed"]), "bytes": path.stat().st_size}
    meta = build_meta(calib, vintage, stats)
    if (OUT / "meta.json").exists():                 # the record of deliberately dropped combinations survives a rebuild
        prev = json.loads((OUT / "meta.json").read_text())
        if prev.get("dropped"): meta["dropped"] = prev["dropped"]
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    log("wrote meta.json")
    import current_baseline           # the Board's baseline from the current quarter, which the page's levels sit on
    cb = current_baseline.write(OUT)
    log(f"wrote current.json (shock hits {cb['start']}, follows the {cb['sep']} SEP)")

    record_solves(tally, args)
    log(f"build done in {(time.time()-t0)/60:.1f} min ({tally['library']} library solves)")
    if config_errors:
        # a set-up error is a bug, not a run that did not solve: nothing was re-run, so whatever those files held
        # before (stale results under --force) is still there. Say so loudly and fail the command.
        log(f"ERROR: {len(config_errors)} configuration(s) failed before any run, their earlier runs were kept: {sorted(set(config_errors))}")
        sys.exit(1)

if __name__ == "__main__":
    main()
