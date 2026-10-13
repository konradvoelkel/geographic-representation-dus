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
for name in MONITOR_REPO MONITOR_PROFILE MONITOR_PUBLISH_DIR GEOREP_DATA_ROOT; do
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
OUT=$MONITOR_PUBLISH_DIR/out
DRY=()
[ -n "$DRY_RUN" ] && DRY=(--dry-run)

command -v rsync >/dev/null || fail "rsync fehlt"
command -v flock >/dev/null || fail "flock fehlt (sonst liefe jeder Lauf ungesperrt)"
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

query() { # query <name> <befehl...>: wie step, aber ohne Zeile im Journal und ohne Stand
  local name=$1
  shift
  "$@" >"$WORK/$name.out" 2>&1
  local code=$?
  if [ "$code" -ne 0 ]; then
    cat "$WORK/$name.out"
    fail "$name (Exit $code)"
  fi
}

value_of() { # value_of <datei> <schlüssel>: der Wert aus key=wert (die Prüfung ist erfolgt)
  local found
  found=$(grep -m1 "^$2=" "$1" | cut -d= -f2-)
  [ -n "$found" ] || fail "$2 fehlt in der Ausgabe von georep paths"
  printf '%s' "$found"
}

number() { # number <datei> <wort>: die erste Zahl vor <wort>, sonst 0 (die Prüfung ist erfolgt)
  local found
  found=$(grep -o "[0-9][0-9]* $2" "$1" 2>/dev/null | head -1 | cut -d' ' -f1)
  printf '%s' "${found:-0}"
}

georep() { "$UV" run georep "$@"; }

health /start
log "georep-monitor: Start, Datenwurzel $GEOREP_DATA_ROOT${DRY_RUN:+, Trockenlauf}"

# (1) Umgebung aus dem Lockfile; beim ersten Lauf braucht das Netz zu PyPI
step sync "$UV" sync --locked

# Profilname und Pfade kommen aus dem Paket: sonst stünden sie hier ein zweites Mal, und ein
# Tippfehler in der Umgebungsdatei ließe den Lauf am falschen Ort suchen (Review 2026-10-12).
query paths georep --profile "$MONITOR_PROFILE" paths
PROFILE=$(value_of "$WORK/paths.out" profile)
PROFILE_SITE=$(value_of "$WORK/paths.out" site)
PDF_DIR=$(value_of "$WORK/paths.out" pdf_dir)
PDF_MANIFEST=$(value_of "$WORK/paths.out" pdf_manifest)
TEXT_STORE=$(value_of "$WORK/paths.out" text_store)
PAPERS_JSONL=$(value_of "$WORK/paths.out" papers)
PROCESSED=$(value_of "$WORK/paths.out" processed)
# Dasselbe für die Hauptperiode: ihr Profil heißt wie der Slug ihrer Stadt und ihre Seite liegt in
# deren Ordner (decisions.md Punkt 52). Der Name kommt aus base_profile und nicht aus
# default_profile: mit dem Periodenprofil einer anderen Stadt wäre das sonst die falsche
# Hauptseite (Review 2026-10-13).
BASE_PROFILE=$(value_of "$WORK/paths.out" base_profile)
query mainpaths georep --profile "$BASE_PROFILE" paths
MAIN_SITE=$(value_of "$WORK/mainpaths.out" site)
log "Profil $PROFILE, Seite unter $PROFILE_SITE; Hauptperiode $BASE_PROFILE unter $MAIN_SITE"

# (2) Eingaben der Referenz: erst die Hauptperiode (das Profil liest mit
# `period.dictionary = "base"` deren Straßen und Orte), dann das Profil selbst ohne Korpus
step mainboot georep --profile "$BASE_PROFILE" bootstrap
step bootstrap georep --profile "$MONITOR_PROFILE" bootstrap

# (3) Metadaten: immer erzwungen, der Schritt hat keine Eingaben und wäre sonst „aktuell"
if [ -n "$DRY_RUN" ]; then
  step papers georep --profile "$MONITOR_PROFILE" run --dry-run --online papers
else
  step papers georep --profile "$MONITOR_PROFILE" fetch papers --force
fi

# (4) Neue PDFs und deren Texte
if [ -n "$DRY_RUN" ]; then
  step pdfs georep --profile "$MONITOR_PROFILE" run --dry-run --online pdfs texts
else
  step pdfs georep --profile "$MONITOR_PROFILE" fetch pdfs texts
fi

# (5) Die Offline-Kette des Profils bis zur Seite
if [ -n "$DRY_RUN" ]; then
  step run georep --profile "$MONITOR_PROFILE" run --dry-run
else
  step run georep --profile "$MONITOR_PROFILE" run
fi

# (6) Die Hauptseite aus der Referenz, mit dem Link auf die laufende Periode (bootstrap lief in (2))
export GEOREP_REPORT__MONITORING_URL="$PROFILE/"
step mainsite georep --profile "$BASE_PROFILE" run
unset GEOREP_REPORT__MONITORING_URL

# (7) Veröffentlichungsordner zusammenstellen: Hauptseite nach out/, Profil nach out/<profil>/.
# Die Stamps der Schritte (index.html.stamp.json) bleiben draußen, sie gehören zur Datenwurzel.
# Geprüft wird index.html, nicht das Verzeichnis: `bootstrap` legt ein leeres site/ an, und im
# Trockenlauf bleibt es leer (2026-10-12 in der Simulation aufgefallen).
if [ -f "$MAIN_SITE/index.html" ]; then
  rsync -a --delete --exclude="/$PROFILE/" --exclude="*.stamp.json" \
    "$MAIN_SITE/" "$OUT/" || fail "Hauptseite nach out/"
elif [ -n "$DRY_RUN" ]; then
  log "Trockenlauf: ohne Hauptseite unter $MAIN_SITE nichts zu kopieren"
else
  fail "Hauptseite fehlt unter $MAIN_SITE, obwohl der Lauf durchlief"
fi
if [ -f "$PROFILE_SITE/index.html" ]; then
  mkdir -p "$OUT/$PROFILE" || fail "Profilordner anlegen"
  rsync -a --delete --exclude=/snapshots/ --exclude=/stand.json --exclude="*.stamp.json" \
    "$PROFILE_SITE/" "$OUT/$PROFILE/" || fail "Profilseite nach out/"
  SNAPSHOTS=$OUT/$PROFILE/snapshots
  MONTH=$(date +%Y-%m)
  if [ -n "$(ls -A "$OUT/$PROFILE/data" 2>/dev/null)" ] && [ ! -d "$SNAPSHOTS/$MONTH" ]; then
    # Erst daneben bauen, dann hineinschieben: der Monatsordner ist die Sperre fuer alle spaeteren
    # Laeufe, und ein abgebrochener cp haette sie mit einem halben Schnappschuss gesetzt (Review
    # 2026-10-12). Der Arbeitsordner liegt im selben Dateisystem, mv ist dort ein rename.
    STAGING=$SNAPSHOTS/.$MONTH.neu
    rm -rf "$STAGING" || fail "Arbeitsordner $STAGING entfernen"
    mkdir -p "$STAGING" || fail "Schnappschuss $MONTH anlegen"
    cp -r "$OUT/$PROFILE/data/." "$STAGING/" || fail "Schnappschuss $MONTH kopieren"
    (cd "$STAGING" && sha256sum -- * >SHA256SUMS) || fail "SHA256SUMS $MONTH"
    mv "$STAGING" "$SNAPSHOTS/$MONTH" || fail "Schnappschuss $MONTH einhaengen"
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
elif [ -n "$DRY_RUN" ]; then
  log "Trockenlauf: ohne Profilseite unter $PROFILE_SITE kein Schnappschuss"
else
  fail "Profilseite fehlt unter $PROFILE_SITE, obwohl der Lauf durchlief"
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
    "$PDF_DIR" "$R2_REMOTE/cache/$PROFILE/pdf"
  step r2manifest "$RCLONE" copyto "${DRY[@]}" --stats-one-line \
    "$PDF_MANIFEST" "$R2_REMOTE/cache/$PROFILE/pdf/manifest.jsonl"
  step r2text "$RCLONE" copyto "${DRY[@]}" --stats-one-line \
    "$TEXT_STORE" "$R2_REMOTE/cache/$PROFILE/text/texts.parquet"
  step r2raw "$RCLONE" copyto "${DRY[@]}" --stats-one-line \
    "$PAPERS_JSONL" "$R2_REMOTE/$PROFILE/raw/papers.jsonl"
  step r2processed "$RCLONE" copy "${DRY[@]}" --stats-one-line --include "*.parquet" \
    "$PROCESSED" "$R2_REMOTE/$PROFILE/processed"
else
  log "ohne MONITOR_R2_REMOTE: keine Sicherung in R2"
fi

# (9) Stand schreiben, bevor übertragen wird: sonst fehlt er im veröffentlichten Baum. `dauer_s`
# zählt darum bis hierher, ohne die Übertragung; die Abschlusszeile nennt die ganze Dauer.
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

# (10) VPS: die kanonische rsync-Zeile (Playbook § 3.10)
if [ -n "$VPS_HOST" ]; then
  [ -n "$VPS_WWW" ] || fail "MONITOR_VPS_HOST ohne MONITOR_VPS_WWW"
  log "Schritt vps: rsync nach $VPS_HOST:$VPS_WWW"
  rsync -a --chmod=D755,F644 --delete --itemize-changes "${DRY[@]}" \
    "$OUT/" "$VPS_HOST:$VPS_WWW/" || fail "rsync zum VPS"
else
  log "ohne MONITOR_VPS_HOST: die Seite bleibt in $OUT"
fi

health ""
log "georep-monitor: $PAPERS neue Paper, $PDFS PDFs, $TEXTS Texte, Seite $PAGE_KB KB, Schnappschuss $SNAPSHOT, Dauer $(($(date +%s) - START))s"
