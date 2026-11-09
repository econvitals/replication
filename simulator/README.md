# Macroeconomic Simulator

**On econvitals.org:** the [Macroeconomic Simulator](https://econvitals.org/lab/frbus-simulator/): policy and economic shocks run through the Federal Reserve Board’s own FRB/US model, with the size, the length, the Fed’s response, the way the shock is paid for and the way expectations are formed chosen by the reader.

**What it is.** FRB/US is the large-scale model of the U.S. economy the Federal Reserve Board’s staff has used since 1996 and publishes with Python code. On the page a reader picks one of fifteen shocks (among them the federal funds rate, government purchases, taxes, oil prices, tariffs and stock prices) and sees the response of 32 variables over ten years, each as a difference from a baseline. The page runs no model: every number it shows comes from **13,426 runs solved in advance** and stored in 119 files, which the page scales, interpolates between sizes and, when shocks are combined, adds. This folder holds the engine that made those runs, the Board’s model and data exactly as they were used, and a check that rebuilds a sample of them. `METHOD.md` describes how the runs are made.

FRB/US is the Federal Reserve Board staff’s model. The simulations here are Econvitals’, not the Federal Reserve’s, and the Federal Reserve has not reviewed or endorsed them.

**How close.** Exact. `verify.py` rebuilds every run in the sample digit for digit (see “Run it”).

**Why it is not in the nightly check.** Rebuilding the sample means solving the model about 240 times, about half an hour with three worker processes, and the stored runs change only when the engine does. Whenever that happens this folder is exported again from the engine that made the page’s runs and `verify.py` is rerun in a fresh environment with the network blocked before it is published.

**Keys.** None. Nothing here uses the network.

## What is in this folder

```
README.md          this file
METHOD.md          how the runs are made: the baseline, the settings, each shock, what did not solve
SOURCES.md         the Board’s packages and every other input, with sources
verify.py          rebuilds the sample in expected/ and compares it with the stored numbers
check.json         how the repository’s nightly check treats this folder (not compared; see above)
requirements.txt   exact package versions (Python 3.14)
LICENSE            CC0, like the rest of the repository; the Board’s code and data are covered by their own terms
engine/            the code that made the page’s runs
  build.py           the engine: every run and the menus (its docstring explains it)
  scenario.py        solves one scenario and prints it as JSON
  tariff.py          the tariff construction (who pays the duty, and through which prices)
  invest_model.py    the model version used by the business-investment shock
  engine_paths.py    every path the engine reads or writes (all can be set by environment variables)
fed/               the Board’s FRB/US packages, as used (November 4, 2026 data package)
  pyfrbus/           pyfrbus 1.1.1, the Board’s Python platform, with the model in models/model.xml
  data_only_package/ LONGBASE.TXT, the Board’s history and baseline, and its README
  VINTAGE.json       where and when each was downloaded
inputs/            a CSV copy of the tariff parameters typed into the engine (the engine does not read it)
expected/          the page’s own numbers
  meta.json          the menus, baseline values, the stock-price calibrations and the Board’s package dates
  runs/              119 files, one per shock x expectations x lower bound x financing, each with a sample of its runs
```

**The sample.** The page’s library (13,426 runs, built November 9, 2026) is too large to keep here. `expected/runs/` holds every one of its files with **240 of its runs: two from every file**, plus the two `scenario.py --selftest` reads, so the sample covers every shock (both stock-price versions, both business-investment runs and the tariff among them) under every combination of expectations, lower bound and financing the page offers; within each shock the files take turns through the Fed responses, lengths and sizes stored for it. Each file’s `stored_runs` says how many runs the page’s copy holds, and its `failed` lists every run of that file that did not solve. `engine/build.py` rebuilds the whole library (below).

## Run it

You need Python 3.14 (tested with 3.14.8 on macOS, Apple silicon; it should run unchanged on Linux, and on Windows we suggest WSL). From this folder:

```
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python verify.py
```

The Board’s pyfrbus is not installed from `requirements.txt`: the engine imports the copy in `fed/pyfrbus/` (see `engine/engine_paths.py`). Run every command from this folder. All model work lowers its own scheduling priority.

### Check the stored runs: `verify.py`

`python verify.py` first reruns the two stock-price calibrations and rebuilds the parts of `meta.json` the engine computes (the baseline values, the menus, the variables and the Board’s package dates) and compares them with `expected/meta.json`. Then it solves every run in `expected/runs/` again with the engine’s own function and compares all 32 variables × 41 quarters with the stored numbers. It prints PASS or FAIL for each, writes `output/verify_report.csv` and ends with one line: `verify: PASS` or `verify: FAIL`.

* `--shocks tariff,invest`, `--exp var|mce`, `--elb no|yes` and `--fiscal fixed|debt` select files.
* `--workers N` sets the number of worker processes (default 3). A forward-looking model takes a few gigabytes of memory per worker.
* `--tol` sets the largest difference allowed in any number (default 0.0001). The stored numbers are rounded to three decimals, and in the test below every rebuilt number came back identical. Rarely one does not: pyfrbus stops its Newton iterations at a relative tolerance of 0.0005, so a floating-point difference too small to matter (another machine or library build, even a different process environment on the same machine) can change the step at which it stops and move a rounded number by 0.001. `verify.py` says so when every difference is of that size, and `--tol 0.0015` accepts them.
* `--compare DIR` solves nothing: it compares a library you rebuilt with `engine/build.py` (below) with the runs in `expected/`.

### Rebuild one run

```
FRBUS_OUT=expected python engine/scenario.py --shock tariff --size 1 --fed balanced --duration q8 --exp var --elb no --fiscal debt
```

This prints one JSON object whose `series` are the run stored in `expected/runs/tariff_var_no_debt.json` under `"1|balanced|q8"`. `scenario.py` reads the stock-price calibration from `meta.json`, and `FRBUS_OUT=expected` points it at this folder’s copy; once you have built your own library (below) you can leave that off. It also solves runs the library does not hold: any size from −10 to 10 units (a 25 percent tariff is `--size 2.5`) in any combination the engine builds. `FRBUS_OUT=expected python engine/scenario.py --selftest` checks a live run against the stored ones.

### Rebuild one shock’s library

```
python engine/build.py --shocks tariff --workers 3
python verify.py --compare data --shocks tariff
```

`build.py` reruns the calibrations, solves every run of that shock and writes `data/runs/tariff_*.json` and `data/meta.json`; `verify.py --compare` then checks the runs in the sample. Add `--exp var` (and `--elb`, `--fiscal`) to build part of it. Each configuration is written to its file as soon as it finishes and a rerun computes only what is missing (`--force` recomputes), so a long build can be stopped and resumed with the same command.

### Rebuild the whole library

```
python engine/build.py --exp var                         # backward-looking
python engine/build.py --exp mce --elb no                # forward-looking, normal times
python engine/build.py --exp mce --elb yes --fiscal fixed    # forward-looking, at the lower bound
python verify.py --compare data
```

A bare `python engine/build.py` runs the three in that order. `build.py` uses every core by default; `--workers` sets the number. It also writes a log (`engine/build.log`) and a count of model solves (`engine/solve_log.json`).

## How the stored runs are keyed

* `expected/runs/<shock>_<expectations>_<lower bound>_<financing>.json`, for example `tariff_mce_no_fixed.json`: expectations `var` (backward-looking) or `mce` (forward-looking); lower bound `no` (normal times) or `yes`; financing `fixed` (taxes fixed) or `debt` (the Board’s debt rule).
* Each file holds `runs`, keyed `size|Fed response|length`, for example `"-1|hold8|perm"`, and `failed`, the runs that did not solve, each with the solver’s message. Sizes are in the engine’s units and signs (the table below); Fed responses are `hold4`, `hold8`, `hold12` (the funds rate held at baseline for one, two or three years, then the inertial rule), `inertial`, `balanced`, `taylor93` and `firstdiff`; lengths are `q1`, `q4`, `q8`, `q12` and `q16` (quarters) and `perm` (permanent).
* Each run is `{variable: [41 numbers]}`, quarter 0 (when the shock starts) to quarter 40, as differences from the baseline, rounded to three decimals (`null` where a number is not finite). `expected/meta.json` lists the 32 variables under `vars`, each with its unit: `pct`, percent difference; `pp`, percentage-point difference; `gdp`, percentage points of GDP; `usd`, dollars a barrel.
* `meta.json` also holds the menus (`shocks`, with each shock’s lengths, Fed responses, stored sizes and the sign the page applies), the baseline values, the Board’s package dates (`vintage`) and the two stock-price calibrations (`calibration`).

| Shock | Size 1 means | Sizes stored | Lengths | Fed responses |
|:---:|:---:|:---:|:---:|:---:|
| `fed`: Federal funds rate | 1 percentage point | −2, −1, 1, 2 | `q1`, `q4`, `q8`, `q12`, `perm` | `inertial`, `balanced`, `taylor93`, `firstdiff` |
| `gov`: Government purchases | 1% of GDP | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `tax`: Taxes | 1% of GDP (engine: +1 = a cut) | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `transfers`: Transfers to households | 1% of GDP | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `oil`: Oil prices | $25 a barrel | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `dollar`: The dollar | 10% | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `stocks`: Stock prices | 10% on impact (engine: +1 = a 10% FALL) | −3, −2, −1, 1, 2, 3 | `q4`, `q8`, `q16`, `perm` | all seven |
| `stocks_earn`: Stock prices (expected earnings) | 10% on impact, through expected earnings growth (engine: +1 = a 10% FALL) | −3, −2, −1, 1, 2, 3 | `q4`, `q8`, `q16`, `perm` | all seven |
| `termprem`: Long-term rates | 1 point on the term premium | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `mfp`: Productivity | 1% | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `realloc`: Labor market reallocation | 1 point on the natural rate of unemployment | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `tariff`: Tariffs | a 10% tariff on non-oil imports | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `immig`: Immigration | 1% of the working-age population (engine: +1 = 1% SMALLER) | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `expect`: Inflation expectations | 1 point on long-run expected inflation | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `credit`: Credit spreads | 1 point on corporate bond spreads | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `invest`: Business investment | 1% of GDP, none of it imported | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |
| `investimp`: Business investment (all imported) | 1% of GDP, all of it imported | −2, −1, 1, 2 | `q4`, `q8`, `q16`, `perm` | all seven |

`investimp` is not on the page’s menu: the page mixes it with `invest` for a share of imported equipment between 0 and 100 percent.

**What the page’s library holds, and what did not solve**, by setting:

| Expectations | Lower bound | Financing | Runs stored | Did not solve |
|:---:|:---:|:---:|:---:|:---:|
| Backward-looking | Normal times | Taxes fixed | 1,984 | 0 |
| Backward-looking | Normal times | Debt rule | 1,984 | 0 |
| Backward-looking | At the lower bound | Taxes fixed | 1,984 | 0 |
| Backward-looking | At the lower bound | Debt rule | 1,984 | 0 |
| Forward-looking | Normal times | Taxes fixed | 1,901 | 67 |
| Forward-looking | Normal times | Debt rule | 1,911 | 57 |
| Forward-looking | At the lower bound | Taxes fixed | 1,678 | 290 |

Forward-looking expectations at the lower bound with the Board’s debt rule are not built (see “Caveats”).

## Run times

Measured on an eight-core Apple M1, in a fresh environment with the network switched off:

* `python verify.py` (calibrations, `meta.json` and the 240 runs): about half an hour with three worker processes.
* One model configuration, most of it setting up the model: about 5 seconds backward-looking; forward-looking, about half a minute in normal times (up to a minute) and about two minutes at the lower bound (up to five and a half), three at a time. `scenario.py` solves one run in about that time.
* A whole library, from the engine’s own logs on the same machine with five worker processes: backward-looking, about 20 minutes; forward-looking in normal times, roughly eight to nine hours at 200 quarters; forward-looking at the lower bound, several hours. Much of the forward-looking time goes to permanent runs that do not converge: each runs to the solver’s 40-iteration limit before it is given up. More workers shorten it about in proportion.

## Caveats

**Forward-looking runs are numerically fussy.** A forward-looking run solves a 200-quarter nonlinear system by Newton’s method, starting from the baseline. On a different processor, BLAS library or package version, the last digits can move, and a run near the edge of convergence can converge on one machine and not on another. The backward-looking runs are robust. If a forward-looking run misses on your machine, check first that you installed the exact versions in `requirements.txt`.

**Some runs did not solve, and they are listed.** Every backward-looking run solved. 414 forward-looking runs did not converge within 40 iterations and are listed, with the solver’s message, under `failed` in their files; the page says when a combination did not solve. `verify.py` does not attempt them. Forward-looking expectations at the lower bound with the Board’s debt rule are not built at all: in an early build only 86 of 680 such runs converged. Nor is a permanent Fed move under forward-looking expectations, which has no unique answer.

**The 200-quarter horizon.** Forward-looking runs are solved over 200 quarters (50 years) and the first 41 are stored, with the policy rule’s neutral real rate learning from the real funds rate (`drstar = 1`). A permanent shock stays in force to the end of the solution, so agents never see it end. Solved over 300 quarters instead, a sample of permanent shocks (government purchases, productivity growth, the tariff, credit spreads and expected earnings, under the balanced-approach rule, with taxes fixed and with the debt rule) moved real GDP, unemployment, core inflation and the funds rate by at most 0.05 and the 10-year yield by at most 0.08 over the 41 stored quarters; stock-market wealth moved by up to 1.6 percent of its level, and housing and business investment by a few tenths, most for shocks that never settle (productivity growth faster forever, a permanent deficit with taxes fixed). The page says so; treat those variables in permanent forward-looking runs as approximate.

**The page’s own arithmetic is not rebuilt here.** Sizes between the stored ones, the mix of imported equipment and combinations of shocks are computed in the browser from these runs (see `METHOD.md`).

**One model.** FRB/US has a flat Phillips curve, follows its policy rule, and has no industry detail and no financial accelerator. The page explains where this probably makes its answers too small.

## License

Like the rest of this repository, the code (`engine/`, `verify.py`), the stored results in `expected/` (Econvitals’ own work) and `inputs/` are in the public domain under Creative Commons CC0 1.0 (`LICENSE`). The bundled FRB/US code is a U.S. Government work in the public domain (`fed/pyfrbus/LICENSE`). The bundled data package is the Federal Reserve Board’s public release; its README notes that one history series in it (the Baa corporate bond yield) is from Moody’s via Bloomberg Finance LP. `SOURCES.md` gives the source of every input.
