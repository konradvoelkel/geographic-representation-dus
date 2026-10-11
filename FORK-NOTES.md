# Fork-Notizen

Lokaler Fork von <https://github.com/lubar102/geographic-representation-dus> (Lukas Bartzsch,
Bachelorarbeit HHU, Januar 2026, Lizenz CC0). Remotes: `upstream` = Original,
`origin` = <https://github.com/konradvoelkel/geographic-representation-dus>. Angelegt 2026-10-09.

Was der Code tut, wie man ihn startet und wo was liegt, steht in `README.md`; der Umbau in
`DEVELOPMENT_PLAN.md`, der Stand in `STATUS.md`, der Befund vor dem Umbau in `docs/baseline-2026-10-10.md`.
Hier bleibt nur, was an Konrads Rechner hängt.

## Umgebung auf diesem Rechner

Die Primärplatte ist voll; Projektumgebung und uv-Cache liegen auf der zweiten Platte:

```bash
export UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep
export UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache
uv sync
```

Daten und Cache ebenfalls, über `settings.local.toml` (gitignored):

```toml
data_root = "/media/konrad/xtraspace/georep/data"
cache_root = "/media/konrad/xtraspace/georep/cache"
```

Die alte venv `/media/konrad/xtraspace/venvs/geographic-representation-dus` (Python 3.12, pip-Pins der
Arbeit) wird nicht mehr gebraucht und kann gelöscht werden.

## Push

Das gh-Token hat keinen `workflow`-Scope; Pushes laufen per SSH. In nicht-interaktiven Sitzungen hält der
gcr-Keyring-Agent den Schlüssel: `SSH_AUTH_SOCK=/run/user/1000/gcr/ssh git push`.

## Was die Arbeit anders machte (Stand des Originals, 2026-01-29)

- OParl-Metadaten und PDFs über `requests` ohne Timeout, Abbruch beim ersten Fehler; der Endpunkt
  antwortete am 2026-10-09 mit 85 s pro Seite à 200 Einträge, 365 Seiten für 2020–2025.
- Straßen per osmnx-Graph je Stimmbezirk, Orte per SPARQL und Wikipedia-GeoSearch mit Punkt-in-Polygon in
  einer Schleife, Suche mit FlashText, Aggregation mit pandas, Regression im Notebook mit vier Rechenwegen.
- `TARGET_ENTITY` stand ohne Wirkung neben einer Query mit literalem `Q1718`; `schulweg` zählt in den
  Treffern und fehlt nur in der Anzeige (Kapitel 4.3.5 der Arbeit); beides ist jetzt konfiguriert.
