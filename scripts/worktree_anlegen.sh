#!/usr/bin/env bash
# Worktree für ein Vorhaben auf eigenem Branch anlegen, mit eigener settings.local.toml
# (docs/plan-vorverarbeitung-2026-11.md, § 6). Anleitung: scripts/README.md.
#
#   scripts/worktree_anlegen.sh <wurzel> <branch> <name> [<cache_root>]
#
# Legt <wurzel>/<name> auf dem neuen Branch <branch> ab `main` an und schreibt dort eine
# settings.local.toml mit data_root = <wurzel>/<name>/data und, wenn angegeben, dem geteilten
# cache_root. Venv, `uv sync`, bootstrap und run macht der Agent danach selbst, mit eigenem
# UV_PROJECT_ENVIRONMENT. Aufruf aus einem beliebigen Verzeichnis: das Repo ist das, in dem dieses
# Skript liegt.
set -u

[ $# -ge 3 ] && [ $# -le 4 ] || {
  echo "Aufruf: $0 <wurzel> <branch> <name> [<cache_root>]" >&2
  exit 2
}
root=$(realpath -m "$1") || exit 2
branch="$2"
name="$3"
cache="${4:-}"
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel) || exit 1
wt="$root/$name"
if [ -e "$wt" ]; then echo "existiert schon: $wt" >&2; exit 1; fi
git -C "$repo" worktree add "$wt" -b "$branch" main || exit 1
{
  echo "data_root = \"$wt/data\""
  if [ -n "$cache" ]; then echo "cache_root = \"$(realpath -m "$cache")\""; fi
} >"$wt/settings.local.toml" || exit 1
echo "$wt"
