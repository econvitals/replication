# Age-Adjusted Labor Market Rates

**On econvitals.org:** [Demographic detail › Actual vs. Age/Sex-Adjusted](https://econvitals.org/labor/demographicdetail/#levels), the eight charts of the participation rate and the employment rate, actual and adjusted, for everyone 16 and over and for ages 16–24, 25–54 and 55+. Method note: [Methods](https://econvitals.org/methods/#age-adjusted-labor-rates).

**What it is.** An older population participates and works less, so the headline participation rate falls even when no group changes its behavior. Each month’s change in the rate is split into a behavior part (people in each of 30 age-and-sex groups changing what they do) and a composition part (the mix of groups shifting), using a chained decomposition: the split is made month by month and the pieces added up, so the weights follow the population as it changes. With population shares *s* and rates *r* for the 30 groups, the month’s behavior part is

> Σ<sub>i</sub> ½ (s<sub>i,t</sub> + s<sub>i,t−1</sub>) (r<sub>i,t</sub> − r<sub>i,t−1</sub>)

and only it is cumulated. The adjusted line is then scaled to equal the actual rate in the latest month:

> adjusted(t) = actual(latest) − [cumulative behavior(latest) − cumulative behavior(t)]

The age-band versions adjust only within the band, using the band’s own groups. The method is Jason Furman’s, from his work at the Peterson Institute for International Economics, ported here to monthly data. The decomposition itself is in [`common/labor.py`](../../common/labor.py), shared with the [aging counterfactual](../aging-counterfactual/).

The 30 groups are BLS’s 15 age bins (16–17, 18–19, 20–24, then five-year bins to 55–59, then 60–61, 62–64, 65–69, 70–74 and 75+) for men and for women. BLS publishes those fine groups only without seasonal adjustment, so each group’s rate is scaled to agree with the seasonally adjusted rate BLS publishes for the broader group it belongs to (16–17, 18–19, 20–24, 25–34, 35–44, 45–54 and 55+, by sex): the factor is the adjusted group rate over the unadjusted one, both using the group’s unadjusted population, since BLS publishes no adjusted population.

**Run it.** `python replicate.py`. No key needed. Writes `output/<lfpr|epop>_adjusted_<all-ages|16-24|25-54|55plus>.csv`, each with `actual` and `adjusted` columns, monthly from January 1990.

**Data.** 118 series from the BLS Current Population Survey: for each of the 30 fine groups, population (`LNU00…`), labor force (`LNU01…`) and employment (`LNU02…`), not seasonally adjusted; and for each of the 14 broader groups, labor force (`LNS11…`) and employment (`LNS12…`), seasonally adjusted. The series ids are listed in `common/labor.py`. FRED carries only some of them, so they come from BLS’s bulk file for the household survey, `download.bls.gov/pub/time.series/ln/ln.data.1.AllData`. That file is about 400 MB and has no smaller pieces; the script streams it, keeps only these 118 series, and caches them with the file’s date, so it is downloaded again only when BLS posts a new version (about once a month).

**How close.** Reproduces the published charts exactly: both lines of all eight charts, over all 441 months since January 1990, agree to within 0.000001 point (the site publishes them unrounded). The nightly check compares the whole history at that tolerance. October 2025, which the household survey did not collect because of the federal shutdown, is absent; the change across it is measured from September to November. Because the adjusted line is pinned to the latest month, its whole history moves slightly with each release — a stale published file therefore fails the check over its entire length, not just at the end.
