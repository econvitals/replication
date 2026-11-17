# Real Retail Sales

**On Econvitals:** the retail sales Flash email (“Adjusted for inflation, retail sales were … and the control group was …”, and the inflation-adjusted panel of its table). The full series is published as [`data/real-retail-sales.json`](https://raw.githubusercontent.com/econvitals/econvitals-data/main/data/real-retail-sales.json). Method note: [Methods](https://econvitals.org/methods/#real-retail-sales).

**What it is.** The Census Bureau publishes retail sales in dollars only. The usual shortcut divides them by the headline consumer price index. But about two-thirds of the CPI is services that stores do not sell, and for the control group the headline CPI rose about 1.7 points a year faster than BEA’s price for the same goods (2012–2026). Econvitals instead deflates each kind of store by the CPI prices of what it sells:

| Kind of store (Census code) | CPI prices used |
|:--:|:--:|
| Motor vehicles and parts (441) | New vehicles 60%, used cars and trucks 30%, parts and equipment 10% |
| Furniture and home furnishings (442) | Furniture and bedding, window and floor coverings and linens, other household equipment and furnishings (by CPI weight) |
| Electronics and appliances (443) | Appliances, video and audio products, information technology goods (by CPI weight) |
| Building materials and garden (444) | Tools, hardware, outdoor equipment and supplies |
| Food and beverage stores (445) | Food at home, alcoholic beverages at home (by CPI weight) |
| Health and personal care (446) | Medical care commodities, personal care products (by CPI weight) |
| Gasoline stations (447) | Motor fuel 80%, food at home 10%, tobacco 10% |
| Clothing and accessories (448) | Apparel |
| Sporting goods, hobby, books (451) | Sporting goods, other recreational goods, recreational reading materials (by CPI weight) |
| General merchandise (452) | Core goods 60%, food at home 40% |
| Miscellaneous stores (453) | Core goods (goods other than food and energy) |
| Nonstore retailers (454) | Core goods |
| Food services and drinking places (722) | Food away from home, alcoholic beverages away from home (by CPI weight) |

“By CPI weight” means BLS’s relative importance of each price in December of the year before (the 2012 weights before 2013). The fixed shares are judgments: the car-dealer split fits BEA’s motor vehicle price better than CPI weights do. Electronics stores, whose own prices start in the late 1990s, use core goods until then. The October 2025 CPI, which BLS never published, is filled by log-linear interpolation.

The totals (all retail and food services; excluding autos; excluding autos and gasoline; excluding food services; and the control group, which is the total less autos, gasoline, building materials and restaurants) are combined with a Törnqvist index: each month’s price change for a total is the average of its stores’ price changes, weighted by their shares of sales in that month and the month before. Real sales are nominal sales divided by that price index (2017 = 100), in millions of 2017 dollars, monthly, seasonally adjusted, from 1992.

**Run it.** `python replicate.py` (needs a free `CENSUS_API_KEY`). Writes `output/real_retail.csv`: `real_<line>` and `price_<line>` for `total`, `ex_autos`, `ex_autos_gas`, `ex_food_services` and `control`.

**Data.**
- Census Bureau, Monthly Retail Trade (dataset `timeseries/eits/marts`), seasonally adjusted sales (`SM`) by category, from the Census API.
- BLS CPI, seasonally adjusted U.S. city average indexes `CUSR0000` + `SETA01`, `SETA02`, `SETC`, `SEHJ`, `SEHH`, `SEHL`, `SEHK`, `SERAC`, `SEEEC`, `SEHM`, `SAF11`, `SEFW`, `SAM1`, `SEGB`, `SETB`, `SEGA`, `SAA`, `SERC`, `SERE`, `SERG`, `SACL1E`, `SEFV`, `SEFX`, and the relative importances (aspect `I`) from the CPI bulk files at download.bls.gov (no key).

**How close.** Reproduces the published series exactly: checked every night over the whole history (1992 on), the price indexes to their four published decimals and real sales to the published tenth of a million dollars. Econvitals adds each year’s December weights in February, when BLS publishes them; `LAST_RI_YEAR` in the script holds the last year it has and moves with it.
