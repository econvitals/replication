#!/bin/bash
# County college share (2000 Census SF3, ACS 5-year) and the 500+ firm employment share (QWI)
# from the Census API. Needs your own Census API key in the environment variable CENSUS_API_KEY (free at api.census.gov/data/key_signup.html).
# Usage: bash 04_census_api.sh <out dir>
set -u
OUT=$1; mkdir -p "$OUT"; K="${CENSUS_API_KEY:?set CENSUS_API_KEY}"
B="https://api.census.gov/data"
curl -s -m 180 -o "$OUT/sf3_2000.json" "$B/2000/dec/sf3?get=P037001,P037015,P037016,P037017,P037018,P037032,P037033,P037034,P037035&for=county:*&in=state:*&key=$K"
for y in 2012 2015 2020 2023; do
  curl -s -m 180 -o "$OUT/acs5_$y.json" "$B/$y/acs/acs5?get=B15003_001E,B15003_022E,B15003_023E,B15003_024E,B15003_025E&for=county:*&in=state:*&key=$K"
done
for s in 01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56; do
  curl -s -m 180 -o "$OUT/qwi_$s.json" "$B/timeseries/qwi/sa?get=Emp&for=county:*&in=state:$s&year=2008&year=2012&year=2016&year=2019&quarter=1&ownercode=A05&firmsize=0&firmsize=5&key=$K"
done
ls -la "$OUT" | awk '{print $5, $9}' | sort -n | head -5
