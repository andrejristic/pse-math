#!/bin/sh
# Run the whole Phase 1-3 (+ addendum) test suite on the Surface.
# Wires the Lean toolchain (if present) and the offscreen Qt platform.
export PATH="$HOME/.elan/bin:$PATH"
export QT_QPA_PLATFORM=offscreen
cd "$(dirname "$0")" || exit 1

total=0; fails=0
for f in tests/test_*.py; do
    out=$(python3 "$f" 2>&1)
    line=$(echo "$out" | tail -1)
    n=$(echo "$line" | grep -oE '^[0-9]+')
    d=$(echo "$line" | grep -oE '/[0-9]+' | tr -d /)
    printf "%-32s %s\n" "$(basename "$f")" "$line"
    [ -n "$d" ] && total=$((total + d)) && fails=$((fails + d - n))
done
echo "-----"
echo "TOTAL passed: $((total - fails))/$total"
[ "$fails" -eq 0 ] || exit 1
