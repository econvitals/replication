#!/bin/bash
# Rebuild the county estimates after 00_download.sh: bash run_all.sh <dir>. About an hour; the panel takes ~650 MB.
set -e
D=$(cd "$(dirname "$0")" && pwd); W=$1; P=${PY:-python3}; C=${PY:-python3}; cd /tmp
mkdir -p $W/out/qcew $W/logs
for g in "1990 1994 1998 2002 2006 2010 2014 2018 2022 2026" "1991 1995 1999 2003 2007 2011 2015 2019 2023" "1992 1996 2000 2004 2008 2012 2016 2020 2024" "1993 1997 2001 2005 2009 2013 2017 2021 2025"; do
  $P -I $D/01_qcew_extract.py $W/raw/qcew $W/out/qcew $g & done; wait
$P -I $D/02_irs_build.py $W/raw/irs $W/out          # the paper's splice (kept for comparison)
$P -I $D/02b_irs_clean.py $W/out                    # the splice used downstream
$C -I $D/03_aggregates.py $W/raw/agg $W/out         # NOTE: reads BEA and FRED through the author's private macrolib; see README.md
bash $D/04_census_api.sh $W/raw/census/api
$P -I $D/05_demog_scf.py $W
$P -I $D/06_wealth.py $W
$P -I $D/07_panel.py $W
$P -I $D/08_results.py $W table1,periods,interacted,asymmetry A > $W/logs/08A.log 2>&1 &
$P -I $D/08_results.py $W paths B > $W/logs/08B.log 2>&1 &
$P -I $D/08_results.py $W rolling,robust C > $W/logs/08C.log 2>&1 &
wait
$P -I -c "import pandas as pd,sys; o=sys.argv[1]; pd.concat([pd.read_csv(f'{o}/results_{t}.csv') for t in 'ABC']).to_csv(f'{o}/results.csv', index=False)" $W/out
