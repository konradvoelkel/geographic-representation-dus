# Synergien der Vorverarbeitung 2026-11

Stand 2026-11-23, geschrieben für den Supervisor nach Lesen der Messdokumente
[11-struktur.md](11-struktur.md), [12-kennungen.md](12-kennungen.md),
[13-dubletten.md](13-dubletten.md), [14-vorgaenge.md](14-vorgaenge.md),
[15-funktion.md](15-funktion.md), [16-ortsbezug.md](16-ortsbezug.md), [17-zeit.md](17-zeit.md),
[22-bedarf.md](22-bedarf.md) und der Sammlung [25-quellen.md](25-quellen.md), der Fundamente F2, F3,
F4 und F6 auf `main` (Punkte 69 bis 71 in [../decisions.md](../decisions.md)) und der Branches
`fund/F1-rohtext` und `fund/F5-modelle`. Meta-Plan:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 9, Haltepunkt A. Vorbild:
[00-synergien.md](00-synergien.md) (Ausbau 2026-10).

Haltepunkt A ist am 2026-11-23 noch nicht ganz erreicht: F4 ist auf `main` (`v0.19.0`, `v0.20.0`),
F1 und F5 sind in Review-Runden, 13 ist kodiert (α 0,941) und wird ausgewertet, die Regel „handelt
von" von 16 hat das Kriterium verfehlt (F1 0,772) und geht mit Nebenregel C in eine Bestätigungsrunde
(Stand: [README.md](README.md)). Was davon abhängt, ist unten als offen markiert. Der Supervisor hat
den Entwurf eines Agenten geprüft und die Entscheidungen in § 3.1, Punkt 4, getroffen.
Was sich je Messdokument ändert, steht kurz in § 4 und
gehört ausführlich in § 10 des jeweiligen Dokuments.

**Umfang der Stufe 2 und 3 auf einen Blick** (§ 7): sieben Vorhaben mit Urteil „bauen" (11, 12, 14,
15, 16 in Teilen, 17, 22), 13 vorläufig „verwerfen". Zusammen 13 neue Schritte, 19 neue Dateien unter
`processed/`, 14 veröffentlichte Tabellen, vier Unterseiten (eine fünfte, `orte.html`, nur wenn nötig),
41 Atom-Feeds, drei neue kleine Datenpakete. Keines der sieben braucht die GPU, keines braucht Konrads
Netzlauf aus F6 für Stufe 2.

## 1. Gemeinsame Bausteine

| Baustein | Wer braucht ihn | Wer hat ihn geplant | Auflösung |
|---|---|---|---|
| **Rohtext je Dokument** (`RawTextStore`, Seiten mit `\f`, `flatten` zum Textstore) | 11, 12, 16; später 18, 20, 21 | F1 (`fund/F1-rohtext`, `prep/raw_texts.py`) | F1 besitzt Store, Paket und `flatten`. Der Store ist nach **Dateiname** geschlüsselt, nicht nach Korpus-ID (Architektur auf dem Branch, Modul `stores`) |
| **Zeilen mit Positionen** (`split_lines`: Zeilenumbruch und Seitenwechsel trennen) | 11, 16, 20 | 11 (Messskript, `split_lines`) | wandert mit 11 nach `prep/raw_texts.py` neben `flatten` (textneutral, nicht strukturspezifisch); 16 und 20 importieren von dort |
| **Positionsbrücke Rohtext ↔ Textstore** (je Zeichen des kleingeschriebenen Texts die Stelle im Rohtext) | 16 (Stelle je Treffer), 14 und 17 (Spannen auf dem Rohtext, § 2, Konflikt 1) | 16 (`store_view`, Messskript; 19 075 von 19 076 Dokumenten gleich dem Store) | als `flatten_with_offsets(raw, marker, form_feeds) -> (text, offsets)` neben `flatten` in `prep/raw_texts.py`, mit der Eigenschaft `flatten_with_offsets(...)[0] == flatten(...)`. Muss die gespeicherten Offsets der 9 Dokumente mit `\f` im Seitentext kennen (Supervisor-Entscheidung zu F1). Fundament-Nachzug nach dem Merge von F1 (§ 3.1), nicht Teil von 16 |
| **Abschnitte** (Betreff, Beschlussvorschlag, Sachdarstellung, Fragen, Kopf) | 12 (`section`), 16 (Stelle), 20, 21, 24; später 14 Regel e | 11 | 11 besitzt sie. Eine Funktion `section_of(spans, sections)` (Intervall-Join, Abschnitt der Ebene 1 je Spanne) kommt mit 11 nach `georep.spans`; 12, 16 und 17 rufen sie statt eigener Joins |
| **Spanne lesen ohne Seitenkopfzeilen** (`page_noise` im Profil) | 11, 16, 20 | 11 (§ 9, Frage 9.6) | mit 11 als `read_span(text, start, end, noise)` in `georep.spans`; die Spannen behalten die rohen Offsets |
| **Spannen-Schema F3** (`id, start, end, kind, value, norm, section, extractor`, Int64, Folge `id, start, end, kind`) | 11, 12, 14, 16, 17; später 28 | F3 auf `main` ([../../src/georep/spans.py](../../src/georep/spans.py)) | jeder Plan nimmt `sort_spans` und `check_spans` unverändert; Abweichungen in § 2 (Konflikte 1 bis 3) |
| **Attribute je Dokument**, Schlüssel `id`, eine Zeile je Korpus-ID | 11 (`dokumente_kopf`), 13 (`dokumentfamilien`), 14 (`vorgaenge`), 15 (`dokumente_funktion`, `mitantraege`), 17 (`bundesvokabular`) | Konvention aus [00-synergien.md](00-synergien.md), § 5.6; Prädikat `contracts.one_row_per_document` liegt vor | Vertrag `one_row_per_document` überall. Dateiname nach der Konvention `dokumente_<attribut>.parquet`: Vorschlag `dokumente_vorgang` (14), `dokumente_antragsteller` (15), `dokumente_bundesvokabular` (17), `dokumente_familie` (13). Die Namen sind Downloadnamen; jetzt ist Umbenennen billig |
| **Dokument je PDF-Datei** (mehrere Korpus-IDs teilen eine Datei: 19 108 Paper, 19 093 Dateien in der Hauptperiode, 12 § 2) | 11, 12, 16 (alle, die den Rohtext lesen) | 12 („je Datei die kleinste ID"), 11 („eine Zeile je Korpus-ID") | **jede** Korpus-ID der Datei bekommt die Spannen und die Zeile; sonst fehlen 15 IDs in jedem Join auf `id`. Eine Hilfsfunktion `ids_by_file(papers)` mit F1 oder 11 |
| **Fundstellen außerhalb des Texts** (Titel, Dokumentart, Anlagenname, Nummer) | 11 (`beschlussvorschlag_quelle`), 14 (`felder`, `quelle`), 15 (`quelle`), 16 (Stelle `titel`), 17 (`kopf`) | je Plan eigene Werte | gemeinsame Werte für dieselbe Sache: `titel` (OParl `name`), `art` (`paper_type`), `anlage`, `nummer`; im Text gilt der Abschnitt aus 11. Spaltennamen bleiben je Plan |
| **Ämter und Dezernate** | 11 (Kopf: Amt, Amtsbezeichnung), 12 (Verwaltungseinheit), 24 (Dezernat und Parteibuch je Zeitraum) | 11 § 6, 12 § 6 und Frage 2, Briefing 24 | das **Ämterverzeichnis** (Nummer → Name) entsteht je Lauf aus `dokumente_kopf` von 11, keine Liste im Profil. Die **Dezernatsverteilung** (Amt → Dezernat, Beigeordnete mit Partei, Gültigkeit, Quelle) ist eine Profiltabelle, die 24 sammelt; 12 baut keine und wartet nicht darauf |
| **Ratsmehrheit, Kooperation, Sitze je Periode** | 15 (K3), 24 (Kooperation), 28 (Fraktionsstärken), 25 (Vereinbarungen) | 15 (`[[functions.majorities]]`, Belege aus dem Korpus), 25 (Sitze und drei Vereinbarungen mit Beleg, § 1 und § 2 dort) | **ein** stadtweiter Block im Stadtprofil, nicht unter `functions` und nicht unter `[council]` (das ist der Abrufblock von F6 und steht außerhalb des Fingerprints, Punkt 70). 15 legt ihn an; Quelle je Zeile die Vereinbarung aus 25 mit Datum, dazu der Korpusbeleg. 24 und 28 lesen ihn |
| **Beobachtet/erwartet gegen die Praxis der Gremien** | 14 (Antworten je Fraktion, § 3.8), 15 (Instrumente je Fraktion, § 3.7) | beide je für sich | eine reine Funktion in `analysis/` (Schicht Gremium und Periode), gebaut von 15 (merged früher fertig, § 3); 14 nutzt sie in Stufe 3 |
| **Vorab festgelegte Hypothesen** (Holm, Ergebnistabelle, Satz mit Commit auf der Seite) | 17 (H17.1 bis H17.3), 22 (H1 bis H3); später 21, 24, 27; Vorschläge H15.1, H15.2, H17.4, H1′, H3′ | 17 (`zeit_hypothesen`), 22 (`bedarf_hypothesen`) mit verschiedenen Spalten | ein gemeinsamer Kern: `hypothese`, `p`, `p_holm`, `ergebnis` (`bestätigt`, `nicht bestätigt`, `vorläufig`), `n`, `festgelegt` (Commit); Zusatzspalten je Vorhaben. `holm` und die Wortwahl in `analysis/hypotheses.py`, gebaut von 17, genutzt von 22 |
| **Punkte und Adressen → Wahlbezirk** | 22 (Unfälle, Zensuszellen, Schulen), 16 (Hausnummern), 21 | 22 (`crosswalk.point_shares` mit Band, `cells_to_districts`), 16 (Adresse → Stimmbezirk → Wahlbezirk, eigenes Skript) | 22 besitzt `point_shares` in `georep/crosswalk.py`; Band 0 ist die scharfe Zuordnung. 16 baut sein Adresspaket damit, nicht mit eigener Punkt-in-Fläche-Logik |
| **Fremddaten unter `fremddaten/`** (GebRef NRW, Schulen, Kitas, Stadtteile, Unfallatlas, Zensus, Programme) | 16, 22, 25, später 23 (Cherif) | 22 hat GebRef, Schulen und Kitas geladen, 16 nutzt sie ohne zweiten Abruf; 25 die Programme | je Quelle ein Ordner mit README (Quelle, Datum, Bytes, SHA-256, Lizenz wörtlich), nie doppelt geladen. Ins Repo nur **abgeleitete Auszüge über `georep pack`** unter `snapshots/<stadt>-<name>/`; unverändert gespeicherte Portaldateien unter `context/` (CLAUDE.md, „Nie"); geschützte Texte (25) nur lokal |
| **Datenpakete aus einem Lauf** (`pack --<art>`, `bootstrap`, `test_data_packages.py`) | F1 (Rohtexte, 16,3 MiB), 14 (Anlagen, 519 KB), 16 (Adressen, 92 827 Bytes), 22 (Bedarf, rund 1 MB), 12 optional | je Plan eine eigene Option | Anhängeregel (§ 2.1) oder ein Paketregister (§ 3.1, Vorschlag); Größenbudget in § 2, Konflikt 12 |
| **Validierung über F4** (`validierung/<NN-name>-f4/`, `guete.json` mit `satz` und `alpha_genuegt`) | Stufe 3 aller Vorhaben | F4 ([../validierung.md](../validierung.md), § 3 Schritt 8) | Stufe 3 liest nur `-f4`-Ordner. Es fehlen: 12 Runde 2 (`labels-2.csv` liegt nur im alten Ordner), die Rückfallregel von 14 (104 / 106 rechnet das Messskript, nicht `score`), 16 und 13 (in Kodierung). Der Satz auf der Seite kommt aus `guete.json`, wortgleich für alle, mit „desselben Modells", bis Frage 19 beantwortet ist |
| **Gremiennamen normalisieren** | 11 (Gremium der Sitzung: nur 27 von 48 wörtlich, § 4.1) | 11 § 5 | über die vorhandenen `prep/bodies.organization_key` und `resolve_organizations` (Punkt 58) und `[bodies]`, keine zweite Normalisierung |
| **Dokumentart-Tabellen** (`paper_type` → Klasse) | 11 (Arten mit erwartetem Beschlussvorschlag), 14 (`procedures.kinds`), 15 (`functions.types`, `type_prefixes`), 17 (`budget_pattern`), Option 04 (`originators.admin_types`, `motion_prefixes`) | je Plan | bleiben je Vorhaben (sie sind so validiert). Neu: **ein** Test, der für jedes Profil jede vorkommende Dokumentart gegen jede Tabelle prüft (abgebildet oder ausdrücklich „sonst"); eine neue Art in einer Periode fällt dann sofort auf. Das Abschneiden der Fraktionsnamen nimmt `originators.motion_prefixes` |
| **Dokumentdialog, nachgeladen** | 14 (`vorgaenge.json`), 18 (ähnliche Dokumente), 26; 13 nur bei „bauen" | 14 § 7 | 14 baut einen allgemeinen Haken in `templates/frame/script.js.j2` (Datei `data/<name>.json`, Zeilen je Dokument); 18 und 26 hängen sich an. `dokumente.json` (2,26 MB) wächst nicht |
| **Unterseiten, die mehrere Vorhaben füllen** | `akteure.html` (15; dann 23, 24, 27, 28), `vorgaenge.html` (14; dann 26) | Briefings | F2 kennt nur eine `Page` je Beitrag. Vor Stufe 3 von 23, 24, 26 bis 28 braucht F2 Abschnitte aus fremden Beiträgen (§ 3.1, später); für Stufe 3 von 14 und 15 nicht |
| **MinHash** | 13, 23 | 13 (Prototyp im Messskript, Parameter vermessen) | geht an 23 (Briefing 13 § 5); baut 13 doch, ein Modul für beide |

## 2. Konflikte und ihre Auflösung

### 2.1 Gemeinsame Dateien

Die Anhängeregel aus [00-synergien.md](00-synergien.md), § 2, gilt weiter. Neu oder geschärft:

| Datei | Wer | Regel |
|---|---|---|
| `src/georep/enrich/__init__.py` | alle | eine Importzeile und ein Eintrag **am Ende** von `CONTRIBUTIONS`, in Merge-Reihenfolge (§ 3); die Reihenfolge erfüllt die Abhängigkeiten (11 vor 12 und 16). `Contribution.name` ist immer `NN-name` (`11-struktur`), wie der Docstring sagt; 11, 14, 15, 16 und 17 nennen ihren Beitrag nach dem Schritt, 17 plant zwei Beiträge: **ein** Beitrag je Vorhaben, mit allen Schritten |
| `src/georep/settings.py`, `defaults.toml` | 11, 12, 14, 15, 16, 17, 22 (13) | Modell vor `class Settings`, Feld am Ende, Block am Ende von `defaults.toml` mit `# --- Vorhaben NN: <Name>`, Schalter aus. Ausnahme 22: `NeedSettings` am Ende von `ContextSettings` und `[context.need]` (22 ist einziger Eigentümer von `context`); in TOML darf `[context.need]` am Dateiende stehen |
| `src/georep/profiles/duesseldorf.toml` | 11, 12, 14, 15, 16, 17, 22 | je Vorhaben ein Block am Ende mit Kopfzeile; Listen stehen im **Stadtprofil**, weil `deep_merge` Listen ersetzt (15 § 6). Periodenprofile: `duesseldorf-2014.toml` (11), `duesseldorf-2025.toml` (17); `moenchengladbach.toml` (11, 12, 14, 15, 22) |
| `src/georep/layout.py` | 13, 22 | **keine neuen Properties**: die Pfade gehören dem Modul (`<modul>_files(layout)`), wie F6 es mit `council_files` vorgemacht hat (Punkt 70). Damit fällt die Datei als Konfliktstelle weg |
| `src/georep/pack.py`, `cli.py` (`pack`), `bootstrap.py`, `tests/unit/test_data_packages.py` | F1, 14, 16, 22 (12 optional) | je Paket eine Funktion am Ende von `pack.py`, eine Option am Ende des `pack`-Parsers, ein Eintrag am Ende der Kopierliste und der Pakettabelle des Tests, je mit Kommentar `# Vorhaben NN`. Besser: Paketregister (§ 3.1) |
| `src/georep/analysis/weights.py`, `settings.FIXED_VARIANTS`, Schritt `weights` in `pipeline.py` | 16 (`ortsbezug`, `stelle`), 13 (`familie`, nur bei „bauen") | 16 ist Eigentümer; die Namen am Ende von `FIXED_VARIANTS`. Setzt den zweiten Einhängepunkt voraus (Konflikt 6) |
| `src/georep/crosswalk.py`, `prep/context.py` | 22 | 22 allein; 16 und 21 rufen `point_shares` nur auf |
| `src/georep/spans.py` | 11 (`section_of`, `read_span`), F3-Nachzug (Konflikt 3) | 11 hängt Funktionen an, das Schema ändert nur der Supervisor |
| `src/georep/prep/raw_texts.py` | F1, Nachzug (`flatten_with_offsets`), 11 (`split_lines`) | Funktionen am Ende des Moduls, je in `VERIFY_TARGETS`, wenn rein |
| `src/georep/templates/frame/script.js.j2` | 14 (Dialog-Haken), später 18, 26 | 14 baut den Haken; spätere hängen nur Daten an |
| `src/georep/oparl.py`, `records.py` | 14 (Anlagen im `PaperRecord`) | F6 hat das ausdrücklich 14 oder 26 überlassen (Punkt 70, „Verworfen"); es ist ein Schema-Sprung des Korpus mit Golden-Master-Risiko. Vorschlag: in Stufe 2 nicht, das Anlagenpaket genügt (§ 4, 14) |
| `pyproject.toml`, `uv.lock` | 17 (Paketdaten `lexika/*.toml`, lxml in der Entwicklungsgruppe), jede Version | 17 eigener Commit für die Paketdaten; lxml nur nach Entscheidung (§ 3.1) und mit `uv lock --upgrade-package lxml` |
| `noxfile.py` (`MUTATION_SCOPE`, `VERIFY_TARGETS`) | 13, F1, jedes Vorhaben mit reinen Funktionen | Einträge am Ende, Kommentar `# Vorhaben NN` |
| `tests/unit/__snapshots__/test_cli.ambr` (`georep steps`) | alle mit Schritten | wie 2026-10: jeder Branch erneuert den Snapshot bewusst (Diff im Commit), der Supervisor rendert ihn beim Merge neu und liest den Diff |
| `.github/workflows/pages.yml` | 17 (`cycle_tests`) | Konflikt 13; Änderung durch den Supervisor |
| `docs/architecture.md`, `decisions.md`, `CHANGELOG.md`, `STATUS.md` | alle | Textkonflikte, Supervisor beim Merge; Punktnummern beim Merge |

Namen: Die neuen Schrittnamen (`sections`, `identifiers`, `references`, `procedures`, `functions`,
`cosponsors`, `places`, `cycles`, `vocabulary`, `cycle_tests`, `feeds`, `need_data`, `need`) kollidieren
weder mit den Kernschritten (`opendata` bis `compare`, `report`) noch mit F1 (`raw_texts`) oder F6
(`meetings`, `consultations`, `persons`) noch untereinander. Die Settings-Schlüssel (`structure`,
`identifiers`, `procedures`, `functions`, `places`, `cycles`, `feeds`, `context.need`, bei 13
`families`) kollidieren nicht mit den vorhandenen Feldern von `Settings` noch mit `ml` (F5). Die
Seitennamen (`vorgaenge`, `akteure`, `zeit`, `bedarf`, `orte`) sind eindeutig und nicht reserviert.

### 2.2 Inhaltliche Konflikte

1. **Zwei Textgrundlagen für Spannen.** 11, 12 und 16 rechnen auf dem Rohtext (F1), 14 (`verweise`,
   [14-vorgaenge.md](14-vorgaenge.md), § 6) und 17 (`bundesvokabular_spannen`,
   [17-zeit.md](17-zeit.md), § 6) auf dem kleingeschriebenen Textstore. F3 erlaubt beides über
   `extractor` (Punkt 69), aber `section` aus 11 gibt es nur auf dem Rohtext, und die Kodierbögen von
   F4 zeigen Rohtext. Dazu legt 14 Treffer im **Titel** und im **Anlagennamen** als Spannen an
   (`section` = `titel` | `text` | `anlage`): das sind keine Stellen im Text, und `check_spans` prüft
   gegen die Länge eines Texts je Dokument. **Auflösung**: Spannen nur für Stellen im Text; 14 und 17
   schreiben sie über `flatten_with_offsets` auf den Rohtext (`extractor` nennt den Rohtext, `section`
   aus 11). Titel- und Anlagentreffer stehen nur in `vorgang_kanten` (`felder`, `quelle`). Ist der
   Nachzug nicht rechtzeitig da, bleiben 14 und 17 auf dem Store, mit `section = ""`, F3-konform.
2. **Typen und Folge der Spannen.** 11 und 16 planen `start`, `end` als UInt32 und die Folge
   `id, start` ([11-struktur.md](11-struktur.md), § 6; [16-ortsbezug.md](16-ortsbezug.md), § 6); F3
   hat Int64 und `id, start, end, kind`, und `check_spans` verwirft jedes andere Schema.
   **Auflösung**: F3 gilt; beide nehmen `sort_spans`.
3. **Zusatzspalte an Spannen.** 12 plant `attr` (Form eines Betrags oder Termins,
   [12-kennungen.md](12-kennungen.md), § 6 und Frage 1); 11 hat die gleiche Frage für `quelle` mit
   „nein" beantwortet (Frage 9.3). `check_spans` vergleicht das Schema exakt. **Entscheidung des
   Supervisors (2026-11-23)**: F3 erlaubt Spalten **hinter** den acht, `check_spans` prüft die acht in
   Folge und mit ihren Typen; dann trägt 12 `attr`, 11 bleibt bei seiner Lösung, und 28 hat später
   Platz. Verworfen: `attr` in einer Nebentabelle (ein Join mehr für jeden Leser, ohne dass F3
   dadurch einfacher würde).
4. **Datei gegen ID.** 12 nimmt je Datei die kleinste ID, 11 schreibt eine Zeile je Korpus-ID.
   **Auflösung**: jede ID (§ 1, „Dokument je PDF-Datei").
5. **Doppelt geplant: das Amt im Kopf und die Termine der Beratungsfolge.** 11 liest das Amt aus dem
   Kopf (`dokumente_kopf.amt_nr`, Präzision 125 / 125), 12 dasselbe als `amt` mit `section = kopf`
   (Verwaltungseinheit, Fassung 2, 0,956 über Kopf und Text). 12 behält Termine aus Kopf und
   Beratungsfolge (Frage 7), die 11 als `beratungsfolge.datum` führt. **Auflösung**: beide bauen, wie
   validiert; **Quelle für das federführende Amt und die Beratungsfolge ist 11**, 12 für Nennungen im
   Text. Ein slow-Test vergleicht das Kopf-Amt beider; eine Abweichung ist ein Befund, kein Umbau.
6. **Gewichtsvarianten brauchen einen Schritt vor `weights`.** F2 hängt die Beiträge unmittelbar vor
   `report` ein, also hinter `weights` ([../../src/georep/pipeline.py](../../src/georep/pipeline.py):
   `… body_hits, weights, controls, parties, compare, *contributed, report`). 16 will
   `document_weights` um einen Faktor erweitern (§ 6), 13 eine Variante `familie`; der Kernschritt
   `weights` liefe dann vor der Ausgabe, die er liest. **Auflösung**: F2-Nachzug, ein zweiter
   Einhängepunkt hinter `index` und vor `weights` (`Contribution.early_steps` oder ein Feld `stage`);
   `sections` (11) und `places` (16) hängen dort. Verworfen: `weights` hinter die Beiträge schieben
   (verschiebt den Kern) und eine eigene Gewichtstabelle für 16 (dann müsste `report/model.py` sie
   lesen, genau die Stelle, die F2 schützen soll).
7. **Ein Netzschritt ohne Transport.** 22 plant `need_data` als Netzschritt; `Contribution.steps`
   bekommt `(settings, layout)`, nicht `http` (der Meta-Plan, § 7, sah `steps(settings, layout,
   http)` vor). Ohne die Naht gibt es keinen Test mit Fake-Session (CLAUDE.md, „Nie").
   **Auflösung**: F2-Nachzug, `steps(settings, layout, http)`; heute ist `CONTRIBUTIONS` leer, die
   Änderung kostet nichts.
8. **11 will die validierte Regel nachschärfen.** [11-struktur.md](11-struktur.md), § 5: „Stufe 2
   schärft das Ende des Beschlussvorschlags". Die 12 Fehler sind an den 200 Labels gefunden; eine
   Nachschärfung daran ist eine Entwurfsschätzung (die Lehre aus 12 und 14). Und 16 hat seine Stelle
   und seine Stichprobe auf `struktur-entwurf-1` gerechnet. **Auflösung**: Stufe 2 baut
   `struktur-entwurf-1` als `struktur-1` unverändert (188 / 200); eine geschärfte Fassung nur als
   `struktur-2` mit frischer Bestätigungsstichprobe, wie 12 Runde 2. Die Normalisierung der
   Gremiennamen ist davon unberührt (das Feld `sitzung` ist nicht im Kriterium).
9. **16 hat das Kriterium ergänzt.** [16-ortsbezug.md](16-ortsbezug.md), § 5 und Frage 9.2: eine Regel
   besteht nur, wenn zusätzlich das κ-Intervall über 0 liegt. Kriterien ändert nur der Supervisor vor
   der Messung (Meta-Plan, § 4). Die Labels liegen (195 / 200 einig, α 0,917), ausgewertet gegen die
   Regel ist noch nicht. **Entschieden**: der Supervisor hat die Zusatzbedingung am 2026-11-23 vor der
   Auswertung bestätigt (F1 ≥ 0,8 unverändert, dazu κ-Intervall über 0 und der Vergleich mit der
   trivialen Regel daneben). Die Regel verfehlte F1 (0,772), die Bedingung entschied also nichts; sie
   gilt für die Bestätigungsrunde von Nebenregel C ebenso.
10. **Zwei Zählungen der Parteien.** Option 04 besitzt die Urheberklasse und `parteien`
    ([00-synergien.md](00-synergien.md), § 2, Punkt 1); 15 zeigt, dass `parteien` bei 281 Dokumenten
    Mitantragsteller übersieht, und baut eigene `antragsteller` (119 / 119). `index.html` zählt dann
    „Dokumente je Partei" anders als `akteure.html`. 14 will in Stufe 3 Antwortzeiten je Fraktion.
    **Auflösung**: 14 nimmt die Fraktion aus 15 (`fraktionen`), nicht aus `parteien`; `akteure.html`
    nennt den Unterschied mit Zahl. Ob Option 04 nachzieht, ändert eine Zahl der Hauptseite: Frage an
    Konrad (§ 6, Nr. 25).
11. **Wo abgeleitete Fremddaten liegen.** 22 legt Stadtauszüge aus Unfallatlas, Zensus und Schuldaten
    nach `context/bedarf/` ([22-bedarf.md](22-bedarf.md), § 6); `context/` hält nach CLAUDE.md
    Portaldateien **unverändert**. 16 legt seinen GebRef-Auszug nach `snapshots/duesseldorf-adressen/`
    über `pack --addresses`. 14 will die Anlagen Mönchengladbachs in `reference/moenchengladbach/raw/`
    schreiben. **Auflösung**: abgeleitete Auszüge nur über `georep pack` nach
    `snapshots/<stadt>-<name>/` (`duesseldorf-bedarf`, `duesseldorf-anlagen`,
    `moenchengladbach-anlagen`, `moenchengladbach-bedarf`); `reference/moenchengladbach/` bleibt, wie
    es ist.
12. **Das Paketbudget.** Mit dem Rohtext der Hauptperiode liegen alle Pakete bei 169 von 180 MiB
    (`TOTAL_LIMIT`, Frage 18, 2026-11-23). Stufe 2 bringt Anlagen (519 KB plus Mönchengladbach,
    Größe offen), Adressen (0,09 MB) und Bedarf (rund 1 MB als CSV): rund 1,7 MB, das passt. Die
    Einbettungen von 18 (float16, rund 30 MB, Meta-Plan § 6) passen nicht. 12 braucht kein Paket
    (`kennungen.parquet` rechnet aus dem Rohtextpaket in unter einer Minute); `pack --identifiers`
    entfällt. **Auflösung**: Frage 18 um die neuen Pakete und die Einbettungen erweitern (§ 6, Nr. 26).
13. **Reihenfolge der Profile auf Pages.** 17 rechnet `cycle_tests` im Hauptprofil aus den Ausgaben
    von `duesseldorf-2014` und `duesseldorf-2025` ([17-zeit.md](17-zeit.md), Frage 9.9). `pages.yml`
    baut das Hauptprofil **zuerst**, danach 2014, Vergleich, 2025, Mönchengladbach. **Auflösung**:
    `cycle_tests` läuft im Hauptprofil in einem zweiten `georep run` am Ende des Workflows, oder in
    einem eigenen Profil wie `compare` (`duesseldorf-vergleich`); der Supervisor ändert `pages.yml`.
    Fehlt eine Eingabe, bricht der Schritt mit Namen ab, wie `compare`.
14. **Rohtext auf Pages nur für die Hauptperiode** (Annahme zu Frage 18). Der Meta-Plan, § 2.13,
    verlangt Stufe 2 für jedes Profil mit Eingaben. **Auflösung**: 11, 12 und 16 laufen lokal für alle
    Profile, auf Pages nur, wo ein Rohtextpaket liegt; ohne Store sollen ihre Ausgaben fehlen, ohne
    dass der Lauf scheitert (F1 behandelt einen leeren Store schon wie einen fehlenden, Commit
    `aac75a4` auf dem Branch; ob die Schritte von 11, 12 und 16 dann übersprungen werden, legt ihr
    Bauplan fest, offen). Die Unterseiten nennen das.
15. **Validierungszahlen für die Seite.** Stufe 3 liest `guete.json` (F4). Für 14 steht dort die
    Präzision der ganzen Regel (0,927 und 0,850), nicht die der Rückfallregel (104 / 106, aus dem
    Messskript über zwei Runden); für 12 fehlt Runde 2 im Format von F4. **Auflösung**: F4-Nachzug
    (§ 3.1); bis dahin kommt keine dieser Zahlen auf die Seite.
16. **Wahltage.** `period.election` heißt „die Wahl, deren Ergebnis Nenner und Zuschnitt liefert"
    (`duesseldorf-2014.toml`: 2020-09-13), nicht der Wahltag am Beginn. 17 führt darum zu Recht eine
    eigene Liste `cycles.elections`. Kein Konflikt, aber eine Falle für 21, 24 und 27: wer Wahltage
    braucht, liest `cycles.elections`.
17. **Annahmen der Briefings, die die Messungen widerlegen.** 21 rechnet mit Beträgen **mit Rolle**
    und einem Abschnitt Finanzen; die Rolle fällt (12, Präzision 0,508), „Finanzielle Auswirkungen"
    steht in 0,6 % der Dokumente (11, § 3.1). 24 rechnet mit dem adressierten Amt aus 11 und 12;
    **Anfragen haben kein Amtsfeld** (11, § 3.3: Amt 0 %; 12, § 3.2: Amt in 6 % der Anfragen). Beides
    gehört vor die Stufe 1 der beiden (§ 4).

## 3. Merge- und Bau-Reihenfolge der Stufe 2

### 3.1 Vorarbeiten auf `main`, vor dem ersten Merge einer Stufe 2

Je ein Merge mit eigener Version, wie § 2.12 des Meta-Plans; der Supervisor darf zwei kurz
aufeinanderfolgende in eine Version fassen.

1. **F5** (Modellnaht) nach der Nachprüfung des Reviewers, dann **F1** (Rohtext). Keines der sieben
   Vorhaben braucht F5; 11, 12 und 16 brauchen F1.
2. **Fundament-Nachzug** (Supervisor, Refactoring mit A/B-Bau wie Punkt 69):
   - F2: `steps(settings, layout, http)` (Konflikt 7); zweiter Einhängepunkt vor `weights`
     (Konflikt 6); je ein Test.
   - F1: `flatten_with_offsets` mit Eigenschaftstest gegen `flatten`, über die Hauptperiode geprüft
     wie in [16-ortsbezug.md](16-ortsbezug.md), § 3.0 (Konflikt 1).
   - F3: Entscheidung über Zusatzspalten (Konflikt 3).
   - Vorschlag, nicht Pflicht: ein **Paketregister** (`Contribution.packages`: Option, Quelle,
     Zielordner, README-Prüfung), das `pack`, `bootstrap` und `test_data_packages.py` lesen. Vier
     neue Pakete in Stufe 2 und das von F1 würden sonst je fünf gemeinsame Stellen berühren.
3. **F4-Nachzug**: 12 Runde 2 als `12-kennungen-2-f4` mit `guete.json`; die Rückfallregel von 14 als
   Verfahren in `score` (nur starke Kanten, beide Runden) oder die Prüfstichprobe aus Frage 9.18 als
   `14-vorgaenge-3-f4`; 16 und 13 nach Schlichtung als `-f4`.
4. **Entscheidungen des Supervisors** (nicht Konrads). Getroffen am 2026-11-23: Zusatzspalten in F3
   hinter den acht (Konflikt 3); die Zusatzbedingung von 16 (Konflikt 9); 11 baut `struktur-1`
   unverändert (Konflikt 8); abgeleitete Fremddaten nur über `pack` nach `snapshots/` (Konflikt 11).
   Noch offen: lxml in der Entwicklungsgruppe ([17-zeit.md](17-zeit.md), Frage 9.8); die
   Prüfstichprobe von 14 (rund 50 Rückfall-Kanten, Kodier-Agenten, parallel zu Stufe 2); die Kodierung
   der Klasse `OVA` an 100 Dokumenten der Bezirksvertretungen ([22-bedarf.md](22-bedarf.md), Frage
   22.3), nur wenn H1 auf die Seite soll; der Feed-Link auf `index.html` (17, Frage 9.11: Vorschlag
   nein, Meta-Plan § 4); Name und Ort des Mehrheitenblocks (§ 1); das Endurteil von 13 nach der
   Kodierung.

### 3.2 Worauf jedes Vorhaben wartet

| Vorhaben | Urteil | F1 | Netzlauf F6 | ollama / F5 | sonst |
|---|---|---|---|---|---|
| 11 Struktur | bauen | ja | nein | nein | — |
| 12 Kennungen | bauen (vier Arten) | ja | nein | nein | 11 (`section`); F3-Entscheidung (`attr`) |
| 13 Dubletten | vorläufig verwerfen | nein | nein | nein | Auswertung der Kodierung (α 0,941, läuft); bei „bauen" der Einhängepunkt vor `weights` |
| 14 Vorgänge | bauen, Rückfallregel | nein (ja, wenn Spannen auf Rohtext) | **nein**: die Anlagen kommen aus dem Cache-Auszug als Paket; F6 ist gemerged | nein | Paketentscheidung (Frage 18, 26) |
| 15 Funktion | bauen, Variante B | nein | nein | nein | — |
| 16 Ortsbezug | bauen: Stelle, Hausnummern; Regel umbauen (Nebenregel C, Bestätigungsrunde) | ja | nein | nein | 11 gemerged; Einhängepunkt vor `weights`; Bestätigung von C; `point_shares` aus 22 |
| 17 Zeit | bauen | nein | nein | nein | Reihenfolge in `pages.yml` |
| 22 Bedarf | bauen | nein | nein | nein | `http` an den Beiträgen; Paketentscheidung |

Was auf ollama und F5 wartet: 18, 19, 20 (Stufe 1), dazu Konrads Signal, die angehaltenen Modelläufe
freizugeben ([README.md](README.md), F5). 25 wartet auf 18 und 26. Was auf Konrads Netzlauf wartet: 26,
27, 28 (Stufe 1); 24 ganz erst mit 27; aus „Kandidat" wird in 14 eine Aussage erst mit 26. Der Netzlauf
kann nach Haltepunkt A starten (Runbook [../runbook-sitzungen.md](../runbook-sitzungen.md), § 5).

### 3.3 Plätze und Start

Höchstens sieben Mess- oder Bau-Agenten zugleich (Meta-Plan, § 5). 23 und 24 messen noch und belegen
zwei; es bleiben **fünf Bau-Agenten**. Die drei Reserveplätze gehen an die Reviews von F1 und F5, die
Kodierung von 13 und die Schlichtung von 16.

- **Welle 1**, nach Haltepunkt A und dem Merge von F1: **14, 11, 12, 15, 22.** 14 steht in Konrads
  Reihenfolge vorn (Meta-Plan § 10, Frage 10), 11 und 12 sind die Zulieferer, 15 baut zwei Bausteine,
  die 14 und 24 brauchen (§ 1), 22 ändert Kerndateien (`crosswalk.py`, `prep/context.py`), auf die
  andere später rebasen, und liefert `point_shares` für 16 und 21.
- **Welle 2**, sobald ein Platz frei wird (23 oder 24 fertig, oder ein Merge): **17**, dann **16**
  nach dem Merge von 11; Stelle und Hausnummern baut 16 sofort, die Regel erst nach bestandener
  Bestätigung.
- Ist F1 nicht rechtzeitig gemerged, starten 14, 15, 22 und 17 zuerst; 11, 12 und 16 folgen.

### 3.4 Merge-Reihenfolge

Regel aus dem Meta-Plan, § 8: erst die Zulieferer, dann nach kleinem Fußabdruck. Die Reihenfolge gilt
für den Merge, nicht für den Start; ein fertiger Branch wartet nicht auf einen langsameren, von dem er
nicht abhängt.

| Pos. | Vorhaben | warum an dieser Stelle |
|---|---|---|
| 1 | 11 Struktur | Zulieferer für 12, 16, 20, 21, 24; bringt `section_of`, `read_span`, `split_lines` |
| 2 | 12 Kennungen | liest `section` aus 11; ein Modul, ein Schritt, kein Paket |
| 3 | 14 Vorgänge | Zulieferer für 26 und 29, Konrads erste Wahl; Paket, `pack`, `bootstrap`, Dialog-Haken |
| 4 | 15 Funktion | kleiner Fußabdruck (zwei Schritte, rund 2 s, kein Paket); Mehrheitenblock, beobachtet/erwartet |
| 5 | 17 Zeit | keine Abhängigkeit; Paketdaten in `pyproject.toml`, `pages.yml`; bringt `analysis/hypotheses.py` |
| 6 | 22 Bedarf | ändert `crosswalk.py` und `prep/context.py`, Netzschritt, Paket; nutzt `hypotheses.py` aus 17 |
| 7 | 16 Ortsbezug | braucht 11, `point_shares` aus 22 und den Einhängepunkt; ändert `weights.py` und den Kartenumschalter |

Jeder Merge: Rebase, `def`-Zahlen je Datei vergleichen, Review am Diff, `nox`, `--no-ff`, Version,
Push, CI über die Actions-REST-API, Pages-Lauf grün. Stufe 3 folgt derselben Reihenfolge. 11 und 12
zeigen in Stufe 3 nur eine Downloadzeile und dürfen eine Version teilen. Jeder neue Settings-Schlüssel
ändert den globalen Fingerprint; nach jedem Merge rechnen die Offline-Schritte einmal neu (bekannt und
hingenommen, Meta-Plan § 7).

## 4. Änderungen an den Bauplänen (Vorschlag)

Kurzfassung; ausführlich in § 10 des jeweiligen Messdokuments, wenn der Supervisor zustimmt.

- **11 Struktur.** Spannen als Int64 in der Folge von F3. `struktur-1` ist `struktur-entwurf-1`
  unverändert; eine Schärfung nur als `struktur-2` mit frischer Stichprobe (Konflikt 8). Eine
  Abschnittsart `rumpf` (Text nach dem Kopf ohne Überschrift: 55 % der BV-Informationsvorlagen, die
  Einleitung einer Anfrage), damit 16 die Lücke nicht selbst schließt ([16-ortsbezug.md](16-ortsbezug.md),
  § 3.0); sie berührt keine validierte Frage. `section_of`, `read_span` (mit `page_noise`, Frage 9.6)
  nach `georep.spans`, `split_lines` nach `prep/raw_texts.py`. Gremien über `prep/bodies`. Eine Zeile
  je Korpus-ID, auch bei geteilter Datei. Nebenarbeit 9.1 ist erledigt (der Kommentar zu „A+F
  Beschluss" in `duesseldorf.toml` ist berichtigt); 9.2 ist Frage 15 an Konrad. Beitrag
  `11-struktur`, Schritt `sections` am Einhängepunkt vor `weights`.
- **12 Kennungen.** Jede Korpus-ID der Datei; `section` aus 11 (Merge nach 11), der Ersatz entfällt;
  `attr` nach der F3-Entscheidung. Reine Funktionen nach `prep/identifiers.py` wie 11 und 14, der
  Beitrag dünn in `enrich/`. Kein Paket. Kein Dezernat aus einer Profiltabelle (sammelt 24); `dezernat`
  nur aus dem Text. Federführendes Amt und Beratungstermine liest jeder Nutzer aus 11 (Konflikt 5).
  Stufe 3 erst mit `12-kennungen-2-f4`.
- **13 Dubletten.** Bleibt es bei „verwerfen": keine Stufe 2, eine Zeile in `decisions.md` mit den
  Zahlen (0,5 % der Dokumente bei τ = 0,9, höchstens 1,4 % Verlust je Wahlbezirk), der Prototyp geht
  an 23, Fortschreibungen deckt 14 über `nachtrag` ab, Verteilervorlagen bleiben zurückgestellt (14,
  Frage 9.13). Wird es eine Variante: Pfade im Modul statt in `layout.py`, Einhängepunkt vor `weights`,
  Name `familie` nach den Varianten von 16 in `FIXED_VARIANTS`.
- **14 Vorgänge.** Spannen nur für Textstellen (Konflikt 1). Anlagen nur als Paket
  `snapshots/duesseldorf-anlagen/` und `snapshots/moenchengladbach-anlagen/`; die Erweiterung von
  `PaperRecord` nicht in Stufe 2 („mit F6 abzustimmen" entfällt: F6 hat sie 14 überlassen). Die
  Prüfstichprobe aus Frage 9.18 läuft parallel. Stufe 3: Fraktion aus 15, beobachtet/erwartet über
  die Funktion aus 15, Dialog über den eigenen Haken. Dateiname `dokumente_vorgang.parquet`.
- **15 Funktion.** Mehrheiten in den stadtweiten Block (§ 1), Quelle die Vereinbarungen aus 25
  (Frage 9.2 damit beantwortet); die Fraktionstabelle bleibt bis zu Konrads Netzlauf. Die Funktion
  beobachtet/erwartet als eigenes Modul in `analysis/`. `akteure.html` nennt den Unterschied zu
  „Dokumente je Partei" (Konflikt 10). Dateiname `dokumente_antragsteller.parquet` für `mitantraege`.
- **16 Ortsbezug.** Spannen als Int64 und in der Folge von F3. `store_view` entfällt zugunsten von
  `flatten_with_offsets` (F1), der Rumpf kommt aus 11, die Adresse → Wahlbezirk über `point_shares`
  (Band 0). Das Adresspaket trägt zusätzlich den Stimmbezirk (wenige KB), dann braucht ein späterer
  Lärmauszug von 22 die 90 MB der Gebäudereferenzen nicht (Vorschlag, nicht gemessen). Variante
  `ortsbezug` nur, wenn Nebenregel C die Bestätigungsrunde besteht (100 frische Paare, Codebuch
  Fassung 2), sonst greift die dort vorab festgelegte Rückfallregel; `stelle` heißt
  „explorativ". Pfade im Modul.
- **17 Zeit.** Spannen des Lexikons auf dem Rohtext über die Brücke, sonst auf dem Store mit leerem
  `section`. **Ein** Beitrag `17-zeit` mit vier Schritten. `analysis/hypotheses.py` mit `holm` und dem
  gemeinsamen Spaltenkern (§ 1). `cycle_tests` nach der Lösung zu `pages.yml` (Konflikt 13). Datei
  `dokumente_bundesvokabular.parquet`. Stufe 3 liest `17-zeit-f4/guete.json` und die Labels dort für
  „richtig: k von 10" je Kategorie.
- **22 Bedarf.** Paket `snapshots/duesseldorf-bedarf/` über `pack --need`, nicht `context/bedarf/`
  (Konflikt 11); Netzschritt mit `http`. Pfade im Modul statt in `layout.py`. Hypothesentabelle mit
  dem Kern aus 17 (`urteil` heißt `ergebnis`). H1′ und H3′ (Frage 22.10) vorab festlegen, solange die
  Daten der laufenden Periode fehlen. Die Klassen `OVA`, `JHA`, `SCHUA` kommen später aus 19, wenn 19
  gebaut wird.

Für Vorhaben, die noch messen oder warten (Hinweise an ihre Stufe 1):

- **21 Geld**: Beträge ohne Rolle; der Abschnitt Finanzen fehlt in Düsseldorf fast immer (11, § 3.1),
  Beträge kommen aus Beschlussvorschlag und Sachdarstellung; ein Merker „aus bezirklichen Mitteln"
  braucht eigene Labels (12, Frage 11); ein Vorgang ist meist ein Paar (14, § 5.1).
- **23 Textübernahme**: MinHash-Parameter aus 13, § 3.3 (32 × 4 Bänder, Paare ab J = 0,6).
- **24 Kontrolle**: Anfragen tragen kein Amtsfeld (Konflikt 17); das Dezernat einer Anfrage muss über
  das Gremium oder die Antwort kommen. Die Dezernatsverteilung sammelt 24 selbst. Mehrheiten aus dem
  Block von 15; H15.1 ist als prospektive Hypothese vorgeschlagen ([15-funktion.md](15-funktion.md), § 8).
- **25 Versprechen**: liefert die Quelle der Mehrheiten für 15 und die Sitze für 28.
- **18 bis 20**: 20 liest Abschnitte mit `read_span`; das Paket der Einbettungen von 18 hängt an Frage
  18 und 26.
- **26 bis 28**: Abschnitte auf fremden Unterseiten brauchen den späteren F2-Nachzug (§ 1).

## 5. Was die Seite zeigt und was nicht

| Vorhaben | zeigt | zeigt nicht |
|---|---|---|
| 11 | Download `dokumente_kopf` (Parquet), Anteil richtiger Beschlussvorschläge (188 / 200) und Präzision je Kopffeld mit Intervall | Abschnittstexte; Namen (Dezernat nur als Amtsbezeichnung); den Unterzeichner als Aussage (4,9 % gefüllt) |
| 12 | Download `kennungen.parquet` mit `bplan`, `fnp`, `betrag`, `termin`, `amt`, `dezernat`; CSV nur Bauleitplanung und Beträge; Güte je Art | Rolle eines Betrags, Fristen, Haushalt, Rechtsgrundlagen (gemessen und verworfen); Personennamen |
| 13 | bei „verwerfen" höchstens einen Satz im Methodenteil | keine Gewichtszeile, keine Familie im Dialog |
| 14 | `vorgaenge.html`: Antworten je Gremium mit Praxis, Antwortzeiten nur gültig datiert (ab 2019-07-04), Vorgänge nach der Rückfallregel (rund 2 200, fast alle Paare), starke Nachbarn im Dialog, 104 / 106 mit Intervall | „unbeantwortete Anfragen"; rohe Antwortquoten je Fraktion (Frage 14); Textverweise, auch nicht als „ungeprüft"; Kandidatenlisten für Gremien mit Praxis unter 0,7 |
| 15 | `akteure.html`: Funktionen, Instrumente je Fraktion beobachtet/erwartet („explorativ"), Matrix wer mit wem, K3 nur in Rat und Ausschüssen mit Quelle der Mehrheit, Liste der Resolutionen, „Funktion nicht erkannt" | Rangfolge der Symbolpolitik je Fraktion; K3 für Bezirksvertretungen; H15.1 und H15.2 als Test (nur prospektiv) |
| 16 | `stelle` als Gewichtszeile („explorativ"); Variante „nur handelt von" im Kartenumschalter nur nach bestandener Regel; Verortbarkeit der Hausnummern mit Quelle | Adressen, Textstellen, die Tabelle „Dokument × Adresse" (Privatpersonen); Stadtteile als Begriffe (Frage 23) |
| 17 | `zeit.html`: Rhythmus, drei Hypothesen mit Commit und Zeitpunkt der Festlegung, „nicht bestätigt" so groß wie „bestätigt"; Vokabular je Kategorie mit Präzision und Ebene; Ereignisspuren „explorativ"; Feeds der laufenden Periode | Hochwasser (nicht geprüft); im Feed Inhalt, Zusammenfassung, Kategorien, Personen (Frage 27) |
| 22 | `bedarf.html`: Quellen mit Namensnennung, Bedarf je Wahlbezirk, drei Tests mit Moran's I und der Rechnung innerhalb der Stadtbezirke, „Was das nicht sagt" | Rangliste „vernachlässigter" Bezirke; Aussagen über Personen; Zeitreihe; etwas je Partei |

Für alle gilt:

- **Nur Validiertes** (Meta-Plan, § 2.6): eine Kennzahl erscheint nur mit `alpha_genuegt = true` in
  `guete.json` und mit dem Satz aus derselben Datei, „geprüft von zwei KI-Kodierern desselben Modells
  an *n* …, nicht von Menschen", bis Frage 19 anders entschieden ist. Wo kein Kodierer prüft (22),
  stehen die deterministischen Gegenproben mit Zahl. Eine nach den Labels gewählte Variante (15 B)
  nennt die nicht gewählte als Untergrenze.
- **Explorativ** heißt alles, was nicht vorab festgelegt war, in derselben Schriftgröße wie der Rest.
- **Grenzen aus den Messungen** stehen neben der Zahl, nicht in einer Fußnote: Antwort im
  Ratsinformationssystem ist nicht Antwort (14), die Wörterbuchgröße treibt die Treffer weiter
  (r 0,765 → 0,770, 16), der Zusammenhang von H1 liegt zwischen den Stadtbezirken (22), die Hälfte des
  Bundesvokabulars ist örtliche Umsetzung (17), Rohtext auf Pages nur für die Hauptperiode (Konflikt 14).
- **Kurzfassungen (20) werden nie veröffentlicht** (Konrad, 2026-11-23, Meta-Plan § 10, Frage 6); sie
  bleiben im Modellcache.
- **Wahlprogramme und Vereinbarungen (25) bleiben lokal** unter `fremddaten/programme/`; ins Repo
  kommen nur Quellenangaben und abgeleitete Tabellen.
- **Kodieraufträge und Ausschnitte bleiben lokal** unter `validation.coding_root`; ins Repo nur
  Codebuch, Stichprobe, Labels, `guete.json`.
- `index.html` bekommt nur den Linkblock „Weitere Auswertungen", die Downloadzeilen aus dem Register
  und die Variante von 16. Wie viel die 14 neuen Downloadzeilen kosten, ist nicht gemessen; der
  slow-Test hält das Budget, und Stufe 3 misst nach jedem Merge.

## 6. Fragen an Konrad für Haltepunkt A

Offen aus [fragen-2026-11.md](fragen-2026-11.md) und neu aus § 9 der Messdokumente. **Neu** heißt:
aus § 9 der Messdokumente am 2026-11-23 in `fragen-2026-11.md` übernommen (Nummern 23 bis 31).

| Nr. | Vorhaben | Frage | Annahme ohne Antwort | Status |
|---|---|---|---|---|
| 18 | F1 | Grenze `TOTAL_LIMIT` (180 MiB) heben, Pakete auslagern oder nur die Hauptperiode packen? | nur die Hauptperiode | offen |
| 26 | 14, 16, 22, 18 | Die drei kleinen Pakete der Stufe 2 freigeben (Anlagen 0,5 MB, Adressen 0,09 MB, Bedarf rund 1 MB), und wohin mit den Einbettungen von 18 (rund 30 MB), die unter 180 MiB nicht passen? | die drei kleinen ja; Einbettungen nicht ins Repo, bis Frage 18 entschieden ist | **neu**, mit 18 zu entscheiden |
| 19 | F4, alle | Soll Kodierer B ein anderes Modell sein? | Opus für beide; die Seite sagt „desselben Modells" | offen |
| 14 | 14 | Soll die Seite überhaupt etwas je Fraktion zeigen? | nur standardisiert und „explorativ" | offen |
| 25 | 15, Option 04 | `parteien` übersieht bei 281 Dokumenten Mitantragsteller; soll Option 04 nachziehen, auch wenn sich „Dokumente je Partei" auf `index.html` ändert? | nein; `akteure.html` zählt eigene Antragsteller und nennt den Unterschied, Rückstand in `docs/todo.md`, Punkt 9 | **neu** ([15-funktion.md](15-funktion.md), Fragen 9.5 und 9.15) |
| 24 | 16 | Soll „Hausnummer vor Straßenname" (−1 790 Paare, Tabelle 5 ohne 1 und 10: p 0,036 → 0,025) Standard werden? | nein, Variante | **neu** ([16-ortsbezug.md](16-ortsbezug.md), Frage 9.8) |
| 23 | 16 | Sollen die 46 Stadtteilnamen als Begriffe zählen (+6 827 Paare, +23 %, aus Orten werden Gebiete)? | nein, der Schalter bleibt aus | **neu** (16, Frage 9.4) |
| 13 | 20 | Kurzfassungen: kleineres Modell oder nur eine Auswahl der Dokumente? | Stufe 1 misst beide Modelle | offen |
| 15 | 11 | Die Namen der sechs Ausschüsse (JHA, KUA, SCHUA, AGS, HFA, AWM) ins Profil übernehmen? | ja, eigener Commit nach Haltepunkt A | offen |
| 21 | 25 | Die ZIP-Archive des Local Manifesto Project laden? | nein | offen |
| 22 | 25 | Fehlende Programme bei den Parteien anfragen, Bezirksprogramme der GRÜNEN dazu? | 25 rechnet mit dem Bestand | offen |
| 27 | 17 | Dürfen die getroffenen Straßennamen als `category` in die Feed-Einträge? | nein | **neu** ([17-zeit.md](17-zeit.md), Frage 9.6) |
| 28 | 17 | Welche Adresse ist die kanonische der Seite (Pages oder VPS), damit die Feeds `rel="self"` tragen? | kein `self` | **neu** (17, Frage 9.4) |
| 29 | 22 | Ein räumliches Modell für H1 und H3, oder genügen Moran's I und die Rechnung innerhalb der Stadtbezirke neben dem Test? | genügen | **neu** ([22-bedarf.md](22-bedarf.md), Frage 22.8) |
| 30 | 16 | Die Stadt veröffentlicht keine Geltungsbereiche der Bebauungspläne (Landesdatensatz: 19,7 % der genannten Nummern); bei der Stadt anfragen? | nein | **neu** (16, Frage 9.5) |
| 31 | 11, 16, 20 | 104 Dokumente der Hauptperiode haben nach dem Kopf keinen Text in der Textebene (gehäuft BV 8); OCR? | nein; `rumpf_leer` macht sie sichtbar | **neu** ([11-struktur.md](11-struktur.md), Frage 9.7) |

Zur Kenntnis, vom Supervisor entschieden und umstoßbar: Frage 16 (Kriterium der Fristfunktion ≥ 0,8),
17 (Restklasse nicht im κ von 15), 20 (gemeint ist die Klasse `frist`; die Fristfunktion fällt).

Handlungen, keine Fragen: der Netzlauf aus F6 nach dem Runbook; das Signal, die angehaltenen
Modelläufe (ollama) wieder zuzulassen.

## 7. Umfang

Schätzungen aus den Messdokumenten, Stand 2026-11-23; was nicht gemessen ist, steht so da.

- **Agentenläufe** für Stufe 2 und 3 der sieben Vorhaben: je ein Bau-Agent (Stufe 3 per SendMessage),
  zwei Reviews, rund eine Nacharbeit: 28 bis 35. Dazu Kodierung: Prüfstichprobe 14 (drei Läufe),
  optional `OVA` für 22 (drei), ein Review des Fundament-Nachzugs. Zusammen **rund 32 bis 42 Läufe**,
  im Rahmen der Schätzung des Meta-Plans (§ 13: 70 bis 90 für vierzehn gebaute Vorhaben).
- **Commits**: rund 80 bis 120 (Schätzung nach dem Ausbau 2026-10: 100 bis 120 für acht Optionen),
  dazu je Merge die Versionscommits.
- **Versionen**: F5, F1, Fundament-Nachzug, sieben Stufe-2-Merges, fünf bis sieben Stufe-3-Merges:
  **rund 15 bis 17**, von `v0.21.0` (F5) bis etwa `v0.37.0`.
- **Neue Schritte: 13** — `sections` (11), `identifiers` (12), `references`, `procedures` (14),
  `functions`, `cosponsors` (15), `places` (16), `cycles`, `vocabulary`, `cycle_tests`, `feeds` (17),
  `need_data`, `need` (22); dazu vier bis fünf Seitenschritte `page_<name>`.
- **Neue Dateien unter `processed/`: 19** — 11: 2, 12: 1, 14: 4, 15: 2, 16: 3, 17: 5, 22: 2.
- **Veröffentlichte Tabellen: 14** — 11: 1, 12: 1, 14: 3, 15: 2, 16: 1, 17: 4, 22: 2.
- **Unterseiten: 4** (`vorgaenge` unter 50 KB, `akteure` 40 bis 70 KB, `zeit` 40 bis 80 KB, `bedarf`
  150 bis 250 KB), `orte` nur bei Bedarf; **41 Feeds** in der laufenden Periode (981,8 KB zusammen).
- **Neue Pakete: 3** (Anlagen, Adressen, Bedarf; rund 1,7 MB) neben dem Rohtext von F1 (16,3 MiB).
- **Laufzeit** der neuen Schritte je vollem Lauf der Hauptperiode, aus den Messungen addiert: 11 rund
  20 s, 12 rund 41 s, 14 unter 20 s (Ziel, nicht gemessen), 15 rund 2 s, 16 rund 40 s, 17 rund 20 s
  für drei Perioden, 22 nicht als Schritt gemessen: **zusammen rund zweieinhalb Minuten**, auf Pages
  dazu der Neulauf nach jedem Fingerprintwechsel.
- **GPU**: keine. **Netz**: nur `need_data` (22), ein kleiner Abruf von Archiven der Quellen.
