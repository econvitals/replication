#!/bin/bash
# Every public input for the county stock-wealth replication, into <dir>/raw/. About 10 GB, mostly QCEW.
# Usage: bash 00_download.sh <dir>        then run_all.sh <dir>
# The Census API pieces (college share, firm size) are fetched by 04_census_api.sh, which needs a Census API key;
# set CENSUS_API_KEY first.
set -u
W=$1; R=$W/raw; mkdir -p $R/qcew $R/irs/zip $R/agg $R/scf $R/census
UA="${UA:-econvitals replication package (set UA to your own contact)}"
get() { for i in 1 2 3 4; do curl -s -f -L -A "$UA" -o "$2.part" "$1" && mv "$2.part" "$2" && return 0; sleep $((i*10)); done; echo "FAILED $1"; }

# BLS QCEW quarterly singlefiles, 1990 onward
for y in $(seq 1990 2026); do [ -s $R/qcew/${y}_qtrly_singlefile.zip ] || get "https://data.bls.gov/cew/data/files/$y/csv/${y}_qtrly_singlefile.zip" $R/qcew/${y}_qtrly_singlefile.zip; done

# IRS SOI county income (1989-2009 zips; 2010 zip; 2011+ csv, with and without AGI classes) and ZIP-code files 2004-2010
for y in $(seq 1989 2009); do get "https://www.irs.gov/pub/irs-soi/${y}countyincome.zip" $R/irs/${y}countyincome.zip; done
get "https://www.irs.gov/pub/irs-soi/2010countydata.zip" $R/irs/2010countydata.zip
for y in $(seq 11 23); do
  if [ $y = 12 ]; then get "https://www.irs.gov/pub/irs-soi/12cyallnoagi.csv" $R/irs/12cyallnoagi.csv
  else get "https://www.irs.gov/pub/irs-soi/${y}incyallnoagi.csv" $R/irs/${y}incyallnoagi.csv; fi
done
for y in $(seq 2004 2010); do get "https://www.irs.gov/pub/irs-soi/${y}zipcode.zip" $R/irs/zip/${y}zipcode.zip; done
get "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_county_rel_10.txt" $R/irs/zcta_county_rel_10.txt

# National series: Ken French factors, Gurkaynak-Sack-Wright curve, Shiller S&P data (BEA and FRED come through macrolib in 03)
get "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip" $R/agg/ff3.zip
get "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv" $R/agg/gsw.csv
get "http://www.econ.yale.edu/~shiller/data/ie_data.xls" $R/agg/ie_data_new.xls    # if this moves, Shiller's site links the current file

# SCF summary extracts, every wave
for y in 1989 1992 1995 1998 2001 2004 2007 2010 2013 2016 2019 2022; do get "https://www.federalreserve.gov/econres/files/scfp${y}s.zip" $R/scf/scfp${y}s.zip; done

# SEER county population by age (19 age groups, 1969-2024)
get "https://seer.cancer.gov/popdata/yr1969_2024.20ages/us.1969_2024.20ages.adjusted.txt.gz" $R/census/seer20.txt.gz
ls -la $R/*/ | head -5
