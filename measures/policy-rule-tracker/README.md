# Policy-Rule Tracker

**On econvitals.org:** the [Taylor Rule tool](https://econvitals.org/tools/taylor-rule/). Method note: [Methods](https://econvitals.org/methods/#policy-rule-tracker).

**What it is.** A policy-rule reading at every FOMC decision since 1960. The rules are the Fed’s; what Econvitals builds is the meeting-by-meeting dataset they run on, the hybrid slack measure, and the tables around them. This folder rebuilds the dataset and the featured rule’s reading at every past decision:

- **Real-time timing, today’s values.** For a decision on day D, the inputs are the latest unemployment month, inflation month and GDP quarter that had been *published* by D (an 8:30 release counts for a 2 p.m. decision), using ALFRED’s first-release date for each observation where its record reaches (unemployment from 1960, GDP from 1991, core CPI from 1996, core PCE from 2000), FRED’s release calendar before that, and a fixed publication lag before the calendar begins. The values are today’s vintage — revised GDP and PCE, CBO’s current potential output and natural rate, the New York Fed’s current r* — not what the committee saw.
- **Which decisions.** Every scheduled meeting, plus any conference call or unscheduled meeting that moved the target within two days (several calls around one move count once). Before the target series begins (September 1982) no call can be told apart, so none are kept.
- **The rate going in** is the target the day before (the single target from September 1982, the midpoint of the range from December 2008); the rate coming out is read three days after. Before 1982 they are the previous and next month’s effective rate.
- **The hybrid slack measure:** CBO’s output gap for the latest quarter with a GDP estimate, moved by Okun’s law (coefficient 2) as the unemployment rate changes from that quarter’s average to the latest month, so the gap follows the jobs report between GDP releases.
- **r\*** is the latest quarter the New York Fed would have posted (a quarter is taken as published 60 days after it ends); **u\*** is CBO’s natural rate for the unemployment month’s quarter.
- **The featured rule** is the Fed’s inertial rule: the balanced-approach rule, *r\* + π + 0.5 (π − 2) + 1.0 × gap*, on 12-month core PCE inflation, the Laubach–Williams r\* and the hybrid gap, smoothed with 0.85 a quarter on the rate going in (0.85 raised to the days since the last meeting over 91.31, with the days held between 20 and 183).

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`). It writes `output/meetings.csv`: one row per decision with every input (and the month or quarter it came from), the hybrid gap, the rule before smoothing and the inertial rule. `output/site_meetings.csv` holds the published inputs laid out flat, with the rule worked out from them by the page’s own arithmetic, for the nightly comparison.

**Data.**

- FRED: `UNRATE` (BLS unemployment rate), `PCEPILFE` and `PCEPI` (BEA PCE price indexes, ex food and energy and all items), `CPILFESL` and `CPIAUCSL` (BLS CPI-U), `GDPC1` (BEA real GDP), `GDPPOT` and `NROU` (CBO potential GDP and noncyclical rate of unemployment), `FEDFUNDS`, `DFEDTAR`, `DFEDTARU`, `DFEDTARL` (the Board’s effective rate and target). Inflation is the 12-month change; October 2025 was never collected (the shutdown), so a year-ago October 2025 is the geometric average of September and November 2025.
- ALFRED first-release dates (`series/observations?output_type=4`) for `UNRATE`, `PCEPILFE`, `CPILFESL` and `GDPC1`; FRED release calendars 50 (Employment Situation), 54 (Personal Income and Outlays), 10 (CPI) and 53 (GDP).
- The New York Fed’s current [Laubach–Williams and Holston–Laubach–Williams estimates](https://www.newyorkfed.org/research/policy/rstar) (one-sided).
- FOMC meeting dates: `inputs/fomc_meetings_1960_2020.csv` (every scheduled meeting, conference call and unscheduled meeting from the Board’s historical-year pages, 1960–2020; notation votes and canceled meetings left out), and the Board’s [current calendar page](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) for 2021 on, read at run time.

CBO’s potential output and natural rate are read through FRED, which republishes them unchanged, so no CBO file is needed here.

**How close.** Reproduces the published dataset exactly: on November 8, 2026 every one of the 688 decisions matched on every input (unemployment, four inflation measures, the output gap and its quarter’s unemployment, CBO’s u\*, both r\* estimates, the rates going in and coming out) and on the featured rule, with no difference at all. The check allows 0.001, one unit in the third decimal the site publishes.

**What is not rebuilt here.** The Dallas Fed’s trimmed-mean PCE (one of the page’s five inflation choices); the Summary of Economic Projections, Survey of Professional Forecasters and CBO forecasts behind the forward leg and the range tables; the CME FedWatch market path (not public data); the upcoming meeting, which is run on whatever has been published on the day the page is built; and the reaction-function updater, which rearranges published SEP medians.
