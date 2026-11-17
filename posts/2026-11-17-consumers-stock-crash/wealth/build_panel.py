"""Build the quarterly panel (output/panel.csv) from the frozen inputs in data/.

The frozen files hold the series exactly as downloaded for the post (Financial Accounts release of September 11,
2026; BEA national accounts through 2026Q3; FRED monthly series averaged to quarters). This script repeats the
original build (the research folder's 01_build_data.py) from them: the three-way split of net worth, holding gains,
real per-person values and real interest rates.

    python wealth/build_panel.py            (run from the package folder)
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)


def frozen(name):
    x = pd.read_csv(DATA / name, index_col=0)
    x.columns = [c.split(" [")[0] for c in x.columns]
    return x


d = frozen("bea_series.csv").join(frozen("z1_series.csv")).join(frozen("fred_series_quarterly.csv"))
d.index.name = "q"

# three-way split of net worth: stocks (direct + indirect), housing (owner-occupied, gross), other (net of all debt)
d["S"] = d["eq_all"]
d["H"] = d["re_oo"]
d["O"] = d["nw"] - d["S"] - d["H"]
d["HE"] = d["home_equity"]
d["O_he"] = d["nw"] - d["S"] - d["HE"]
# holding gains during the quarter
d["ret_S"] = d["rv_eq_direct"] / d["eq_direct"].shift(1)
d["g_S"] = d["ret_S"] * d["S"].shift(1)
d["ret_H"] = d["rv_re"] / d["re_total"].shift(1)
d["g_H"] = d["ret_H"] * d["H"].shift(1)
d["g_NW"] = d["rv_nw"]
d["g_O"] = d["g_NW"] - d["g_S"] - d["g_H"]
d["infl_q"] = d["p_pce"] / d["p_pce"].shift(1) - 1
for k in ["S", "H", "O", "NW"]:
    lvl = d["nw"] if k == "NW" else d[k]
    d[f"rg_{k}"] = d[f"g_{k}"] - d["infl_q"] * lvl.shift(1)
d["labor_y"] = d["comp"] + d["transfers"] - d["contrib"]
d["labor_at"] = d["labor_y"] * (1 - d["taxes"] / d["pinc"])
d["ex_transfer_y"] = d["dpi"] - d["transfers"]
d["pce_nds"] = d["pce_nd"] + d["pce_sv"]
pdefl = d["p_pce"] / 100.0
pop = d["pop"] * 1000.0
for k in ["dpi", "pce", "outlays", "labor_y", "labor_at", "transfers", "ex_transfer_y", "pce_nds", "pce_dur",
          "S", "H", "O", "nw", "HE", "O_he", "g_S", "g_H", "g_O", "g_NW", "rg_S", "rg_H", "rg_O", "rg_NW"]:
    d[f"r_{k}"] = d[k] * 1e6 / pdefl / pop
d["infl_core_4q"] = 100 * (d["p_core"] / d["p_core"].shift(4) - 1)
d["infl_pce_4q"] = 100 * (d["p_pce"] / d["p_pce"].shift(4) - 1)
d["real_tb3m"] = d["tb3m"] - d["infl_pce_4q"]
d["real_gs10"] = d["gs10"] - d["infl_pce_4q"]
d.to_csv(OUT / "panel.csv")
(OUT / "data_notes.json").write_text(json.dumps({"z1_last_quarter": str(d["nw"].last_valid_index()),
                                                  "bea_last_quarter": str(d["pce"].last_valid_index())}, indent=1))
print("panel:", d.index[0], "to", d.index[-1], d.shape)
