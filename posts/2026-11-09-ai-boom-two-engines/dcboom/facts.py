"""facts.py: every number the post states, recomputed from the frozen data and the model runs, in one flat
dictionary (output/results/facts.json) that verify.py compares with the post. Keys are documented inline;
'pp' = percentage points, 'pct' = percent."""
import json
import re

import numpy as np
import pandas as pd

from . import common as C
from . import descriptive as D
from . import engine as E
from . import inputs as I
from . import paths


def _r(v):
    return None if v is None else round(float(v), 6)


def descriptive_facts(F):
    sh = D.buildout_shares()
    F["buildout_share_2026Q3"] = sh.loc["2026Q3", "total"]
    bea = I.bea()
    F["residential_share_gdp_2026Q3"] = 100 * bea.loc["2026Q3", "A011RC"] / bea.loc["2026Q3", "A191RC"]
    F["buildout_dollars_bn_2026Q3"] = sh.loc["2026Q3", "dollars_bn"]
    pre = sh.loc[:"2010Q4", "total"]
    F["buildout_peak_share_1990_2010"] = pre.max()
    F["buildout_peak_year_1990_2010"] = pre.idxmax().year
    F["buildout_2026Q3_minus_2000_peak"] = sh.loc["2026Q3", "total"] - pre.max()
    F["telecom_vn_avg_1996_2003"] = sh.loc["1996Q1":"2003Q4", "telecom_vn"].mean()
    b = D.capex_booms().set_index("episode")["avg_capex_pct_gdp"]
    for k, v in b.items():
        F[f"fig1_{k.lower().replace(' ', '_')}"] = v
    F["buildout_2026Q3_minus_vn_telecom_avg"] = sh.loc["2026Q3", "total"] - b["Telecom and fiber"]
    # stocks
    sg = D.stocks()
    base = sg.iloc[0]
    q3 = sg[sg.quarter == "2026Q3"].iloc[0]
    last = sg.iloc[-1]
    F["stocks_latest_date"] = last["date"]
    for tag, row in (("2026Q3", q3), ("latest", last)):
        F[f"seven_share_of_public_gain_{tag}"] = (row.sum7 - base.sum7) / (row.M_alt_public_ex_funds - base.M_alt_public_ex_funds)
        F[f"seven_index_{tag}"] = 100 * row.sum7 / base.sum7
        F[f"rest_index_{tag}"] = 100 * row.R_alt / base.R_alt
        F[f"extra_gain_tn_{tag}"] = row.G / 1e3
        F[f"household_extra_gain_tn_{tag}"] = row.H / 1e3
    F["seven_value_multiple_latest"] = F["seven_index_latest"] / 100
    F["rest_rise_fraction_latest"] = F["rest_index_latest"] / 100 - 1
    a = C.actual()
    ngdp = a.loc[C.Q, "ngdp"]                                           # $ trillions, 2026Q3 annual rate
    F["wealth_effect_bn"] = 0.03 * q3.H                                 # 3 percent of the households' part ($ billions)
    F["wealth_effect_pct_gdp"] = 100 * 0.03 * q3.H / 1e3 / ngdp
    F["tenth_pct_gdp_bn"] = 0.001 * ngdp * 1e3
    # investment shares
    inv = D.investment_shares()
    F["nonres_share_2026Q3"] = inv.loc["2026Q3", "nonres"]
    F["nonres_ex_share_2026Q3"] = inv.loc["2026Q3", "nonres_ex"]
    h = D.nonres_share_history()
    prev = h.iloc[:-1]
    F["nonres_share_highest_since_year"] = prev[prev >= h.iloc[-1]].index[-1].year
    F["fixed_ex_share_2023_24"] = inv.loc["2023Q1":"2024Q4", "fixed_ex"].mean()
    F["fixed_ex_share_2026Q3"] = inv.loc["2026Q3", "fixed_ex"]
    # construction
    con = D.construction_growth()
    for r in con.itertuples():
        k = re.sub(r"[^a-z0-9]+", "_", r.label.lower()).strip("_")
        F[f"construction_real_{k}"] = r.real
        F[f"construction_nominal_{k}"] = r.nominal
    F["ppi_construction_change_12m"] = con.attrs["ppi_change"]
    # trade
    tr = D.trade_ytd()
    for y in (2024, 2025, 2026):
        for c in ("total", "dc", "other"):
            F[f"trade_ytd_{c}_{y}"] = tr.loc[y, c]
    for y in tr.index:
        for c in ("total", "dc", "other"):
            F[f"fig5_{c}_{y}"] = tr.loc[y, c]
    for c in ("total", "dc", "other"):
        F[f"trade_ytd_{c}_change_2024_2026"] = tr.loc[2026, c] - tr.loc[2024, c]
    full = D.dc_goods_imports_full_year()
    F["dc_goods_imports_avg_2015_2023"] = full.loc[2015:2023].mean()
    F["dc_goods_imports_2026_ytd"] = tr.loc[2026, "dc_imports"]
    nx = D.nx_share_annual()
    F["nx_share_1998"] = nx.loc[1998]
    F["nx_share_1999"] = nx.loc[1999]
    F["nx_smallest_deficit_1999_2025"] = nx.loc[1999:2025].max()
    # the shock
    inv_ex = pd.read_csv(paths.OUT_INPUTS / "inv_excess.csv", index_col=0)
    s = inv_ex.loc["2023Q1":"2026Q3", "inv_excess_share"]
    pos = [q for q in s.index if (s.loc[q:] > 0.02).all()]
    F["boom_start_quarter"] = pos[0]
    F["dc_share_2026Q3"] = s.loc["2026Q3"]
    F["dc_share_2026Q4_extrapolated"] = inv_ex.loc["2026Q4", "inv_excess_share"]   # no data yet: past year's growth carried one quarter
    # the model file
    xml = paths.FED_MODEL_XML.read_text()
    F["frbus_behavioral_equations"] = len(re.findall(r"<equation_type>Behavioral</equation_type>", xml))
    F["frbus_equations"] = F["frbus_behavioral_equations"] + len(re.findall(r"<equation_type>Identity</equation_type>", xml))
    F["frbus_estimated_equations"] = len(re.findall(r"<estimation_statistics>", xml))   # an estimation sample and fit statistics
    # context: the economy when the boom began (the Board's baseline, and BEA)
    d = E.data()
    q = pd.Period("2024Q2", "Q")
    F["longbase_unemployment_gap_2024Q2"] = float(d.loc[q, "lur"] - d.loc[q, "lurnat"])
    F["core_pce_4q_2024Q2"] = a.loc[q, "core4"]


def model_facts(F):
    runs, ext, a = C.post_runs(), C.extend_runs(), C.actual()
    raw = C.post_runs_raw()
    Q = C.Q
    A, B = runs["A_s75"], runs["B_s75"]
    for name in ("A_s75", "B_s75", "C_s75"):
        F[f"run_ok_{name}"] = int(bool(raw["runs"].get(name, {}).get("ok")))
    for s, e in (("A", A), ("B", B)) + ((("C", runs["C_s75"]),) if "C_s75" in runs else ()):
        for v in ("xgdp", "lur", "rff", "rg10", "rme", "ecnia", "eh", "ebfio", "nx", "ca", "picx4", "fpxr", "wpsn", "dcinv"):
            F[f"{s}_{v}_2026Q3"] = e.loc[Q, v]
    for name, e in ext.items():
        for v in ("xgdp", "lur", "rff", "eh"):
            F[f"ext_{name}_{v}_2028Q4"] = e.loc[C.END, v]
        F[f"ext_{name}_xgdp_rise_2028"] = e.loc[C.END, "xgdp"] - e.loc[C.END - 4, "xgdp"]   # 2027Q4 to 2028Q4
    info = raw["runs"]["A_s75"]["info"]
    F["import_share_computers"] = info["type_shares"]["comp"]
    F["import_share_comm_equipment"] = info["type_shares"]["comm"]
    F["import_share_construction"] = info["type_shares"]["dcc"]
    F["import_share_cumulative"] = info["import_share_cum"]
    imported = E.import_share_series(0.75)[0]
    F["imported_pp_2026Q3"] = imported.loc[Q]
    F["import_ratio_2026Q3"] = imported.loc[Q] / a.loc[Q, "dc_share"]
    for s, e in (("A", A), ("B", B)):
        for k, v in C.waterfall_steps(a, e, imported).items():
            F[f"waterfall_{s}_{re.sub(r'[^a-z]+', '_', k.lower()).strip('_')}"] = v
    F["stock_gain_consumer_contrib_B_minus_A"] = F["waterfall_B_consumer_spending"] - F["waterfall_A_consumer_spending"]
    F["stock_gain_other_bi_contrib_B_minus_A"] = F["waterfall_B_other_business_investment"] - F["waterfall_A_other_business_investment"]
    # the model's consumer-spending effect of the stock gain over the back-of-the-envelope wealth effect (3 percent of
    # households' part of the gain, as a share of GDP): "noticeably smaller"
    F["stock_gain_consumer_over_envelope"] = F["stock_gain_consumer_contrib_B_minus_A"] / F["wealth_effect_pct_gdp"]
    # the real dollar in the results shown (backward-looking, the buildout alone and with the stock gain), through
    # 2026Q3: the largest move either way, percent
    F["fpxr_max_abs_AB_2023Q1_2026Q3"] = max(float(e.loc[:Q, "fpxr"].abs().max()) for e in (A, B))
    # housing: the stock-gain case's residential-investment gap by the end of 2028, as a multiple of 2026Q3's
    F["housing_gap_change_A_2026Q3_to_2028Q4"] = ext["A_s75"].loc[C.END, "eh"] - A.loc[Q, "eh"]
    F["housing_gap_multiple_B_2028Q4"] = ext["B_s75"].loc[C.END, "eh"] / B.loc[Q, "eh"]
    F["added_investment_B_pp"] = F["waterfall_B_data_center_spending"] + F["waterfall_B_other_business_investment"] + F["waterfall_B_housing"]
    # saving implied by the identity the post uses (current account = saving - investment), percent of GDP
    F["added_saving_B_pp"] = F["added_investment_B_pp"] + F["B_ca_2026Q3"]
    # other (non-data-center) imports pulled in by the stock gain: B's effect minus A's, percent of their level
    F["B_minus_A_other_imports_pct_2026Q3"] = B.loc[Q, "emoo"] - A.loc[Q, "emoo"]
    F["nx_B_minus_A_2026Q3"] = B.loc[Q, "nx"] - A.loc[Q, "nx"]
    qq = pd.period_range("2026Q1", "2026Q3", freq="Q")
    F["nx_actual_avg_2026Q1_Q3"] = a.loc[qq, "nx_share"].mean()
    F["nx_actual_avg_2024"] = a.loc["2024Q1":"2024Q4", "nx_share"].mean()
    for s, e in (("A", A), ("B", B)):
        w = (a.loc[qq, "nx_share"] - e.loc[qq, "nx"]).mean()
        F[f"nx_without_{s}_avg_2026Q1_Q3"] = w
        nx = D.nx_share_annual()
        F[f"nx_without_{s}_lowest_since_year"] = int(nx.loc[:2025][nx.loc[:2025] >= w].index[-1])
    F["nx_without_B_change_from_2024_actual"] = F["nx_without_B_avg_2026Q1_Q3"] - F["nx_actual_avg_2024"]
    F["nx_actual_change_2024_to_2026"] = F["nx_actual_avg_2026Q1_Q3"] - F["nx_actual_avg_2024"]
    # expectations
    if "C_s75" in runs:
        Cc = runs["C_s75"]
        F["C_minus_B_rg10_2026Q3"] = Cc.loc[Q, "rg10"] - B.loc[Q, "rg10"]
        # GDP lost to forward-looking expectations over the stock gain's addition to GDP (above 1 = "more than offset")
        F["C_offset_share_of_stock_gain_gdp_2026Q3"] = (B.loc[Q, "xgdp"] - Cc.loc[Q, "xgdp"]) / (B.loc[Q, "xgdp"] - A.loc[Q, "xgdp"])
    news, NJ = C.news_runs()
    F["news2026_prod05_did_not_solve"] = int("_did_not_solve" in NJ and abs(NJ["_did_not_solve"]["prod"] - 0.5) < 1e-9)
    for k, e in news.items():
        F[f"{k}_rg10_2026Q3"] = e.loc[Q, "rg10"]
        F[f"{k}_xgdp_2026Q3"] = e.loc[Q, "xgdp"]
        if "C_s75" in runs:
            Cc = runs["C_s75"]
            F[f"{k}_share_of_added_rate_rise"] = (e.loc[Q, "rg10"] - B.loc[Q, "rg10"]) / (Cc.loc[Q, "rg10"] - B.loc[Q, "rg10"])
            F[f"{k}_share_of_gdp_offset"] = (B.loc[Q, "xgdp"] - e.loc[Q, "xgdp"]) / (B.loc[Q, "xgdp"] - Cc.loc[Q, "xgdp"])


def reversal_facts(F):
    """The boom ending in 2027 (reversal.py): the paragraph after the table and the future section. 'Growth' is real
    GDP growth, fourth quarter over fourth quarter; 'holds' is the world in which the boom holds (the baseline)."""
    f = paths.OUT_RESULTS / "reversal_runs.json"
    if not f.exists():
        print("facts: output/results/reversal_runs.json is missing (run python run_all.py without --skip-runs); "
              "verify will fail the rows that need it")
        return
    H, W, _ = C.reversal_runs()
    if not W:
        print("facts: no reversal scenario solved; verify will fail the rows that need them")
        return
    P = lambda s: pd.Period(s, "Q")

    def growth(df, y):
        return 100 * (df.loc[P(f"{y}Q4"), "xgdp"] / df.loc[P(f"{y - 1}Q4"), "xgdp"] - 1)

    def vs_holds(df, q, v="xgdp"):                            # percent difference in level from the boom holding
        return 100 * (df.loc[P(q), v] / H.loc[P(q), v] - 1)
    after = pd.period_range("2027Q1", "2030Q4", freq="Q")      # every quarter solved after the boom ends
    for k, df in {"holds": H, **W}.items():
        for y in (2027, 2028):
            F[f"rev_growth_{k}_{y}"] = growth(df, y)
        x = df["xgdp"]
        F[f"rev_min_qgrowth_{k}"] = float((100 * ((x / x.shift(1)) ** 4 - 1)).loc[after].min())   # annualized
    for k, df in W.items():
        if k == "noboom":
            continue
        for y in (2027, 2028):
            F[f"rev_{k}_minus_holds_growth_{y}"] = F[f"rev_growth_{k}_{y}"] - F[f"rev_growth_holds_{y}"]
    bust_like = [k for k in ("bust", "build_ends", "bust_market30") if k in W]
    if bust_like:
        F["rev_min_qgrowth_busts"] = min(F[f"rev_min_qgrowth_{k}"] for k in bust_like)
    if "bust" in W and "mirror" in W:
        # symmetry: the bust as a share of the negative of the mirror (a second boom of the same size from 2027Q1),
        # in GDP's level each quarter 2027Q1-2028Q4 and in growth in 2027 and 2028, all measured from the boom holding
        r = [vs_holds(W["bust"], str(q)) / -vs_holds(W["mirror"], str(q)) for q in pd.period_range("2027Q1", "2028Q4", freq="Q")]
        r += [F[f"rev_bust_minus_holds_growth_{y}"] / -F[f"rev_mirror_minus_holds_growth_{y}"] for y in (2027, 2028)]
        F["rev_symmetry_ratio_min"], F["rev_symmetry_ratio_max"] = min(r), max(r)
    if "bust" in W and "noboom" in W:
        # faster: growth taken off in 2027 against the most growth the boom added in any year 2024-2026
        boom = [growth(H, y) - growth(W["noboom"], y) for y in (2024, 2025, 2026)]
        F["rev_boom_growth_effect_max_2024_2026"] = max(boom)
        F["rev_bust_faster_ratio"] = -F["rev_bust_minus_holds_growth_2027"] / max(boom)
    if "build_ends" in W:
        B = W["build_ends"]
        for v in ("xgdp", "ebfi", "em"):
            for q in ("2027Q4", "2028Q4"):
                F[f"rev_build_ends_{v}_{q}"] = vs_holds(B, q, v)
        for v in ("rff", "rg10"):
            for q in ("2027Q4", "2028Q4"):
                F[f"rev_build_ends_{v}_{q}"] = B.loc[P(q), v] - H.loc[P(q), v]
    if "bust_market30" in W:
        F["rev_bust_market30_wpsn_2027Q4"] = vs_holds(W["bust_market30"], "2027Q4", "wpsn")
        if "build_ends" in W:   # a broad market fall on top of the buildout ending, against the buildout ending alone
            F["rev_market30_vs_build_ends_growth_hit_2027"] = (F["rev_bust_market30_minus_holds_growth_2027"]
                                                               / F["rev_build_ends_minus_holds_growth_2027"])
    if "bust" in W and "build_ends" in W:
        # "the AI stock gains disappear": the bust's stock wealth against the world in which only the buildout ended,
        # as a share of the AI stock gain's share of market value, 2027Q1-2028Q4 (1 = exactly the AI gain, no more)
        f = E.stock_cut()
        r = [(1 - W["bust"].loc[q, "wpsn"] / W["build_ends"].loc[q, "wpsn"]) / f.loc[q]
             for q in pd.period_range("2027Q1", "2028Q4", freq="Q")]
        F["rev_bust_ai_gain_removed_min"], F["rev_bust_ai_gain_removed_max"] = min(r), max(r)
    if "noboom" in W:
        # the check: with the boom taken out from 2023Q1 the reversal runs are the post's world without the boom
        ext = C.extend_runs().get("B_s75")
        if ext is not None:
            nb, q = W["noboom"], ext.index
            gdp = 100 * (H.loc[q, "xgdp"] / nb.loc[q, "xgdp"] - 1)       # effects as runs.py measures them
            une = H.loc[q, "lur"] - nb.loc[q, "lur"]
            d = float(max((gdp - ext["xgdp"]).abs().max(), (une - ext["lur"]).abs().max()))
            F["rev_check_noboom_vs_post_extend"] = d
            print(f"facts: the reversal runs' world without the boom matches post_extend.json's B_s75 within {d:.1g}")
            if d > 5e-5:
                raise SystemExit(f"facts: the reversal runs' world without the boom differs from post_extend.json's B_s75 "
                                 f"by {d:.2g} (GDP or unemployment); the two should agree to the 5 decimals stored")


def table_facts(F):
    T = pd.read_csv(paths.OUT_RESULTS / "table_1_summary.csv")
    cols = {"actual": "actual", "without_buildout": "wo_build", "without_buildout_or_stock_gain": "wo_both",
            "effect_buildout": "eff_build", "effect_buildout_and_stock_gain": "eff_both"}
    for r in T.itertuples(index=False):
        rk = re.sub(r"[^a-z0-9]+", "_", r.row.lower()).strip("_")
        for c, ck in cols.items():
            F[f"table_{rk}_{ck}"] = getattr(r, c)


def figure_facts(F):
    G = json.loads((paths.OUT_RESULTS / "figure_data.json").read_text())
    for fig, d in G.items():
        fk = re.sub(r"[^a-z0-9]+", "_", fig.lower().replace(".png", "")).strip("_")
        if fig.startswith(("figure 6", "figure 8", "appendix")):
            for panel, sc in d.items():
                pk = re.sub(r"[^a-z0-9]+", "_", panel.lower()).strip("_")
                for s, series in sc.items():
                    for q in ("2026Q3", "2028Q4"):
                        F[f"{fk}__{pk}__{s}_{q}"] = series[q]
        elif fig.startswith("figure 10"):
            for lab, series in d.items():
                F[f"{fk}__{re.sub(r'[^a-z0-9]+', '_', lab.lower()).strip('_')}_2026Q3"] = series["2026Q3"]


def main():
    F = {}
    descriptive_facts(F)
    model_facts(F)
    reversal_facts(F)
    table_facts(F)
    figure_facts(F)
    out = {k: (v if isinstance(v, str) else (int(v) if isinstance(v, (bool, np.bool_)) else _r(v))) for k, v in F.items()}
    out = {k: (str(v) if isinstance(v, pd.Period) else v) for k, v in out.items()}
    (paths.OUT_RESULTS / "facts.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"facts: {len(out)} numbers written to output/results/facts.json")


if __name__ == "__main__":
    main()
