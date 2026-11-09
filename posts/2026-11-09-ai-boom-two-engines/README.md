# Replication package: “The AI Boom’s Two Engines”

This package reproduces every number, the table and every figure in “The AI Boom’s Two Engines,” an Occasional Post by Jason Furman on Econvitals (November 2026). It starts from frozen public data and the Federal Reserve Board’s FRB/US model, and ends by checking each rebuilt number against the post.

**On econvitals.org:** [“The AI Boom’s Two Engines”](https://econvitals.org/posts/2026-11-09-ai-boom-two-engines/), one of Jason’s Occasional Posts (November 9, 2026). The online version of its data-center case, where readers can change the assumptions, is on Jason Furman’s [What If page](https://jasonfurman.org/research/what-if/#data-centers), which has its own replication zip.

**How close.** Exact. `python run_all.py` rebuilds every number in the post from the frozen inputs and ends `verify: 278 PASS, 0 FAIL`.

**Why it is not in the nightly check.** The inputs are frozen, the run solves FRB/US many times (about 5 minutes with three worker processes, see “How to run it”), and nothing it checks changes after publication; its own `verify.py` is the check.

**Keys.** None. Nothing here uses the network.

## What the post does

The post asks how different the U.S. economy is because of the data-center buildout and the stock market boom that came with it. It uses FRB/US, the large-scale model of the U.S. economy that the Fed’s staff has used since 1996 and publishes with Python code.

The experiment takes the economy as it was and removes two things from 2023 on:

1. **The buildout:** spending on computers, communication equipment and data-center construction above its 2015–2022 trend, about 75 percent of it imported.
2. **The AI stock gain:** the extra rise in the market value of seven AI-related companies over the rest of the market since ChatGPT launched.

The model works out everything else. The stock gain is taken out as lower expected corporate earnings: in the run without it, investors expect slower growth of dividends, enough to bring household stock wealth down by the gain’s share of the market, measured from that run’s own world (for the post’s central run, the world without the buildout; see “Two ways to model the stock gain”). The headline finding: by the third quarter of 2026, the buildout alone has raised GDP by about 0.3 percent, and together with the stock gain by about 0.6 percent, with the unemployment rate about 0.3 percentage point lower. The post also asks what happens if the boom ends in 2027 (“If the boom ends” below). `METHOD.md` describes the method in full.

Earlier drafts of the post took the stock gain out as a higher equity premium instead. That version also lowers firms’ cost of capital, so it gives larger effects (about 0.8 percent on GDP), and like those drafts it measures the gain from the actual path rather than from each run’s own world. `python run_all.py --stock-mode premium` runs that version; on the August 7, 2026 baseline the earlier drafts used, it reproduced them exactly. See “Two ways to model the stock gain” below. `verify.py` checks the current draft, so that run fails the rows that depend on the stock gain.

FRB/US is the Federal Reserve Board staff’s model. The simulations here were run by the author. They are not the Federal Reserve’s, and the Federal Reserve has not reviewed or endorsed them.

## What is in the package

```
run_all.py                     one entry point: rebuilds everything, then runs verify.py
verify.py                      checks every rebuilt number against the post (expected.csv)
expected.csv                   every number in the post’s text, table and figures, with the sentence it comes from
make_zip.py                    writes a clean zip of the package (what git archive makes of a commit)
METHOD.md                      the method: model changes, the shock, import shares, the stock gain, expectations
requirements.txt               exact package versions (Python 3.14)
dcboom/                        the code
  inputs.py                      the shock and the actual series, rebuilt from data/ and checked against data/as_used/
  model_setup.py                 the data-center version of the Board’s model file
  engine.py                      the experiment (shock, import shares, stock gain, solves, effects)
  runs.py                        every model run behind the post
  reversal.py                    the boom ending in 2027, its mirror image and a 30 percent market fall
  table.py, figures.py           the summary table, figures 1–10 and appendix figures 1–4
  descriptive.py, facts.py       the descriptive numbers, and every number in the post in one file
data/                          frozen inputs as used for the post; data/SOURCES.md documents each one
pyfrbus/                       the Board’s pyfrbus 1.1.1 solver, unmodified
fed/                           the Board’s model file, license and baseline database (LONGBASE, 2026-11-04 vintage)
refresh/                       optional: re-pull the public data from the agencies (never run by default)
```

## How to run it

You need Python 3.14 (tested with 3.14.8 on macOS, Apple silicon; it should run unchanged on Linux, and on Windows we suggest WSL). Nothing else is required, and the main run needs no network, no API keys and no other software.

```
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run_all.py
```

`run_all.py` runs seven steps in order. Each step can also be run on its own with `python -m dcboom.<step>`:

1. Rebuild the inputs and check them against those used for the post.
2. Build the model file.
3. Run the model.
4. Make the table.
5. Make the figures.
6. Collect every number.
7. Run `verify.py`.

**Run time.** On an eight-core Apple M1 shared with other model jobs, the whole run, sensitivity runs included (`--all-shares`), took about 5 minutes with three worker processes and 37 with one. On November 9, 2026, with another three-process model job running on the same machine, the default run took 5 minutes and `--all-shares` 11. Since the stock gain comes out of each run’s own world (later that day), the runs in which expectations switch on in 2026 also solve those worlds, six more forward-looking solves: the default run then took 10 and 14 minutes with three workers, beside a six-process model job. With the premium construction it is slower: 24 minutes for the default run, with two worker processes, in a test with a fresh environment and the network switched off.

* The model runs use three worker processes by default. Change this with `--workers`. Each run gets a fresh process, because a forward-looking model setup holds about 4 GB of memory.
* Almost all the time goes into two forward-looking runs: the expectations scenario, and expectations that switch on in 2026.
* The backward-looking runs behind the table and most figures take under a minute; the runs in which the boom ends take about 5 seconds, alongside the others.

The model step lowers its own scheduling priority.

* `--skip-runs` reuses earlier model output.
* `--all-shares` adds sensitivity runs (85 and 50 percent imported). The post mentions them only in passing (a higher import share “would make the effect smaller still”), and verify does not need them.
* `--stock-mode premium` takes the stock gain out as a higher equity premium, as earlier drafts of the post did, instead of as lower expected earnings (the default).
* `--try-unsolved` matters only with `--stock-mode premium`. It then also attempts the 2026 run with a 0.5 productivity belief, which does not converge with that construction (see “Caveats”); with `--all-shares` it also attempts the sensitivity run that does not converge. This adds half an hour or more. With the default construction both runs solve and are always run.

## What you should get

Everything is written to `output/`:

* `output/figures/` holds the table and all 14 figures as PNG files, named as in the post.
* `output/results/` holds the model runs (`post_runs.json`, `post_extend.json`, `news2026.json`, `reversal_runs.json`), the table (`table_1_summary.csv`), every recomputed number (`facts.json`) and the verification report (`verify_report.csv`).

**What verify reports.** `expected.csv` holds the numbers of the published post, on the Board’s November 4, 2026 baseline. `python run_all.py` ends with `verify: 278 PASS, 0 FAIL out of 278 numbers from the post`. With `--stock-mode premium` the rows that depend on the stock gain fail, because that run follows the earlier drafts’ construction.

**What verify checks.** `expected.csv` lists 278 numbers, all typed from the post itself and never from this package’s output. Each comes with the sentence, table cell or figure label it appears in. They include:

* every number in the text, including the descriptive ones (“highest since 1982,” “$840 billion,” “two-fifths,” “$7.6 trillion,” “16.8 to 16.1 percent,” the construction figures);
* every cell of the table;
* every printed label in the figures, plus values read off the charts that have no labels;
* every claim about what happens if the boom ends (“about half a percentage point,” “about 1½ percent,” “nothing resembling a recession,” “basically symmetric”).

**Tolerances.** A rounded number passes if the rebuilt value rounds to it: “about 0.3” passes for anything from 0.25 to 0.35. Table cells and figure labels get an extra 0.0005 for last-digit differences across machines; numbers in the text are checked at their printed rounding alone, which is stricter. Values read off a chart carry a reading tolerance, stated in the row. Qualitative statements (“housing is a touch lower,” “much of the added interest rate increase,” “not even a shallow recession”) are made explicit as ranges, and the `note` column says how.

On the machine where it was built, and on the Board’s August 7, 2026 baseline that the original work used, every result of the premium construction matched the original work:

* every model result agreed with the original runs to the five decimals stored;
* the rebuilt table equaled the post’s table exactly;
* the data behind figures 2–4 matched the post’s chart data exactly;
* figure 5 matched within 0.002 percentage point (the original divided by a monthly interpolation of GDP rather than quarterly GDP).

The inputs step stops if the rebuilt inputs differ from those used for the post (`data/as_used/`).

## Two ways to model the stock gain

In FRB/US, household stock wealth is current corporate payouts scaled up by the gap between the return investors require on equity and the growth of dividends they expect. So the stock gain can be taken out through either one. They differ in what else moves, and in the target they bring stock wealth down to.

* **Higher expected earnings (the default).** In the run without the gain, investors expect slower growth of real dividends, until household stock wealth is lower than in that run’s own world without the stock gain taken out by the gain’s share of market value: the world without the buildout, for the post’s central run; the forward-looking run without the gain, for the expectations scenario; the world in which the buildout has ended, for the boom ending. So each run takes out the stated gain, and only that. (Earlier drafts of the post measured it from the actual path instead, which also took out what the buildout itself did to stock prices: about $13 trillion of market value at the end of September, not the $11 trillion stated. That version is commit `1e94cd5`.) Expected dividend growth enters nothing else in the model, so the gain works only through wealth: consumer spending directly, other spending through the extra demand. With forward-looking expectations the higher earnings are a belief, not profits that arrive.
* **A lower equity premium (`--stock-mode premium`, earlier drafts of the post).** In the run without the gain, investors demand a higher return on equity. The required return on equity also enters firms’ cost of capital, so in this version the stock gain also raises business investment directly. This version keeps those drafts’ target too, the actual path times one minus the gain’s share, so that it still reproduces them.

In the third quarter of 2026, with backward-looking expectations, the buildout and the stock gain together raise GDP by 0.63 percent (0.81 with the premium construction), lower the unemployment rate by 0.28 percentage point (0.35) and raise the federal funds rate by 0.34 point (0.41). The stock gain adds 0.37 percent of GDP to consumer spending (0.45) but only 0.04 percent of GDP to other business investment (0.19).

## If the boom ends

The paragraph after the post’s table, and its section on the future, ask what happens if the boom stops. `dcboom/reversal.py` answers with five runs, all on the post’s central assumptions: backward-looking expectations, the inertial policy rule, 75 percent of the buildout imported, and the stock gain as higher expected earnings. Each starts from the world in which the boom holds. That is the Board’s baseline, with the buildout at its 2026Q4 share of GDP and the stock gain at its share of market value on November 5, 2026 (the post’s dotted lines). From the first quarter of 2027:

* **The boom ends:** the buildout above trend drops to zero and the AI stock gain disappears: stock wealth is the world in which the buildout has ended, less the gain’s share of market value.
* **The buildout ends:** the buildout drops to zero, and the model decides what stock prices do.
* **The buildout ends and the whole market falls 30 percent:** household stock wealth is held 30 percent below its path with the boom (measured from that path, as the post means it, not from the world in which the buildout has ended).
* **A second boom** of the same size starts instead: the mirror image of the first run, for the symmetry claim.
* **No boom at all**, from 2023: the post’s “without” world. It matches `post_extend.json` to the five decimals stored (`dcboom.facts` stops if it does not), and it measures how fast the boom added to growth.

Real GDP growth, fourth quarter over fourth quarter, percent:

| | 2027 | 2028 |
|:---:|:---:|:---:|
| The boom holds (the Board’s baseline) | 2.40 | 2.20 |
| The boom ends | 1.85 | 1.99 |
| The buildout ends | 2.00 | 2.11 |
| The buildout ends and the market falls 30 percent | 1.44 | 1.64 |

What the post quotes, and what verify checks:

* **“Shaving about half a percentage point off growth next year and a quarter point the year after.”** The boom ending takes 0.55 point off growth in 2027 and 0.21 point in 2028.
* **“Nothing resembling a recession,” “not even a shallow recession.”** GDP never falls in a quarter, in any of these runs, through 2030. The weakest quarter is the first of 2027, when the buildout stops: 1.1 percent at an annual rate.
* **“Basically symmetric … only faster.”** The boom ending is 97 to 103 percent of the mirror image, in GDP’s level each quarter of 2027–28 and in growth in each year. It takes more off growth in 2027 than the boom added in any year of 2024–26 (at most 0.32 point, in 2026).
* **“If the data center boom ends and the AI stock gains disappear.”** The boom ending takes out exactly the AI stock gain: its stock wealth is 99.5 to 100 percent of the gain’s share below the world in which only the buildout ended, in every quarter of 2027–28.
* **“The economy could survive less data center buildout just fine.”** When the buildout ends on its own, business investment, imports and interest rates fall, and GDP ends 2028 0.48 percent below its path with the boom. Verify reads “little changed” as less than half a percent, which this passes narrowly.
* **“Growth would slow to about 1½ percent.”** With the 30 percent market fall, growth in 2027 is 1.44 percent. Growth in 2028, 1.64 percent, is not quoted in the post.

The five runs take about 5 seconds (one model setup, then under a second each). `dcboom.runs` runs them alongside its other runs, so they add nothing noticeable to the total. `python -m dcboom.reversal` runs them alone, once steps 1 and 2 have run. `METHOD.md` gives the construction.

## Caveats

**Forward-looking runs are numerically fussy.** They solve a 200-quarter nonlinear system by Newton’s method, with warm starts and, for the expectations scenario, a homotopy step. On a different processor, BLAS library or package version, the last digits can move. The backward-looking runs are robust.

Even on one machine, the last digits of a backward-looking solve vary from one run to the next, by a few parts in ten trillion, because the order in which the model’s equations are handled depends on Python’s string hashing, which changes with each process. Setting `PYTHONHASHSEED=0` makes such reruns bit-identical. Nothing verify checks comes close to depending on it.

The package was tested on one machine, where, on the August 7, 2026 baseline the original work used, the results matched the original runs to the last digit stored. verify’s extra 0.0005 for model output is a margin for other machines, not a measured cross-machine difference. If a forward-looking number misses by more than that on your machine, check first that you installed the exact versions in `requirements.txt`.

**Some combinations do not solve with the premium construction.** With the default construction every run in the package solves, on the November 4 baseline as on the August one. With `--stock-mode premium` on the August 7, 2026 baseline, two runs failed to converge within their iteration limits, as they had in the original work. They have not been retried on the November 4 baseline.

* With expectations that switch on in 2026, a productivity belief of 0.5 does not solve. The earlier draft’s parenthetical rests on the beliefs that do solve (0 to 0.4).
* In the sensitivity grid only, the forward-looking run with the stock gain and productivity at 50 percent imported does not solve, even in smaller steps.

Because these failures take a long time to arrive, the premium run does not attempt them. On the build machine the 0.5 case took 55 minutes to fail. `python run_all.py --stock-mode premium --try-unsolved` attempts the first and records the failure; add `--all-shares` to attempt the second as well.

In both cases the iterative solver fails to find a path within its limit. This is not evidence that no equilibrium exists. `METHOD.md` has the full list.

**Data vintage.** The data are as of November 5–7, 2026:

* national accounts through BEA’s advance estimate for 2026Q3;
* construction spending and trade through September 2026;
* stock prices through November 5, 2026.

The model’s baseline is the Board’s November 4, 2026 LONGBASE, the newest when the post was written, with history through 2026Q2. For 2026Q3 the effects are therefore measured around the Board’s projection rather than actual history. They are then applied to the actual data.

The Board replaces its LONGBASE download from time to time. A different download gives a different baseline and different results, which is why the vintage used is bundled. Drafts of the post before November 8, 2026 used the August 7, 2026 file, with history through 2026Q1. `refresh/` can update the public data, but it deliberately leaves the baseline alone.

**One model.** FRB/US has a flat Phillips curve, assumes policy follows its rule, and has no detailed industry structure and no financial accelerator. The post discusses what that leaves out.

**Figures.** The figures use plain matplotlib, not the post’s typeface and house style. They show the same series, titles, units and periods; small differences in layout are expected.

## Notes on the post’s numbers

Every number in the text of the post’s latest round reproduces within its rounding on the November 4 baseline (the table cells and figure labels that moved are under “What verify reports” above). A few things are worth knowing when reading them:

* **“The 1.6 percent of GDP it is on track to reach by the end of this year.”** The dotted lines hold the buildout at its extrapolated 2026Q4 share, 1.6 percent of GDP, not the 1.3 percent measured in 2026Q3: 2026Q4 has no data yet, so each spending series carries its past year’s growth one more quarter. The dotted-line numbers rest on it: for the buildout alone 0.44 percent on GDP and 0.25 point on unemployment by the end of 2028; with the stock gain 0.76 percent, 0.44 point and 0.68 point on the funds rate, written 0.75, 0.45 and 0.7 (1.20, 0.61 and 0.89 with the premium construction).
* **The stock gain in the dotted lines.** The dotted lines hold the gain at its share of market value on November 5, 2026 (8.6 percent), the last close used: the post’s “early-November level.” That is below its share at the end of September (10.1 percent), when the solid lines end. Because the gain comes out of the world without the buildout, whose stock market the buildout’s higher interest rates hold down by about 5 percent by the end of 2028, household stock wealth with the boom ends 2028 about 4 percent above the world without it (appendix figure 4), not the 9.4 percent the gain alone would give.
* **Rounding to the nearest 0.05.** Two-decimal numbers in the text are rounded to the nearest 0.05. The unemployment effect if the buildout keeps growing is 0.37 point, written 0.35. The rise in the 10-year yield in the forward-looking case is 0.75 point, written 75 basis points (0.85 with the premium construction; the earlier drafts, on the August baseline, had 0.86 and wrote 85). The exception is the 10-year yield with backward-looking expectations, 0.126 point, written 13 basis points.
* **Saving.** “Saving has risen only about a tenth of a percentage point of GDP” is implied rather than read off the model, through the identity the post states (the current account is saving minus investment): the added investment (1.39 percent of GDP, “about 1.4”) less the fall in the current account (1.30).
* **A higher import share.** The remark that a higher import share “would make the effect smaller still” rests on the sensitivity runs (`--all-shares`), which verify does not check. With 85 percent imported, the buildout alone raises GDP by 0.31 percent by the end of 2028 instead of 0.44.
* **“About $30 billion.”** Each tenth of a percent of GDP is $33 billion at the 2026Q3 annual rate. The post rounds that to about $30 billion.
* **Two market totals.** The model’s stock gain ($11.1 trillion at the end of September, households’ part $7.6 trillion) is measured against all U.S. corporate equity, including closely held companies. The “two-fifths” share and figure 3 use U.S. public companies only.
* **The table’s stock market row.** The table’s $9.14 trillion is the buildout’s effect on market value (−$2.22 trillion, through higher interest rates) plus the gain, taken out of the world without the buildout: 10.1 percent of its $112.7 trillion, $11.4 trillion, against $11.1 trillion of the actual $110.5 trillion.
* **The household share.** The household share (68 percent) divides households’ direct and indirect equity holdings by the value of U.S.-issued equity. Other reasonable definitions move the $7.6 trillion by roughly a tenth either way.

## Refreshing the data

See `refresh/README.md`. BEA, Census and the Survey of Professional Forecasters need no key; FRED needs a free key. Two inputs have to be updated by hand: the trade lines and the stock gain. The refreshed run is never the default.

## License

The code is MIT-licensed (`LICENSE`). The bundled FRB/US code is a U.S. Government work in the public domain (`fed/pyfrbus_dist/LICENSE`). The bundled FRB/US data package is the Federal Reserve Board’s public release; its README notes that one history series in it (the Baa corporate bond yield) is from Moody’s via Bloomberg Finance LP. The data in `data/` are public data from U.S. agencies, the Federal Reserve Bank of Philadelphia, and company filings and market prices; `data/SOURCES.md` gives each source.
