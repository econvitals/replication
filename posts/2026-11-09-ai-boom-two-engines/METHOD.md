# Method

This note describes how the post’s simulations are built and why. The code is in `dcboom/`; `engine.py` holds the experiment itself.

## The question

How different is the U.S. economy because of the data-center buildout and the stock market gain that came with it? The method takes the economy as it actually was (the Federal Reserve Board’s FRB/US baseline, which reproduces history), removes the buildout and then also the stock gain, and lets the model work out everything else. Every reported effect is “with minus without”: percent differences for levels, percentage points for rates and shares of GDP. The “without” columns of the table are the actual data less those effects (divided by them, for levels).

## The model

FRB/US is the Federal Reserve Board staff’s large-scale model of the U.S. economy. The Board publishes it with a Python solver (pyfrbus). This package uses version 1.1.1 and the November 4, 2026 baseline database, both bundled. The baseline’s history runs through 2026Q2, with the Board’s projection after that. From 2023Q1 the model reproduces the baseline exactly through tracking residuals, so any difference in a run is the effect of what was removed. The author used the model; the Federal Reserve did not produce or endorse these results.

**Three changes to the Board’s model file** (`model_setup.py`; each keeps the Board’s equations for everything else):

1. **Separate data-center pieces.** Business investment (`ebfi`) and non-oil imports (`emo`) are each split into the Board’s own equation for the rest (`ebfio`, `emoo`) plus an exogenous data-center piece (`edc`, `emdc`). Both pieces are zero in the baseline. Otherwise, an add factor on the aggregate would read to the model as a gap to close and be worked off over time.
2. **Current-dollar GDP weights for those pieces** (switch `dcw` = 1). FRB/US adds up real final sales with fixed estimated weights. For a shock that is mostly imported, investment and imports net two large numbers, and the fixed weights would make a dollar of spending add 14–16 cents to GDP instead of the 25 cents its domestic content implies. With the switch on, each real unit of the data-center pieces enters at its baseline price relative to nominal final sales, which is the chain-weight contribution at current shares.
3. **Data-center capital does not count toward potential output** (switch `kdcsw` = 0). This keeps the experiment a pure demand shock, matching the post’s statement that AI’s supply effects are not included.

Two reporting identities are added: net exports and the current account as shares of GDP.

## The buildout

“The buildout” is spending above its 2015–2022 trend in three series:

* BEA private fixed investment in computers and peripheral equipment;
* BEA private fixed investment in communication equipment;
* Census private construction of data centers.

Each series gets a log-linear trend fitted to 2015–2022 and extrapolated. The excess counts from 2023Q1. Software is excluded.

The total is about zero, and slightly negative, through early 2024, because the pandemic surge in PC and server purchases was still unwinding. So by this measure the boom starts in mid-2024. It reaches 1.33 percent of GDP in 2026Q3, the last quarter of data. For 2026Q4 each series carries its past year’s average growth one more quarter, which gives 1.61 percent of GDP. The shock enters as a share of nominal GDP and is converted to the model’s real units at baseline prices.

**After 2026.** The share is held at its 2026Q4 level through 2031 and then fades to zero by 2035. This matters only for forward-looking expectations and for the “if the boom continues” projections, the dotted lines through 2028. The post’s “1.6 percent of GDP it is on track to reach by the end of this year” is this extrapolated 2026Q4 share, not the measured 2026Q3 share (1.3 percent). The “keeps growing” case adds 0.5 percent of GDP a year from the 2026Q4 level through 2028.

## How much is imported

The imported part of the buildout does not add to U.S. GDP: it shows up as positive investment and as negative imports. This is the most important judgment in the exercise.

The trade data cannot settle it directly. Imports of the four data-center goods categories rose more than measured investment did: 1.5 times as much gross, and 1.1 times net of the matching rise in exports of the same goods. A share above 100 percent cannot be the import content of the investment itself. Those categories also include consumer devices, and some of the measured imports go to uses outside the three investment series.

The post instead uses plausible direct import shares by type of spending, applied to each type’s excess:

* computers 85 percent;
* communication equipment 75 percent;
* data-center construction 10 percent.

All three are scaled by one factor so that the share over 2023Q1–2026Q4 is 75 percent. The scaling gives about 90 percent for computers, 79 percent for communication equipment and 11 percent for construction. In BEA’s 2017 input-output tables, the average direct import shares for these broad categories are much lower: about 41 percent for computers, 42 percent for communication equipment and 4 percent for structures. But the boom is concentrated in servers, chips and network gear, which are largely made abroad, so its shares should sit near the hardware end. After 2026Q4 the import ratio is held at its 2026Q4 value (78 percent).

## The stock gain

The gain is the extra market value of seven companies since ChatGPT’s release on November 30, 2022, measured against the rest of the U.S. market. The seven are Nvidia, Microsoft, Alphabet, Amazon, Meta, Broadcom and Oracle. The gain is what the seven are worth minus what they would be worth had they kept pace with the rest. It was $11.1 trillion at the end of September 2026, 10 percent of the value of all U.S. corporate equity. Households own about 68 percent of U.S. equity, directly and indirectly, so their part was $7.6 trillion.

**The gain as higher expected earnings.** In the “without the stock gain” run, investors expect slower growth of corporate dividends than in the baseline, quarter by quarter, until household stock wealth is lower by that share of market value than in the same run’s own world before the gain is taken out: the run solved with everything else it changes and expected dividend growth left alone. For the post’s central run that is the world without the buildout; for the expectations scenario, the forward-looking run without the gain, with the same productivity belief; for expectations that switch on in 2026, the same switch starting from the world without the buildout; for the boom ending, the world in which the buildout has ended. So each run takes out exactly the stated gain. Measured from the actual path instead, as earlier drafts of the post did, the target would also take out whatever the buildout itself did to stock prices: the buildout’s higher interest rates hold the market down by about 2 percent by 2026Q3, so the earlier construction removed about $13 trillion of market value rather than the $11 trillion the post states (Jason Furman’s decision of November 9, 2026). In FRB/US, stock wealth is current corporate payouts scaled up by the gap between the required return on equity and the expected growth of real dividends (`zdivgr`): a 1-point fall in expected dividend growth lowers log stock wealth by 0.25. The change is made through the add factor on the expected-dividend-growth equation, so expected dividend growth still responds to everything else the model moves. A few fixed-point iterations find the path, each one a full model solve. The target is hit within 0.05 percent. In the backward-looking runs it takes expected dividend growth about half a point a year higher with the gain than without it by 2026.

Expected dividend growth enters nothing else in the model. So the gain works only through wealth: it raises consumer spending directly, and other spending only through the extra demand. It does not lower firms’ cost of capital, so it gives business investment no direct boost.

In the forward-looking runs the higher earnings are investors’ belief, not profits that actually arrive. There expected dividend growth is a forward-looking average of future profit growth (it equals 0.99 times next quarter’s value, plus a small weight on next quarter’s profit growth, plus the add factor), so a belief about any quarter also lifts stock prices in every quarter before it. The iteration inverts that recursion when it updates the add factor.

**The alternative: a lower equity premium.** Earlier drafts of the post took the gain out by raising the model’s equity premium (`reqp`) instead, and measured it from the actual path (the baseline times one minus the gain’s share); `--stock-mode premium` keeps both, so it still reproduces those drafts. The premium also enters the cost of capital for business investment (`rbfi`, half the cost of equity and half the cost of debt), so in that version the stock gain also raised business investment by lowering the cost of equity. `python run_all.py --stock-mode premium` runs that version. On the August 7, 2026 baseline those drafts used, it wrote the same files, to the last byte, as the package did before the switch was added; on the November 4 baseline its numbers differ a little, as the default’s do.

After the fitting window the gap in whichever instrument is used (the add factor, or the premium) is held. In the forward-looking runs a held add factor keeps the belief in place; its effect fades by less than 2 percent by the end of 2028, only because the model’s 200-quarter horizon ends. For the post’s central runs the window is 2023Q1–2026Q4. For the projections through 2028 it is the whole window, so the gain itself stays at its latest share of market value. That share is measured at the last close used, November 5, 2026, which stands in for 2026Q4: 8.6 percent of market value, against 10.1 percent at the end of September. Because the target is a level of stock wealth, the switch cannot double count any stock market effect of the investment itself.

## Policy and expectations

* **Monetary policy:** the inertial Taylor rule, the default in the public model, responding from 2023Q1.
* **Fiscal policy:** the Board’s debt-stabilizing tax rule.
* **Expectations:** backward-looking (the model’s VAR expectations) in every result the post reports, except the expectations paragraph. The forward-looking runs use model-consistent expectations in asset pricing and in wage and price setting (`mcap+wp`), over a 200-quarter horizon. In those runs the policy rule’s r* learns from the real funds rate (`drstar` = 1). With r* fixed, as in the Board’s baseline, a believed productivity payoff that raises the neutral rate leaves policy too loose, and the larger productivity cases fail to solve.

**The expectations paragraph.** Here forward-looking agents expect the buildout to continue through 2031, and productivity growth to rise by 0.5 point a year starting in 2027. That run is solved by homotopy: first with a 0.3 belief, then with 0.5 starting from the 0.3 solution. With the premium construction the 0.5 case with the stock gain does not converge cold; the homotopy is kept for both.

FRB/US has a counterintuitive but genuine feature here. A payoff believed in advance makes 2023–2026 slightly weaker, because forward-looking wage setters build the coming gains into wages before they arrive.

**Expectations that switch on in 2026.** These runs follow the backward-looking run with the stock gain through 2025. From 2026Q1 they solve forward-looking, with the stock gain re-targeted for 2026. They use productivity beliefs of 0, 0.1, …, 0.5, each warm-started from the previous one. With the premium construction a belief of 0.5 does not solve, so that run stops at 0.4 unless `--try-unsolved` is given.

## If the boom ends

The paragraph after the post’s table and its section on the future rest on five backward-looking runs (`reversal.py`), with the inertial rule and 75 percent imported, as in the post’s central runs. Each starts from the world in which the boom holds: the Board’s baseline, in which the buildout stays at its extrapolated 2026Q4 share of GDP and the stock gain at its November 5, 2026 share of market value (8.6 percent), as in the dotted lines. Each run then takes out a share r(t) of the boom in each quarter, with the experiment’s own pieces:

* **The buildout.** `edc` and `emdc` are the excess spending and its imported part, as in every other run, times r(t), and times −1 to take the buildout out or +1 to add a second one.
* **Stock wealth.** The target for household stock wealth is the run’s own world before the stock change (its first solve, with the buildout change alone) times 1 − r(t) f(t), where f(t) is the AI stock gain’s share of market value, so the boom ending takes out exactly the AI stock gain from the world in which the buildout has ended. For a second boom it is divided by 1 − r(t) f(t) instead. A fall in the whole market is measured as the post means it, from the path with the boom: the baseline times 0.7. The target is reached through the same instrument and step as in the post’s runs (the add factor on expected dividend growth), fitted over 2023Q1–2028Q4 and held after.

The runs:

| Run | The buildout, r(t) | Stock wealth |
|:---:|:---:|:---:|
| The boom ends | 1 from 2027Q1 | the AI stock gain removed from 2027Q1, from the world in which the buildout has ended |
| The buildout ends | 1 from 2027Q1 | left to the model |
| The buildout ends and the market falls 30 percent | 1 from 2027Q1 | 30 percent below the path with the boom (the baseline) from 2027Q1 |
| A second boom (the mirror image) | 1 from 2027Q1, added | the stock gain added again from 2027Q1 |
| No boom | 1 from 2023Q1 | the stock gain removed from 2023Q1 |

The last run is the post’s world without the boom; `facts.py` checks that it matches `post_extend.json` to the five decimals stored, and stops if it does not. The solves run to 2030Q4.

How the post’s claims are read:

* **Growth** is real GDP, fourth quarter over fourth quarter. “Next year” is 2027 and “the year after” 2028; each is measured against the boom holding.
* **No recession** means no quarter of falling real GDP from 2027Q1 through 2030Q4.
* **Basically symmetric** means the boom ending is within 10 percent of the negative of the second boom: GDP’s level each quarter of 2027–28 and growth in each year, all measured from the boom holding.
* **Only faster** means the boom ending takes more off growth in 2027 than the boom added in any one year of 2024–26 (the boom holding against no boom).
* **Less buildout** is the buildout ending outright, the stock gain left in place. “Little changed” means GDP within half a percent of its path with the boom by the end of 2028. “A bigger deal” means the 30 percent market fall, on top of the buildout ending, takes at least half again as much off growth in 2027 as the buildout ending alone.

## From model effects to the table and the waterfalls

The table applies the model’s effects to the actual data. A level without the boom is the actual level divided by (1 + effect/100). A rate or share without the boom is the actual value minus the effect. Growth rows are annualized over 2024Q3–2026Q3.

Three approximations are worth knowing:

* **Business investment excluding data centers** (real) is real business investment less the nominal excess spending deflated by the overall business-investment price index. Computer prices fall faster than that index, so this probably understates the real excess.
* **Core PCE inflation without the boom** is actual eight-quarter inflation less the average of the model’s effects on quarterly annualized core inflation over the same quarters.
* **The waterfall contributions** (figures 7 and 9) are differences in chained-dollar components as a share of real GDP. Chained components do not add up exactly. “Everything else” is the remainder of the model’s GDP effect, so it absorbs that, along with other imports, inventories, government and exports.

The first two waterfall bars are the measured excess spending and the assumed imported part of it; the rest come from the model.

## What does not solve

With the default construction (higher expected earnings) every run in the package solves, including the two below that fail with the premium construction. The premium failures were recorded on the August 7, 2026 baseline, where the original work found the same ones; they have not been retried on the November 4 baseline.

| Run | Where it is used | Result with the premium construction |
|:---:|:---:|:---:|
| Expectations switching on in 2026, productivity belief 0.5 | the expectations parenthetical (the earlier draft used beliefs 0–0.4 instead) | does not converge: trust-region solver, 60 iterations |
| Forward-looking, stock gain, productivity 0.5, 50 percent imported (C_s50) | sensitivity runs only (`--all-shares`) | does not converge, even in smaller homotopy steps (0.15, 0.3, 0.4) |
| Forward-looking with r* fixed, productivity 0.6 (and 0.3 with the stock gain) | not used | does not converge; the reason for r* learning (not retried with the default construction) |

These are numerical failures of a large nonlinear forward-looking solve. The solver does not find a path within its iteration limit. This is not evidence that no equilibrium exists.

## Limits

This is one model. FRB/US was estimated largely on a calm period, so its Phillips curve is flat and inflation barely moves. It assumes monetary policy responds as the rule says. It has no detailed industry structure: bottlenecks in chips and other hardware could add to inflation in ways it cannot show. And it has no financial accelerator, so the unwinding of leverage is outside it.
