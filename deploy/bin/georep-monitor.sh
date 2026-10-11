#!/usr/bin/env bash
# Ein Lauf des Monitorings der laufenden Wahlperiode: holen, rechnen, veröffentlichen.
#
# Idempotent: jeder Schritt entscheidet über seinen Stamp selbst, ein zweiter Lauf ohne neue
# Dokumente ändert nichts. Alles Rechnerspezifische kommt aus der Umgebung (deploy/monitor.env),
# nichts steht hier fest. Aufruf über die systemd-Einheit (siehe deploy/README.md).
#
# Kein `set -e`: es greift in dieser Umgebung nicht zuverlässig (CLAUDE.md) und verdeckt, welcher
# Schritt scheiterte. Jeder Schritt prüft seinen Exit-Code selbst, keine Prüfung hinter einer Pipe.
#
# Mit DRY_RUN=1 spricht der Lauf mit nichts von außen: die Netzschritte planen nur
# (`run --dry-run --online`), die Kette des Profils plant nur (ihr fehlen ohne Abruf die
# Dokumente), rclone und rsync laufen mit `--dry-run`. Die Hauptseite entsteht wirklich, sie
# braucht kein Netz; so hat die Simulation etwas zu zeigen.
set -u

START=$(date +%s)
STARTED=$(date -Is)
SUMMARY=""
SNAPSHOT=nein

log() { printf '%s %s\n' "$(date -Is)" "$*"; }

health() { # Healthcheck anpingen, falls konfiguriert; nie der Grund zu scheitern
  [ -n "${HEALTHCHECK_URL:-}" ] || return 0
  curl -fsS -m 10 -o /dev/null "$HEALTHCHECK_URL$1" || log "Healthcheck $1 nicht erreicht"
}

fail() {
  log "FEHLER: $*"
  health /fail
  exit 1
}

# --- Umgebung ---------------------------------------------------------------------------------
for name in MONITOR_REPO MONITOR_SETTINGS MONITOR_PROFILE MONITOR_PUBLISH_DIR GEOREP_DATA_ROOT; do
  [ -n "${!name:-}" ] || fail "$name ist nicht gesetzt (Vorlage: deploy/monitor.env.example)"
done
UV=${MONITOR_UV:-uv}
RCLONE=${MONITOR_RCLONE:-rclone}
R2_REMOTE=${MONITOR_R2_REMOTE:-}
VPS_HOST=${MONITOR_VPS_HOST:-}
VPS_WWW=${MONITOR_VPS_WWW:-}
SNAPSHOT_KEEP=${MONITOR_SNAPSHOT_KEEP:-24}
HEALTHCHECK_URL=${MONITOR_HEALTHCHECK_URL:-}
DRY_RUN=${DRY_RUN:-}
CACHE_ROOT=${GEOREP_CACHE_ROOT:-$GEOREP_DATA_ROOT/cache}
PROFILE=$MONITOR_PROFILE
OUT=$MONITOR_PUBLISH_DIR/out
MAIN_SITE=$GEOREP_DATA_ROOT/site
PROFILE_SITE=$GEOREP_DATA_ROOT/$PROFILE/site
DRY=()
[ -n "$DRY_RUN" ] && DRY=(--dry-run)

command -v rsync >/dev/null || fail "rsync fehlt"
cd "$MONITOR_REPO" || fail "MONITOR_REPO $MONITOR_REPO ist kein Verzeichnis"
mkdir -p "$GEOREP_DATA_ROOT" "$OUT" || fail "Verzeichnisse anlegen"
WORK=$(mktemp -d) || fail "Arbeitsverzeichnis anlegen"
trap 'rm -rf "$WORK"' EXIT

# --- Nur ein Lauf zur Zeit --------------------------------------------------------------------
LOCK=$GEOREP_DATA_ROOT/.monitor.lock
exec 9>"$LOCK" || fail "Sperrdatei $LOCK"
if ! flock -n 9; then
  log "georep-monitor: läuft bereits ($LOCK), dieser Lauf endet ohne Arbeit"
  exit 0
fi

step() { # step <name> <befehl...>: ausführen, Ausgabe zeigen, Exit-Code prüfen (nie hinter Pipe)
  local name=$1
  shift
  log "Schritt $name: $*"
  "$@" >"$WORK/$name.out" 2>&1
  local code=$?
  cat "$WORK/$name.out"
  [ "$code" -eq 0 ] || fail "$name (Exit $code)"
  SUMMARY="$SUMMARY$(tail -1 "$WORK/$name.out" | tr -d '"\\')
"
}

number() { # number <datei> <wort>: die erste Zahl vor <wort>, sonst 0 (die Prüfung ist erfolgt)
  local found
  found=$(grep -o "[0-9][0-9]* $2" "$1" 2>/dev/null | head -1 | cut -d' ' -f1)
  printf '%s' "${found:-0}"
}

georep() { "$UV" run georep "$@"; }

health /start
log "georep-monitor: Start, Profil $PROFILE, Datenwurzel $GEOREP_DATA_ROOT${DRY_RUN:+, Trockenlauf}"

# (1) Umgebung aus dem Lockfile; beim ersten Lauf braucht das Netz zu PyPI
step sync "$UV" sync --locked

# (2) Eingaben der Referenz in die Datenwurzel des Profils (ohne Korpus der Arbeit)
step bootstrap georep --settings "$MONITOR_SETTINGS" bootstrap

# (3) Metadaten: immer erzwungen, der Schritt hat keine Eingaben und wäre sonst „aktuell"
if [ -n "$DRY_RUN" ]; then
  step papers georep --settings "$MONITOR_SETTINGS" run --dry-run --online papers
else
  step papers georep --settings "$MONITOR_SETTINGS" fetch papers --force
fi

# (4) Neue PDFs und deren Texte
if [ -n "$DRY_RUN" ]; then
  step pdfs georep --settings "$MONITOR_SETTINGS" run --dry-run --online pdfs texts
else
  step pdfs georep --settings "$MONITOR_SETTINGS" fetch pdfs texts
fi

# (5) Die Offline-Kette des Profils bis zur Seite
if [ -n "$DRY_RUN" ]; then
  step run georep --settings "$MONITOR_SETTINGS" run --dry-run
else
  step run georep --settings "$MONITOR_SETTINGS" run
fi

# (6) Die Hauptseite aus der Referenz, mit dem Link auf die laufende Periode
step mainboot georep bootstrap
export GEOREP_REPORT__MONITORING_URL="$PROFILE/"
step mainsite georep run
unset GEOREP_REPORT__MONITORING_URL

# (7) Veröffentlichungsordner zusammenstellen: Hauptseite nach out/, Profil nach out/<profil>/
if [ -d "$MAIN_SITE" ]; then
  rsync -a --delete --exclude="/$PROFILE/" "$MAIN_SITE/" "$OUT/" || fail "Hauptseite nach out/"
else
  log "ohne Hauptseite unter $MAIN_SITE: nichts zu kopieren"
fi
if [ -d "$PROFILE_SITE" ]; then
  mkdir -p "$OUT/$PROFILE" || fail "Profilordner anlegen"
  rsync -a --delete --exclude=/snapshots/ "$PROFILE_SITE/" "$OUT/$PROFILE/" ||
    fail "Profilseite nach out/"
  SNAPSHOTS=$OUT/$PROFILE/snapshots
  MONTH=$(date +%Y-%m)
  if [ -d "$OUT/$PROFILE/data" ] && [ ! -d "$SNAPSHOTS/$MONTH" ]; then
    mkdir -p "$SNAPSHOTS/$MONTH" || fail "Schnappschuss $MONTH anlegen"
    cp -r "$OUT/$PROFILE/data/." "$SNAPSHOTS/$MONTH/" || fail "Schnappschuss $MONTH kopieren"
    (cd "$SNAPSHOTS/$MONTH" && sha256sum -- * >SHA256SUMS) || fail "SHA256SUMS $MONTH"
    SNAPSHOT=$MONTH
  fi
  if [ -d "$SNAPSHOTS" ]; then
    REMOVED=0
    for old in $(ls -1 "$SNAPSHOTS" | sort -r | tail -n +"$((SNAPSHOT_KEEP + 1))"); do
      rm -rf "${SNAPSHOTS:?}/$old" || fail "alten Schnappschuss $old entfernen"
      REMOVED=$((REMOVED + 1))
    done
    log "Schnappschüsse: $(ls -1 "$SNAPSHOTS" | wc -l) behalten, $REMOVED entfernt"
  fi
else
  log "ohne Profilseite unter $PROFILE_SITE: kein Schnappschuss"
fi

PAPERS=$(number "$WORK/papers.out" neu)
PDFS=$(number "$WORK/pdfs.out" geladen)
TEXTS=$(number "$WORK/pdfs.out" extrahiert)
PAGE_KB=0
if [ -f "$OUT/$PROFILE/index.html" ]; then
  PAGE_KB=$(($(wc -c <"$OUT/$PROFILE/index.html") / 1000))
fi

# (8) R2: PDFs und Textstore des Profils sichern, dazu Metadaten und fertige Tabellen
if [ -n "$R2_REMOTE" ]; then
  step r2pdf "$RCLONE" sync "${DRY[@]}" --stats-one-line --exclude manifest.jsonl \
    "$CACHE_ROOT/$PROFILE/pdf" "$R2_REMOTE/cache/$PROFILE/pdf"
  step r2manifest "$RCLONE" copyto "${DRY[@]}" --stats-one-line \
    "$CACHE_ROOT/$PROFILE/pdf/manifest.jsonl" "$R2_REMOTE/cache/$PROFILE/pdf/manifest.jsonl"
  step r2text "$RCLONE" copyto "${DRY[@]}" --stats-one-line \
    "$CACHE_ROOT/$PROFILE/text/texts.parquet" "$R2_REMOTE/cache/$PROFILE/text/texts.parquet"
  step r2raw "$RCLONE" copyto "${DRY[@]}" --stats-one-line \
    "$GEOREP_DATA_ROOT/$PROFILE/raw/papers.jsonl" "$R2_REMOTE/$PROFILE/raw/papers.jsonl"
  step r2processed "$RCLONE" copy "${DRY[@]}" --stats-one-line --include "*.parquet" \
    "$GEOREP_DATA_ROOT/$PROFILE/processed" "$R2_REMOTE/$PROFILE/processed"
else
  log "ohne MONITOR_R2_REMOTE: keine Sicherung in R2"
fi

# (9) VPS: die kanonische rsync-Zeile (Playbook § 3.10)
if [ -n "$VPS_HOST" ]; then
  [ -n "$VPS_WWW" ] || fail "MONITOR_VPS_HOST ohne MONITOR_VPS_WWW"
  log "Schritt vps: rsync nach $VPS_HOST:$VPS_WWW"
  rsync -a --chmod=D755,F644 --delete --itemize-changes "${DRY[@]}" \
    "$OUT/" "$VPS_HOST:$VPS_WWW/" || fail "rsync zum VPS"
else
  log "ohne MONITOR_VPS_HOST: die Seite bleibt in $OUT"
fi

# (10) Stand schreiben und Abschlusszeile drucken
ENDED=$(date -Is)
TOOK=$(($(date +%s) - START))
RESULT=ok
[ -n "$DRY_RUN" ] && RESULT=trocken
mkdir -p "$OUT/$PROFILE" || fail "Standdatei anlegen"
{
  printf '{\n  "profil": "%s",\n  "beginn": "%s",\n  "ende": "%s",\n' "$PROFILE" "$STARTED" "$ENDED"
  printf '  "ergebnis": "%s",\n  "dauer_s": %s,\n' "$RESULT" "$TOOK"
  printf '  "neue_paper": %s,\n  "pdfs": %s,\n  "texte": %s,\n' "$PAPERS" "$PDFS" "$TEXTS"
  printf '  "seite_kb": %s,\n  "schnappschuss": "%s",\n  "schritte": [\n' "$PAGE_KB" "$SNAPSHOT"
  printf '%s' "$SUMMARY" | sed 's/.*/    "&",/' | sed '$ s/,$//'
  printf '  ]\n}\n'
} >"$OUT/$PROFILE/stand.json" || fail "stand.json schreiben"

health ""
log "georep-monitor: $PAPERS neue Paper, $PDFS PDFs, $TEXTS Texte, Seite $PAGE_KB KB, Schnappschuss $SNAPSHOT, Dauer ${TOOK}s"
