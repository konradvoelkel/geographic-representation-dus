#!/usr/bin/env bash
# A/B-Bau aller Seiten wie .github/workflows/pages.yml, aus den Datenpaketen, in eigener Datenwurzel
# (docs/decisions.md, Punkt 66). Anleitung und Aufruf für dieses Repo: scripts/README.md.
#
#   scripts/ab_bau.sh <wurzel> <klon> <venv> [--periode P]... [--vergleich P]... [--stadt P]...
#
# <wurzel>  Ordner für diesen Bau; das Skript schreibt <wurzel>/settings.toml (data_root und
#           cache_root darunter), <wurzel>/bau.log und die Ausgaben von `georep paths`
# <klon>    der Stand, der gebaut wird (Worktree oder `git archive`); seine settings.local.toml
#           verliert gegen GEOREP_SETTINGS
# <venv>    eigenes Venv für diesen Klon (UV_PROJECT_ENVIRONMENT); `uv run` richtet es nach dem
#           Lock des Klons ein
#
# Reihenfolge wie pages.yml: das Standardprofil (bootstrap, run); je --periode bootstrap und run,
# ihre Seite als Unterordner <profil>/ in den Ordner der Stadtseite; je --vergleich nur run, nach
# den Perioden, weil es deren Ausgaben liest; je --stadt bootstrap und run; zuletzt
# `publish --strict-budget`.
#
# Kein `set -e`, es greift in dieser Umgebung nicht zuverlässig (CLAUDE.md): jeder Aufruf prüft
# seinen Exit-Code, keine Prüfung steht hinter einer Pipe. UV_CACHE_DIR, POLARS_MAX_THREADS und die
# übrige Umgebung kommen vom Aufrufer und sind für beide Seiten eines Vergleichs dieselben.
set -u

usage() {
  echo "Aufruf: $0 <wurzel> <klon> <venv> [--periode P]... [--vergleich P]... [--stadt P]..." >&2
  exit 2
}

[ $# -ge 3 ] || usage
root=$(realpath -m "$1") || exit 2
repo=$(realpath -m "$2") || exit 2
venv=$(realpath -m "$3") || exit 2
shift 3
periods=()
compares=()
cities=()
while [ $# -gt 0 ]; do
  case "$1" in
    --periode) [ $# -ge 2 ] || usage; periods+=("$2"); shift 2 ;;
    --vergleich) [ $# -ge 2 ] || usage; compares+=("$2"); shift 2 ;;
    --stadt) [ $# -ge 2 ] || usage; cities+=("$2"); shift 2 ;;
    *) usage ;;
  esac
done
[ -f "$repo/pyproject.toml" ] || { echo "kein Klon von georep: $repo" >&2; exit 2; }

mkdir -p "$root" || exit 1
cat >"$root/settings.toml" <<EOT || exit 1
data_root = "$root/data"
cache_root = "$root/cache"
EOT
export GEOREP_SETTINGS="$root/settings.toml" UV_PROJECT_ENVIRONMENT="$venv"
log="$root/bau.log"
: >"$log" || exit 1
cd "$repo" || exit 1

fail() { echo "FEHLER: $*" | tee -a "$log" >&2; exit 1; }
g() { uv run --frozen georep "$@" >>"$log" 2>&1 || fail "georep $*"; }
# `georep paths` in eine Datei unter <wurzel>, nicht in eine Pipe: so bleibt der Exit-Code sichtbar.
paths_to() {
  local out="$1"
  shift
  uv run --frozen georep "$@" paths >"$out" 2>>"$log" || fail "georep $* paths"
}
value() { sed -n "s/^$1=//p" "$2"; }

g bootstrap
g run
paths_to "$root/main.paths"
main=$(value site "$root/main.paths")
[ -n "$main" ] || fail "georep paths nennt kein site"

for p in "${periods[@]}"; do
  g --profile "$p" bootstrap
  g --profile "$p" run
  paths_to "$root/period.paths" --profile "$p"
  sub=$(value site "$root/period.paths")
  prof=$(value profile "$root/period.paths")
  [ -n "$sub" ] && [ -n "$prof" ] || fail "georep --profile $p paths nennt site oder profile nicht"
  rm -rf "${main:?}/$prof" || exit 1
  cp -r "$sub" "$main/$prof" || exit 1
done
for p in "${compares[@]}"; do
  g --profile "$p" run
done
for p in "${cities[@]}"; do
  g --profile "$p" bootstrap
  g --profile "$p" run
done
g publish --strict-budget
echo "fertig: $root"
