#!/bin/bash
LT="$HOME/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe"
cd "$(dirname "$0")"
for f in "$@"; do ( s=$(date +%s); wine "$LT" -b $f.asc >/dev/null 2>&1; echo "$f done in $(( $(date +%s)-s )) s" ) & done
wait
