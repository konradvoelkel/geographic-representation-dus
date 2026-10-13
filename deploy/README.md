# Betrieb: die laufende Wahlperiode fortschreiben

Ein Lauf holt die seit dem letzten Mal geänderten Ratsdokumente, lädt deren PDFs, extrahiert die
Texte, rechnet die Kette und stellt zwei Seiten zusammen: die Hauptseite (Periode 2020 bis 2025,
aus der Referenz) und darunter `2025/` die laufende Periode. Beide Seiten kommen aus dem Ordner
ihres Profils (`<data_root>/<slug>/site/` und `<data_root>/2025/site/`, decisions.md Punkt 52);
welcher das ist, fragt das Skript mit `georep paths` und nicht die Umgebungsdatei. Alles
Rechnerspezifische steht in `monitor.env`, nichts im Skript. Hintergrund und Entscheidungen: `docs/plans/07-monitoring.md`,
Architektur: `docs/architecture.md` (Abschnitt „Betrieb").

| Datei | Zweck |
|---|---|
| `bin/georep-monitor.sh` | der Lauf: sync, bootstrap, fetch, run, Hauptseite, `out/`, R2, VPS, Stand |
| `monitor.env.example` | Vorlage der Konfiguration (Pfade, Ziele, Takt der Aufbewahrung) |
| `systemd/georep-monitor.service` | die Einheit; dieselbe Datei für Nutzer- und Systeminstanz |
| `systemd/georep-monitor.timer` | täglich 04:17 plus bis zu 30 min, verpasste Läufe werden nachgeholt |
| `systemd/georep-monitor.service.d/r2.conf.example` | Drop-in für die rclone-Zugangsdaten (R2) |

## Installation auf kookaburra (Nutzereinheit)

```bash
mkdir -p ~/.config/georep ~/.config/systemd/user
cp deploy/monitor.env.example ~/.config/georep/monitor.env   # Pfade eintragen
chmod 600 ~/.config/georep/monitor.env
cp deploy/systemd/georep-monitor.service deploy/systemd/georep-monitor.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start georep-monitor.service    # ein Lauf von Hand
journalctl --user -u georep-monitor -n 50 --no-pager
systemctl --user enable --now georep-monitor.timer   # erst, wenn der erste Lauf gut war
systemctl --user list-timers georep-monitor.timer
```

`Linger=yes` ist für den Nutzer gesetzt (`loginctl show-user konrad`), der Timer läuft also auch
ohne Anmeldung. Ein Lauf ohne Timer, mit derselben Umgebung und eigenem Journal:

```bash
systemd-run --user --collect --unit=georep-monitor-hand \
  -p EnvironmentFile="$HOME/.config/georep/monitor.env" \
  /usr/bin/bash "$PWD/deploy/bin/georep-monitor.sh"
journalctl --user -u georep-monitor-hand -f
```

Der Pfad muss ausgeschrieben sein: `systemd-run` löst in `-p` keine Spezifizierer auf, `%h` endet
mit „Path %h/… is not absolute" und die Einheit startet nicht (geprüft am 2026-10-12 mit einer
transienten Einheit, die nur `true` ausführt). In den Unit-Dateien selbst gilt `%E` dagegen. Aus
demselben Grund steht auch `%d` dort nicht zur Verfügung: wer in einer transienten Einheit
Zugangsdaten braucht, schreibt `$CREDENTIALS_DIRECTORY/rclone.conf` ins Kommando (Playbook § 3.10).

## Was der Lauf tut

1. `uv sync --locked` (beim ersten Mal mit Netz zu PyPI).
2. `georep bootstrap`, dann `georep --profile $MONITOR_PROFILE bootstrap`: die Hauptperiode muss
   zuerst da sein, weil das Profil mit `period.dictionary = "base"` deren Straßen und Orte liest;
   das Profil selbst bekommt nur Wahlergebnis und Stimmbezirke, **keinen** Korpus der Arbeit
   (`seed_corpus = false`).
3. `georep --profile … fetch papers --force`: eine Seite OParl mit `modified_since` (rund 45 bis 85 s).
   Das `--force` muss sein: der Schritt hat keine Eingaben und wäre sonst „aktuell".
4. `georep … fetch pdfs texts`: nur die neuen PDFs (rund 15 je Tag) und deren Texte.
5. `georep … run`: die Offline-Kette bis zur Seite des Profils.
6. `georep bootstrap && GEOREP_REPORT__MONITORING_URL=2025/ georep run`: die Hauptseite aus der
   Referenz, diesmal mit dem Link auf die laufende Periode (GitHub Pages baut sie ohne diesen Link).
   Sie entsteht im Ordner der Stadt, nicht flach unter `data_root`; das Skript liest ihn mit
   `georep paths` (Punkt 52).
7. `out/` zusammenstellen: Hauptseite nach `out/`, Profil nach `out/2025/`, beim ersten Lauf eines
   Monats `out/2025/snapshots/<JJJJ-MM>/` als Kopie der Downloads mit `SHA256SUMS`; ältere über
   `MONITOR_SNAPSHOT_KEEP` hinaus werden entfernt, der Lauf druckt beide Zahlen.
8. Mit `MONITOR_R2_REMOTE`: PDFs und Textstore des Profils nach R2 (`cache/2025/…`), dazu
   `papers.jsonl` und die Parquet-Tabellen. Ohne die Variable passiert nichts.
9. Mit `MONITOR_VPS_HOST`: `rsync -a --chmod=D755,F644 --delete --itemize-changes` nach
   `$MONITOR_VPS_WWW`. Ohne die Variable bleibt die Seite in `$MONITOR_PUBLISH_DIR/out`.
10. `out/2025/stand.json` mit Beginn, Ende, Ergebnis, Zahlen und den Zusammenfassungszeilen; zum
    Schluss eine Zeile im Journal: „n neue Paper, n PDFs, n Texte, Seite n KB, Schnappschuss …".

Die Ausgabe eines Schritts erscheint im Journal erst, wenn der Schritt fertig ist: das Skript
sammelt sie in einer Datei, prüft den Exit-Code und druckt sie dann (eine Prüfung hinter einer Pipe
verlöre ihn). Bei langen Schritten — `fetch pdfs` kann Stunden laufen — steht im Journal also erst
die Zeile „Schritt pdfs: …" und lange nichts; `ps` oder die wachsende Datenwurzel zeigen den
Fortschritt.

Mehrere Läufe stören sich nicht: eine Sperre (`flock` auf `$GEOREP_DATA_ROOT/.monitor.lock`) lässt
nur einen zu, der zweite endet sofort mit „läuft bereits" und Exit 0. Ein Fehler bricht den Lauf
mit Exit 1 ab und nennt den Schritt („FEHLER: papers (Exit 1)"); systemd meldet die Einheit als
`failed`, der Timer versucht es am nächsten Tag wieder.

**Trockenlauf**: `DRY_RUN=1` in `monitor.env` (oder `systemd-run … -p Environment=DRY_RUN=1`). Dann
spricht der Lauf mit nichts von außen: die Netzschritte planen nur, die Kette des Profils plant nur
(ohne Abruf fehlen ihr die Dokumente), rclone und rsync laufen mit `--dry-run`. Die Hauptseite
entsteht wirklich, sie braucht kein Netz.

## Variablen

`monitor.env.example` erklärt jede. Zwei Dinge sind wichtig:

- Das Präfix `MONITOR_` für alles, was nur das Skript braucht. `GEOREP_*` liest pydantic-settings
  als Einstellung; `GEOREP_PROFILE` wählt seit Option 01 das Paketprofil **jedes** Aufrufs, und der
  Lauf braucht zwei davon (die laufende Periode und die Hauptperiode) — darum steht das Profil in
  `MONITOR_PROFILE` und geht je Aufruf als `--profile` mit. Einstellungen gehören bewusst gesetzt:
  `GEOREP_DATA_ROOT`, `GEOREP_CACHE_ROOT`, `GEOREP_LOG_LEVEL`.
- Wohin das Profil schreibt und wie sein Ordner heißt, fragt das Skript mit `georep paths` beim
  Paket ab; in `monitor.env` gehört kein abgeleiteter Pfad.
- `PATH`: systemd kennt keinen Login-PATH (Playbook § 3.2). `uv` und `rclone` liegen in
  `~/.local/bin`; `MONITOR_UV` und `MONITOR_RCLONE` zeigen zusätzlich direkt darauf.

## Erstabruf (einmalig, Konrads Lauf)

Der erste Lauf holt die ganze Periode seit dem 15.09.2025: rund 21 Seiten Metadaten in 16 bis
30 min, danach rund 4 100 PDFs seriell mit einer Sekunde Pause (rund 2,3 h) und die Extraktion
(rund 3 min). Davor lohnt eine Stichprobe mit 50 PDFs (fünf Minuten):

```bash
systemd-run --user --collect --unit=georep-monitor-probe \
  -p EnvironmentFile="$HOME/.config/georep/monitor.env" \
  -p Environment=GEOREP_SOURCES__OPARL__PDF_LIMIT=50 \
  /usr/bin/bash "$HOME/files/work/georep/deploy/bin/georep-monitor.sh"
```

Dateinamen, Textextraktion und Trefferzahl ansehen (`georep --profile $MONITOR_PROFILE status`),
dann denselben Befehl ohne `PDF_LIMIT` als `georep-monitor-erstlauf`. `georep status` zeigt `pdfs`
nach der Stichprobe als „offen: Settings geändert", weil `pdf_limit` im Stamp steht; das ist richtig.

Danach `systemctl --user enable --now georep-monitor.timer` und nach dem ersten Timer-Lauf das
Journal lesen: Seiten, Dauer, übertragene Objekte. Die Zahlen gehören datiert in
`docs/profiling/README.md` und `STATUS.md`.

Gelegentlich (etwa monatlich) lohnt ein Lauf ohne `modified_since`, falls die Serveruhr einmal
springt und ein Paper zwischen zwei Filtern durchfällt — 21 Seiten, 16 bis 30 min:

```bash
GEOREP_SOURCES__OPARL__INCREMENTAL=false georep --profile duesseldorf-2025 fetch papers --force
```

## Konrads Handgriffe, bevor R2 und VPS laufen

1. **R2-Bucket** `georep` im Cloudflare-Konto anlegen: Region WEUR, privat, keine eigene Domain,
   kein `r2.dev`. Ein zweites Bucket kostet nichts; die Abrechnung läuft je Konto über alle Buckets
   (Freibetrag 10 GB-Monat; bubatzblick belegt rund 6,5 GB, georep käme mit rund 0,6 GB dazu und
   wüchse um rund 0,55 GB je Jahr).
2. **Zwei Token** mit „Object Read & Write", je auf dieses Bucket beschränkt: eines für kookaburra,
   eines für den VPS. Nie dasselbe Token zweimal.
3. **`~/.config/georep/rclone.conf`** (0600, nicht im Repo) nach dem Muster aus bubatzblicks
   `DEPLOY.md` § 0:

   ```ini
   [georep]
   type = s3
   provider = Cloudflare
   access_key_id = …
   secret_access_key = …
   endpoint = https://<konto-id>.r2.cloudflarestorage.com
   acl = private
   no_check_bucket = true
   ```

4. In `monitor.env`: `MONITOR_R2_REMOTE=georep:georep`; das Drop-in `r2.conf` aus
   `deploy/systemd/georep-monitor.service.d/r2.conf.example` kopieren, dann `daemon-reload`.
   Ein erster Lauf mit `DRY_RUN=1` listet, überträgt aber nichts.
5. **VPS**: zuerst DNS (`georep.konradvoelkel.de`), dann Caddy — in dieser Reihenfolge, sonst
   droht die ZeroSSL-Falle (Playbook § 3.10). Im Infra-Repo (`~/files/work/server`) eine Rolle
   `georep`: Nutzer, uv, rclone, Klon des Repos, `/etc/georep/monitor.env`, `/etc/georep/rclone.conf`
   per `LoadCredential`, die beiden Unit-Dateien aus `deploy/systemd/` plus ein Härtungs-Drop-in
   (`ProtectSystem=strict`, `ReadWritePaths`, `SystemCallFilter`, wie `bubatz-daily.service.j2`),
   und ein Caddy-Block mit den MIME-Typen `application/vnd.apache.parquet` für `.parquet` und
   `application/geo+json` für `.geojson`.
6. In `monitor.env` des Rechners, der veröffentlicht: `MONITOR_VPS_HOST` und `MONITOR_VPS_WWW`.

## Umzug von kookaburra auf den VPS

Der Cache ist die einzige Datenmenge, die zählt (PDFs und Textstore). Auf dem VPS:
`rclone copy georep:georep/cache/2025 $GEOREP_CACHE_ROOT/2025`, dann einen Lauf starten: die
Stamps entscheiden selbst, was fehlt. Die Metadaten (`papers.jsonl`) kommen genauso aus
`georep:georep/2025/raw/`. Nichts muss neu abgerufen werden.
