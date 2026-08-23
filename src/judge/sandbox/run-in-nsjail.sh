#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: run-in-nsjail <python3.12|cpp17|java21> <source-file> [input-file]
Source and input files must be under /sandbox.
EOF
  exit 64
}

[[ $# -ge 2 && $# -le 3 ]] || usage
language="$1"
source="$2"
input="${3:-}"

# Do not allow a caller to escape the per-run workspace through a path argument.
case "$source" in
  /sandbox/*) ;;
  *) echo "source must be under /sandbox" >&2; exit 64 ;;
esac
if [[ -n "$input" ]]; then
  case "$input" in
    /sandbox/*) ;;
    *) echo "input must be under /sandbox" >&2; exit 64 ;;
  esac
fi

source_q=$(printf '%q' "$source")
case "$language" in
  python3.12)
    jailed_command="exec python3.12 $source_q"
    ;;
  cpp17)
    jailed_command="g++ -std=c++17 -O2 -pipe -o /sandbox/Main $source_q && exec /sandbox/Main"
    ;;
  java21)
    jailed_command="javac $source_q && exec java -Xmx256m -cp /sandbox Main"
    ;;
  *)
    echo "unsupported language" >&2
    exit 64
    ;;
esac

# Compilation and execution both happen inside nsjail. stdin is passed through.
if [[ -n "$input" ]]; then
  exec nsjail --config /etc/pigeonoj/nsjail.cfg --time_limit 5 -- /bin/sh -c "$jailed_command" < "$input"
else
  exec nsjail --config /etc/pigeonoj/nsjail.cfg --time_limit 5 -- /bin/sh -c "$jailed_command"
fi
