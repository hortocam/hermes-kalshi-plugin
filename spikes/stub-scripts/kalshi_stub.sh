#!/bin/sh
# S3 stub: appends a line per run so firing time and profile can be verified.
OUT="${HERMES_HOME:-/tmp}/plugin-data/hermes-kalshi-spike-s3.log"
mkdir -p "$(dirname "$OUT")"
echo "$(date -u +%FT%TZ) local=$(TZ=America/New_York date +%FT%T%z) home=$HERMES_HOME" >> "$OUT"
