# Paket ähnliche Dokumente Düsseldorf (Hauptperiode, gepackt am 2026-11-24)

Die **zehn ähnlichsten Dokumente je Ratsdokument** der Wahlperiode 2020 bis 2025, nach dem
Skalarprodukt ihrer Dokumentvektoren aus `nomic-embed-text-v2-moe` (Vorhaben 18,
`docs/plans/18-einbettungen.md`; Entscheidung „Einbettungen über Stücke, ähnliche Dokumente als
Paket" in `docs/decisions.md`). Nur die Nachbartabelle, keine Vektoren: die Seite braucht nur die
IDs, und die Vektoren (Dokumentvektoren 25,7 MiB als float16, Stückvektoren 64 MiB) bleiben auf dem
Rechner mit Modell (Messdokument § 3.4, Frage 9.1; aus Einbettungen lässt sich Text teilweise
zurückgewinnen, Frage 9.7).

Das Paket gibt es, weil GitHub Pages weder GPU noch Modell hat: ohne Paket schriebe der Schritt
`neighbors` dort eine leere Tabelle. Geprüft ist die Tabelle an 50 Ankern gegen zwei KI-Kodierer
(Präzision@5 0,832, Wilson 0,781 bis 0,873; Messdokument § 4.4); Kodierer und Schlichter sind
dasselbe Modell, kein menschlicher Goldstandard.

Erzeugt mit

```bash
georep bootstrap && georep run
flock /media/konrad/xtraspace/georep/gpu-queue/gpu.lock georep run --models embeddings neighbors
georep pack --neighbors snapshots/duesseldorf-aehnlich
```

`profiles/duesseldorf.toml` nennt die Datei als `[embeddings].neighbors_package`. `bootstrap` legt sie
nach `raw/aehnliche_dokumente_paket.parquet`, **wenn jede `id` und jeder `nachbar` ein Paper der
Periode ist** (`georep.bootstrap.overlay_neighbors`); die Periodenprofile nehmen den Schlüssel
zurück. Der Schritt `neighbors` liest sie nur, wo es keine Dokumentvektoren gibt; gibt es sie,
rechnet er aus ihnen dieselbe Tabelle. Der Ordner wird **nur gelesen**; die pre-commit-Hooks lassen
`snapshots/` aus, und `.gitattributes` hält die Bytes unverändert.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `raw/aehnliche_dokumente_paket.parquet` | 905 998 | `18885e78d32c43b11aaf166c9ac56e5171482e36c43a666b210f8f0842cba60d` |

Zusammen 905 998 Bytes, Schema-Version 1 (`search.vectors.NEIGHBORS_SCHEMA_VERSION`), mit zstd auf
Stufe 19 geschrieben. `tests/unit/test_data_packages.py` hält diese Tabelle gegen die Datei im Repo
und, als `slow`-Test, die Invarianten der Tabelle.

## Spalten

| Spalte | Typ | Inhalt |
|---|---|---|
| `id` | String | Korpus-ID (OParl `id` des Papers) |
| `rang` | Int64 | 1 bis 10, lückenlos |
| `nachbar` | String | die kleinste Korpus-ID der Nachbardatei; nie dieselbe Datei wie `id` |
| `aehnlichkeit` | Float32 | Skalarprodukt der normierten Dokumentvektoren, auf vier Stellen gerundet; je `id` fallend |

Sortiert nach `id, rang`. Der Rang folgt der **ungerundeten** Ähnlichkeit (float32), fallend;
Gleichstände der ungerundeten Ähnlichkeit stehen nach ID, auch an der Grenze zum zehnten Platz.
Gerundet können zwei Nachbarn gleich aussehen und trotzdem nicht nach ID stehen: von den 1 300
Paaren benachbarter Ränge mit gleicher gerundeter Ähnlichkeit stehen 647 nicht nach ID. Mit
`georep pack --neighbors` am 2026-11-24 nach Runde 1 des Reviews neu gepackt: die Datei ist
bytegleich (SHA-256 unten unverändert).

## Zahlen des Laufs

| Größe | Wert |
|---|---|
| Zeilen | 190 320 |
| Korpus-IDs mit Nachbarn | 19 032 von 19 108 (76 ohne Rohtext: kein PDF, ein leeres oder ein Scan ohne Text) |
| Nachbarn je ID | 10 |
| Stücke | 47 407 (47 312 verschiedene Texte), alle aus dem Modellcache der Messung, 0 neu gerechnet |
| Rechenzeit | `embeddings` 7,4 s (Stücke bilden, Cache lesen), `neighbors` 4,2 s (Blöcke zu 2 048, float32, CPU) |
| gleich der Messung | alle 190 320 Zeilen (ID, Rang, Nachbar, Ähnlichkeit) gleich der Probe `groessen/aehnliche_dokumente.parquet` des Messskripts |

## Modell der Vektoren

| Angabe | Wert |
|---|---|
| Modell | `nomic-embed-text-v2-moe:latest` (ollama 0.24.0, F16, 768 Dimensionen, Fenster 512 Token) |
| Digest | `ff9c2f10ef5e3722623a1b396e1e04efc27a93112c83e9b7b7b9ca1d05620965` |
| Prompt-Version der Stücke | `18-stuecke-1` (Präfix `search_document: `, Titel bis 200 Zeichen, Stücke bis 1 600 Zeichen, Überlappung 200) |
| Schlüssel der Optionen | `1868f0241d5a` (`num_ctx` 512, `truncate`) |
| Dokumentvektor | `18-dokvektor-1`: Mittel der ersten drei Stückvektoren, normiert |
| abgewiesene Eingaben | 0 |

## Herkunft und Lizenz

| Angabe | Wert |
|---|---|
| Quelle der Texte | die Hauptdateien der Ratsdokumente, Ratsinformationssystem der Landeshauptstadt Düsseldorf (OParl 1.1), Body `0015`, gelesen mit pypdf 7.1.0 (`snapshots/duesseldorf-rohtexte`) |
| Lizenz der Ratsdokumente | auf den Seiten des Anbieters nicht angegeben (wie bei den übrigen Ratsdokumenten) |
| Modell | `nomic-embed-text-v2-moe` von Nomic AI; `ollama show --license` nennt keine Lizenz, die Modellseite nach Erinnerung Apache 2.0, nicht nachgesehen (Frage 9.6 des Messdokuments) |

Das Paket trägt keinen Text, nur IDs und Zahlen.

## Was im Paket **nicht** liegt

- die Vektoren (`processed/einbettungen_stuecke.parquet`, `processed/einbettungen_dokumente.parquet`),
- der Modellcache (`cache_root/ml/nomic-embed-text-v2-moe_latest.sqlite`),
- die Stamps (`*.stamp.json`) und alles andere Abgeleitete.
