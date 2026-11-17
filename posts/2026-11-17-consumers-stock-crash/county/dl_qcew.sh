#!/bin/bash
# Download QCEW quarterly singlefiles, 1990 onward, politely (2 at a time).
W="$1"; UA="${UA:-econvitals replication package (set UA to your own contact)}"
dl() { y=$1; f="$W/raw/qcew/${y}_qtrly_singlefile.zip"; [ -s "$f" ] && unzip -tq "$f" >/dev/null 2>&1 && { echo "$y have"; return; }
  for i in 1 2 3 4; do curl -s -f -A "$UA" -o "$f.part" "https://data.bls.gov/cew/data/files/$y/csv/${y}_qtrly_singlefile.zip" && mv "$f.part" "$f" && echo "$y ok $(stat -f %z "$f")" && return; sleep $((i*10)); done; echo "$y FAILED"; }
export -f dl; export W UA
seq 1990 2026 | xargs -P 2 -I{} bash -c 'dl {}'
