"""Where the engine reads and writes. One module, so the same code runs in two layouts.

  * A standalone replication package bundles the Federal Reserve Board's two FRB/US packages in fed/ beside engine/
    (fed/pyfrbus: the Python platform with models/model.xml; fed/data_only_package: LONGBASE.TXT; fed/VINTAGE.json).
    The engine finds them there and writes everything under data/ beside engine/.
  * In its home repository the Board's packages sit in a download folder outside the repository (home_paths.py,
    which a package does not carry).

Every path can be set by an environment variable, which wins over both layouts:
  FRBUS_FED          the folder holding the Board's packages (pyfrbus/, data_only_package/, VINTAGE.json)
  FRBUS_OUT          where the library is written: meta.json and runs/ (default: data/ beside engine/)

pyfrbus itself is imported from the Python environment when it is installed there (pip install -e <FED>/pyfrbus);
otherwise from <FED>/pyfrbus, the Board's distribution as bundled, which this module adds to the import path.
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLED_FED = HERE.parent / "fed"
BUNDLED = (BUNDLED_FED / "VINTAGE.json").exists()          # True inside a replication package
try:                                                         # the home repository's own location (home_paths.py);
    from home_paths import HOME_FED                          # a replication package does not carry that file
except ImportError:
    HOME_FED = BUNDLED_FED

FED = Path(os.environ.get("FRBUS_FED") or (BUNDLED_FED if BUNDLED else HOME_FED))
OUT = Path(os.environ.get("FRBUS_OUT") or (HERE.parent / "data"))

if importlib.util.find_spec("pyfrbus") is None and (FED / "pyfrbus" / "pyfrbus" / "frbus.py").exists():
    sys.path.append(str(FED / "pyfrbus"))
