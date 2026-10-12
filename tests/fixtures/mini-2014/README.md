# Mini-Periode: eine erfundene zweite Wahlperiode

**Alle Zahlen und Flächen hier sind synthetisch und bilden keine Wahl und keinen Datenstand ab.**
Die Fixture ist der Referenzdatensatz (`reference_root`) eines Periodenprofils und prüft die
Kette, nicht die Geschichte: dieselbe Stadt, ein anderer Stimmbezirkszuschnitt, ein
Wahlergebnis im Format der Ratswahl 2020 und Dokumente mit zurückdatiertem Datum.

Erzeugt aus `tests/fixtures/mini/` (den drei Wahlbezirken 1, 10 und 38 der Arbeit) mit

```bash
uv run python -m tests.fixtures.make_mini --period
```

Die Funktion ist `write_period_fixture` in [../make_mini.py](../make_mini.py); sie ist
deterministisch, und jede Zahl steht dort als Konstante mit ihrem Grund.

## Was drin ist

| Datei | Inhalt |
|---|---|
| `external/Stimmbezirke_2020.geojson` | 26 Stimmbezirke, EPSG:4647, einzige Eigenschaft `Stimmbezchar` (wie das Original von 2020). Entstanden aus den 22 Stimmbezirken von 2025: jeder vierte an der Senkrechten durch seinen Schwerpunkt geteilt (Kennung `…a`, `…b`), dann zwei Paare über Wahlbezirksgrenzen hinweg vereinigt (Kennung `…m`). Die beiden mehrteiligen Stimmbezirke liegen in zwei Zielbezirken und machen den Flächen-Crosswalk nicht trivial — in den echten Daten sind 83 der 316 Stimmbezirke von 2020 geteilt. |
| `external/Kommunalwahlbezirke.geojson` | drei Wahlbezirke 101, 110, 138 mit `Kommunalwahlbezirk` und `Name`, als Vereinigung je eines Drittels der nach Nummer sortierten Stimmbezirke. Der Zuschnitt unterscheidet sich damit absichtlich vom Zuschnitt 2025, wie 2020 gegen 2025. |
| `external/Stimmbezirk_Wahlergebnis.csv` | 26 Urnen- und 6 Briefwahlbezirke im Format der Ratswahl 2020 (`A1;A2;A3;A;B;B2;C;D;D1…D6`, UTF-8, `;`). Wahlberechtigte = Flächenanteil mal Wahlberechtigte 2025, 30 % davon mit Sperrvermerk W, 45 % Wahlbeteiligung, Stimmen in den Parteiverhältnissen von 2025; die Briefwahlbezirke tragen `A` = 0 und zusammen 80 % der Wahlscheine ihres Wahlbezirks. |
| `external/Wahlbezirk_Wahlergebnis.csv` | drei Zeilen, jede exakt die Summe ihrer Stimmbezirks- und Briefwahlzeilen. Dadurch gehen die drei Summenproben des Schritts `voters` auf, und ein Fehler in der Zuordnung fällt auf. |
| `raw/papers.jsonl` | 100 Dokumente: jedes zweite der 200 aus `tests/fixtures/mini/`, Datum um sechs Jahre zurück (2014-09-14 bis 2019-09-12, ganz in der Periode), Kennungen und URLs unverändert. |
| `cache/text/texts.parquet` | die Texte dieser 100 Dokumente, Herkunft `fixture`. |

Zusammen rund 330 KB. `bootstrap` erkennt an `raw/papers.jsonl` und `cache/text/texts.parquet`
das native Format und kopiert beide, statt einen Korpus im Altformat umzurechnen — genau wie
später beim echten Schnappschuss der Periode 2014 bis 2020.

## Was nicht drin ist

Straßen und Orte: das Profil setzt `period.dictionary = "base"` und liest das Wörterbuch der
Hauptperiode. Ein `expected/`-Verzeichnis gibt es nicht; der Golden Master der Arbeit liegt
unter `tests/fixtures/mini/expected/` und wird von dieser Fixture nicht berührt.
