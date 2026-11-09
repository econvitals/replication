"""Every path the package uses, relative to the repository root. Nothing outside the repository is read."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FED = ROOT / "fed"
FED_MODEL_XML = FED / "pyfrbus_dist" / "models" / "model.xml"       # the Board's FRB/US model file, as distributed
LONGBASE = FED / "data_only_package" / "LONGBASE.TXT"               # the Board's baseline database (2026-11-04 vintage)

# Frozen inputs. DCBOOM_DATA lets a refreshed copy (refresh/ writes data_refreshed/) stand in for data/.
DATA = Path(os.environ.get("DCBOOM_DATA", ROOT / "data"))
AS_USED = ROOT / "data" / "as_used"                                  # the derived inputs exactly as used for the post

OUT = Path(os.environ.get("DCBOOM_OUTPUT", ROOT / "output"))
OUT_INPUTS = OUT / "inputs"                                          # derived model inputs rebuilt from data/
OUT_MODEL = OUT / "model"                                            # the data-center version of the model file
OUT_RESULTS = OUT / "results"                                        # model runs (JSON), table and facts (CSV/JSON)
OUT_FIGS = OUT / "figures"

DC_MODEL_XML = OUT_MODEL / "model_dc.xml"


def ensure():
    for p in (OUT, OUT_INPUTS, OUT_MODEL, OUT_RESULTS, OUT_FIGS):
        p.mkdir(parents=True, exist_ok=True)


def using_frozen_data() -> bool:
    return DATA.resolve() == (ROOT / "data").resolve()
