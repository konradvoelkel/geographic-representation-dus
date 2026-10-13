# Fragen an Konrad, gesammelt vom Supervisor

Protokoll: § 6 des Meta-Plans. Je Frage: Nummer, Option, Datum, Frage, warum sie zählt, Annahme ohne
Antwort, Status. Die sieben Fragen aus § 9 des Meta-Plans stehen zuerst (beantwortet); danach die Fragen der
acht Pläne aus der Synergiephase (2026-10-12). Wo der Supervisor entscheiden konnte, steht die Entscheidung im
Status („Supervisor: …"); diese Fragen brauchen keine Antwort mehr, Konrad darf sie aber umstoßen. **Keine
Frage blockiert die Implementierung**; alle Unteragenten arbeiten unter den Annahmen weiter.

Stand nach dem Merge aller acht Optionen (2026-10-12): keine Frage wurde in Phase 3 bis 5 beantwortet, alle
Annahmen gelten unverändert. Getroffen ist damit: Mönchengladbach statt Neuss (3), Düsseldorf bleibt flach (4),
Quartiersatlas im Repo unter `context/` (2, Teil), Hauptmodell ohne Parteianteile (8), Lizenzfeld „nicht
angegeben" (7). Offen und nur von Konrad zu erledigen: die vier Netzläufe (1), die Pakete Mönchengladbach und
2014 bis 2020 im Repo oder im R2-Bucket (2), VPS und Domain (5), R2-Bucket und Token (6).

Konrads Antworten vom 2026-10-13 auf die acht wichtigsten Fragen: (1) alle vier Netzläufe freigegeben, der
Supervisor startet sie auf kookaburra (Reihenfolge: laufende Periode 2025, Mönchengladbach, Periode 2014 bis
2020, Vollabruf der Metadaten der Hauptperiode in eine eigene Datenwurzel); (2) die Datenpakete kommen ins
Repo, sie sind klein; (3) Mönchengladbach; (4) der Umzug Düsseldorfs nach `data/duesseldorf/` ist gewünscht;
(5) VPS später, jetzt nicht; (6) kein R2-Bucket, kaum Traffic und kleine Dateien; (7) Rückfrage, woher die
votemanager-CSV stammt (Antwort: `wep.itk-rheinland.de/vm/prod/kw_2025/05116000/daten/opendata/`, die
Open-Data-Seite der Wahlpräsentation der ITK Rheinland, siehe Profil Mönchengladbach); (8) die Frage 3.1 war
unklar formuliert, die Annahme bleibt (Hauptmodell mit Sozialdaten, Parteianteile nur im Parteimodell). Kein
Kontakt mit Lukas Bartzsch zu diesem Zeitpunkt; die nachzutragenden Angaben der Literatur bleiben offen.

## Beantwortet (Meta-Plan § 9, 2026-10-11)

| Nr. | Option | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|---|
| 1 | 1, 2, 4, 7 | 2026-10-11 | Netzabrufe: Dauer und Freigabe | Netz-Optionen brauchen Daten vom OParl-Server und den Portalen | nur vorbereiten | beantwortet 2026-10-11: nur stichprobenartig, mit Rate-Limiting rund 5 Minuten am Stück; alles wesentlich Längere braucht Konrads Freigabe und sollte nicht nötig sein |
| 2 | alle | 2026-10-11 | Merge-Modus | wer merged, in welcher Reihenfolge | Supervisor merged | beantwortet 2026-10-11: der Supervisor merged nach Inspektion in angemessener Reihenfolge; er darf Unteragenten um Rebase bitten und iterativ vorgehen |
| 3 | 6 | 2026-10-11 | scikit-learn trotz nox-Verbot | Themenmodell für die Gewichtung | numpy | beantwortet 2026-10-11: scikit-learn ist voll in Ordnung; TF-IDF von Hand und gensim sind nicht nötig. Branch 06 nimmt es aus FORBIDDEN in noxfile.py und begründet das in decisions.md |
| 4 | 7 | 2026-10-11 | Ort und Speicher des wiederkehrenden Abrufs | Actions hat keinen dauerhaften Speicher | Timer auf Konrads Rechner | beantwortet 2026-10-11: zuerst auf kookaburra (Heimrechner) simulieren und prüfen, aber direkt für den VPS vorbereiten; größere aktualisierte Daten wie bei bubatzblick in ein Cloudflare-R2-Bucket (wenn ein zweites nichts kostet); fertige Datensätze bis 10 GB zum Download auf dem VPS; später eine Datenplattform, Vorschläge erwünscht; Kleines direkt auf kookaburra |
| 5 | 3 | 2026-10-11 | Fremddaten aus PDFs der Stadt | Quartiersatlas liegt vermutlich als PDF vor | ja, mit Lizenz | beantwortet 2026-10-11: Quartiersatlas ausdrücklich erlaubt; andere Daten dürfen mit Lizenz verarbeitet werden, dann muss auf der Seite stehen, was alles daraus abgeleitet wurde |
| 6 | alle | 2026-10-11 | Versionierung | Tag je Option oder gesammelt | je Option | beantwortet 2026-10-11: eine Sammelversion am Ende |
| 7 | alle | 2026-10-11 | Rechnerlast | acht Agenten parallel | Wellen zu vier | beantwortet 2026-10-11: 13 Kerne insgesamt und so viel RAM wie nötig; acht Agenten dürfen gleichzeitig nox laufen lassen |

## Die wichtigsten offenen Fragen (brauchen Konrads Entscheidung oder Handgriff)

Diese acht entscheiden über Umfang, Daten im Repo oder einen Lauf, den nur Konrad starten kann. Die
Nummern verweisen auf die Tabellen unten.

1. **Netzläufe, gebündelt** (1.9, 2.5, 4.4, 7.6): vier Läufe auf kookaburra nach dem jeweiligen Merge, je
   mit Runbook im Branch: Mönchengladbach (3 bis 5 h), Periode 2014 bis 2020 (3 h Metadaten plus 8 bis 11 h
   PDFs, 3,7 bis 4,4 GB), Erstabruf der laufenden Periode (16 bis 30 min plus 2,3 h PDFs), optional der
   Vollabruf der Hauptperiode (2 bis 3 h; bringt keine Urheber, aber `modified` und `consultation`). Annahme:
   die Agenten rufen nichts ab; die Seite zeigt die neuen Teile erst nach Konrads Lauf.
2. **Datenpakete im Repo** (1.2, 2.1, 3.3): Mönchengladbach-Paket (10 bis 20 MB), Schnappschuss
   2014 bis 2020 (35 bis 40 MB), Quartiersatlas (2,3 MB). Annahme: alle drei ins Repo, wie die Referenz der
   Arbeit (82 MB); Alternative wäre das R2-Bucket aus Option 7 mit einem Download-Schritt in Actions.
3. **Mönchengladbach statt Neuss** (1.1): nur Mönchengladbach hat Stimmbezirksflächen als Open Data. Annahme:
   Mönchengladbach; Neuss später über Flächen aus dem Straßenverzeichnis (§ 9 des Plans 01).
4. **Düsseldorf unter `data/duesseldorf/`** (1.7): Umzug der Ordner auf xtraspace und in Actions. Annahme in
   Phase 3: Düsseldorf bleibt flach (`profile = ""`); der Umzug ist nach dem Merge von 01 ein Einzeiler plus
   `mv`, wenn Konrad ihn will.
5. **VPS und Domain** (7.1, 7.2): `georep.konradvoelkel.de` mit `/2025/`, Pages bleibt Hauptseite. Annahme:
   so; bis DNS und Infra-Rolle stehen, läuft nur die Simulation auf kookaburra.
6. **R2-Bucket und Token** (7.4): Bucket `georep`, WEUR, privat, zwei Token. Annahme: Konrad legt sie an, wenn
   Option 7 so weit ist; ohne Bucket endet die Stufe mit dem Smoke-Test.
7. **Lizenz der votemanager-CSV** (1.4): nirgends angegeben. Annahme: Quelle und Herausgeber nennen,
   Lizenzfeld „nicht angegeben"; Konrad kann die ITK Rheinland fragen.
8. **Modellwahl der Kontrollvariablen** (3.1): Parteianteile als Kontrollen sind inhaltlich angreifbar.
   Annahme: Hauptmodell mit Handlungsbedarf, Anteil 65+, Fluktuation; Parteien nur im Parteimodell und einzeln.

## Option 1: Städte

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 1.1 | 2026-10-11 | Mönchengladbach als erste zweite Stadt statt Neuss? | nur Mönchengladbach hat Stimmbezirksflächen als Open Data | Mönchengladbach | offen |
| 1.2 | 2026-10-11 | Paket des vollen Laufs (10 bis 20 MB) nach `reference/moenchengladbach/` ins Repo? | CI baut nur aus dem Repo | ja | beantwortet 2026-10-13: ins Repo |
| 1.3 | 2026-10-11 | Die Stadt nach den Flächen der Kommunalwahl 2025 fragen? | 4 bzw. 5 Stimmbezirke weichen zwischen 2022 und 2025 ab | Flächen von 2022 mit gemessener Übereinstimmung | offen (Konrads Satz an `gdi@moenchengladbach.de`) |
| 1.4 | 2026-10-11 | Lizenz der votemanager-CSVs der ITK Rheinland? | die Seite nennt Lizenzen wörtlich | Quelle nennen, Lizenz „nicht angegeben" | beantwortet 2026-10-13: Quelle ist die Open-Data-Seite der votemanager-Wahlpräsentation; Lizenzfeld bleibt wie es ist, keine Anfrage jetzt |
| 1.5 | 2026-10-11 | Marker des Vorlagenkopfs in Mönchengladbach? | ohne Marker zählen Treffer im Kopf | `betrifft`, Stichprobe misst | Supervisor: Annahme gilt, der Plan misst |
| 1.6 | 2026-10-11 | Ausreißer der zweiten Regression für Mönchengladbach? | Tabelle 5 nennt 1 und 10 für Düsseldorf | leer bis zum Lauf, dann die zwei höchsten | Supervisor: Annahme gilt (`analysis.exclude_districts` je Profil, F3) |
| 1.7 | 2026-10-11 | Düsseldorfs `data_root` auf `data/duesseldorf/`? | sonst Ausnahme ohne Slug | Slug für alle, Umzug dokumentiert | beantwortet 2026-10-13: Umzug gewünscht |
| 1.8 | 2026-10-11 | Vergleich als `vergleich.html` an der Wurzel oder Abschnitt je Stadtseite? | Budget, Trennung der Läufe | Unterseite mit Teaser | Supervisor: Unterseite |
| 1.9 | 2026-10-11 | Dauer und Rechner des vollen Abrufs (3 bis 5 h)? | über fünf Minuten braucht Freigabe | Konrad startet nach dem Merge auf kookaburra | freigegeben 2026-10-13, Supervisor startet den Lauf |
## Option 2: Zeitreihe

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 2.1 | 2026-10-11 | Schnappschuss 2014 bis 2020 (35 bis 40 MB) ins Repo oder nach R2? | Pages baut rein aus dem Repo | ins Repo unter `snapshots/2014-2020/` | offen (gebündelt, oben 2) |
| 2.2 | 2026-10-11 | Dasselbe Wörterbuch (Stand November 2025) für beide Perioden? | Alternative macht Trefferquoten nicht additiv | ja | Supervisor: ja, wie der Meta-Plan vorschlägt |
| 2.3 | 2026-10-11 | Zeitgrenzen 2014-05-25 bis 2020-09-12, Wahltag 13.09.2020? | wenige Dokumente am Rand | ja | Supervisor: ja |
| 2.4 | 2026-10-11 | Briefwahl proportional zu A2 (Sperrvermerk W) verteilen? | bis 5,1 Prozentpunkte je Bezirk | A2, Alternative als Satz und Settings-Zeile | Supervisor: Annahme gilt |
| 2.5 | 2026-10-11 | Freigabe des Abrufs (3 h Metadaten, 8 bis 11 h PDFs, 3,7 bis 4,4 GB)? | ohne ihn kein echter Vergleich | Konrad startet nach Stufe G | freigegeben 2026-10-13, Supervisor startet den Lauf |
| 2.6 | 2026-10-11 | Pages baut beide Perioden (plus rund eine Minute)? | sonst Unterseite nur lokal | ja | Supervisor: ja, sobald der Schnappschuss da ist |
| 2.7 | 2026-10-11 | Weitere Parteispalten 2020 (`D7` bis `D16`) in die Wählertabelle? | Schemaunterschied zwischen Perioden | nein | Supervisor: nein |
| 2.8 | 2026-10-11 | Vergleich als Abschnitt der Hauptseite oder eigene Unterseite? | 45 KB Zuwachs | Abschnitt | Supervisor: Abschnitt `36-perioden`, Budget hält |

## Option 3: Kontrollvariablen

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 3.1 | 2026-10-11 | Variablen des Hauptmodells; Parteianteile als Kontrollen? | bestimmt Tabelle 6 und die Plots; Endogenität | Handlungsbedarf-Score, Anteil 65+, Fluktuation; Parteien nur im Parteimodell und einzeln | Annahme bestätigt 2026-10-13 (Frage war unklar formuliert) |
| 3.2 | 2026-10-11 | Ordinalskala gering = 1 bis hoch = 5 für `Sozialer_HB`? | ordinal als metrisch ist eine Annahme | ja, `Mindestsicherungsquote` als Gegenprobe | Supervisor: Annahme gilt |
| 3.3 | 2026-10-11 | 2,3 MB Fremddaten unter `context/` ins Repo? | Reproduzierbarkeit ohne Netz | ja, mit README und SHA-256 | offen (gebündelt, oben 2) |
| 3.4 | 2026-10-11 | Datenstand 31.12.2021 für eine Wahl 2025 akzeptabel? | Deutung der Koeffizienten | ja, mit Hinweis | Supervisor: ja, mit Hinweis auf der Seite |
| 3.5 | 2026-10-11 | Tabelle 6 auch ohne die Wahlbezirke 1 und 10? | Seitenlänge gegen Konsistenz | beide in Parquet, Seite nur „alle" plus ein Satz | Supervisor: Annahme gilt |
| 3.6 | 2026-10-11 | Einheiten: Prozent für Anteile, Trefferquote unskaliert, standardisierte Koeffizienten dazu? | Lesbarkeit | ja | Supervisor: Annahme gilt |
| 3.7 | 2026-10-11 | Stimmbezirk 3301: GeoJSON (Hafen) oder CSV (Unterbilk)? | 297 Wahlberechtigte | GeoJSON | Supervisor: GeoJSON, Test hält die Abweichung fest |

## Option 4: Parteien

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 4.1 | 2026-10-11 | Nur die sechs Parteien aus `columns.results.parties` mit Hochburg-Kennzahl? | Zahl der Karten, Settings | die sechs; Gruppen als Zeile ohne r und p | Supervisor: Annahme gilt |
| 4.2 | 2026-10-11 | Kooperationspapiere (CDU+GRÜNE 825) für jede Partei voll zählen? | verändert Karten und Korrelationen | voll, `treffer_allein` daneben | Supervisor: Annahme gilt |
| 4.3 | 2026-10-11 | Personen (746 Dokumente) über `memberships`/`persons` den Fraktionen zuordnen? | Hunderte Anfragen | Klasse „Person" ohne Partei | Supervisor: nein in Phase 3 |
| 4.4 | 2026-10-11 | Vollabruf der Metadaten (2 bis 3 h) starten, obwohl er keine Urheber bringt? | `modified` für 7, `consultation` für 5 | nur vorbereitet | freigegeben 2026-10-13, Supervisor startet den Lauf |
| 4.5 | 2026-10-11 | Netzschritt `organizations` bei jedem `georep fetch` mitlaufen lassen? | eine Seite, 0,5 s | ja | Supervisor: ja |
| 4.6 | 2026-10-11 | Sechs kleine Karten plus Tabelle oder Matrix-Heatmap? | Budget rund 75 KB | Karten plus Tabelle | Supervisor: Karten plus Tabelle, Budget hält |
| 4.7 | 2026-10-11 | `dokumente.json` mit Urheber je Dokument (+130 KB)? | Größe beim ersten Klick | ja | Supervisor: ja |
| 4.8 | 2026-10-11 | Nur r und p je Partei, Modell bei Option 3? | Abgrenzung | ja | Supervisor: ja |
| 4.9 | 2026-10-11 | `dokumente_urheber.csv` (1,7 MB) anbieten? | Seitengröße | ja | Supervisor: ja, wie `wahlbezirke_auswertung.csv` |
| 4.10 | 2026-10-11 | Eingaben nach § 24 GO als eigene Klasse? | fünf statt vier Klassen | ja | Supervisor: ja |

## Option 5: Gremien

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 5.1 | 2026-10-11 | Wahlbezirk 40: BV9 und BV10 beide „eigene" oder nur BV9? | Kennzahl 0,77 gegen 0,26 | beide, Fußnote | Supervisor: beide, Gewichte veröffentlicht |
| 5.2 | 2026-10-11 | Gremiennamen aus Settings oder einmaliger `organizations`-Abruf? | Lesbarkeit, Option 4 | Settings; Abruf kommt mit 04 | Supervisor: Settings jetzt, nach dem Merge von 04 aus `organizations.json` |
| 5.3 | 2026-10-11 | Kartenkennzahl Anteil eigene BV oder Quote je Wahlberechtigtem? | Lesart der dritten Karte | Anteil | Supervisor: Anteil |
| 5.4 | 2026-10-11 | Beiräte als eigene Klasse? | Tabelle und Settings-Form | ja, nicht auf der Karte | Supervisor: ja |
| 5.5 | 2026-10-11 | Spalte `herkunft` hier oder in Option 4/6? | Grenze zu 04 | hier | **Supervisor: nein, 04 besitzt den Urheber; `herkunft` entfällt in 05** |
| 5.6 | 2026-10-11 | Zuordnung je Dokument (`papers_gremien`) veröffentlichen? | CSV 2,3 MB | nein | Supervisor: nein |
| 5.7 | 2026-10-11 | Regressionssatz zur Quote der eigenen BV? | Kennzahlvarianten gehören 03 und 06 | ein Satz | Supervisor: ein Satz über `regression_pair(x=…)` |

## Option 6: Gewichtung

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 6.1 | 2026-10-11 | Sechs feste Varianten plus 20 Themen? | Länge der Tabelle | genau diese, Themen weich | Supervisor: Annahme gilt |
| 6.2 | 2026-10-11 | Antrag, Anfrage, Haushaltsantrag, Eingabe als Klassengrenze der Dokumentart? | zwei Regelsätze | ja, Muster in Settings | Supervisor: ja |
| 6.3 | 2026-10-11 | K = 20, nur das dominante Thema veröffentlichen? | Lesbarkeit, Download-Größe | ja | Supervisor: ja |
| 6.4 | 2026-10-11 | Spalte „ohne Ausreißer" für alle Varianten mit 1 und 10? | Vergleichbarkeit | ja, fest | Supervisor: ja (`analysis.exclude_districts`) |
| 6.5 | 2026-10-11 | Gewichtete Quoten auch auf Karte und Bezirkstabelle? | Konflikt mit 05, Budget | nein | Supervisor: nein |
| 6.6 | 2026-10-11 | `kombiniert` = IDF × Anträge halb? | eine Zeile | ja | Supervisor: ja |
| 6.7 | 2026-10-11 | `OUTLIERS` in die Settings? | Düsseldorf-Wert im Code | ja | **Supervisor: erledigt im Fundament F3** |

## Option 7: Monitoring

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 7.1 | 2026-10-11 | Hostname und Pfad auf dem VPS? | DNS vor Caddy; relative Links | `georep.konradvoelkel.de`, Profil unter `/2025/` | beantwortet 2026-10-13: VPS später, jetzt nicht |
| 7.2 | 2026-10-11 | Bleibt Pages die Hauptseite? | `monitoring_url` absolut oder relativ | Pages bleibt, VPS spiegelt | offen (oben 5) |
| 7.3 | 2026-10-11 | PDFs und Texte der laufenden Periode veröffentlichen? | urheberrechtlich nicht geklärt | nein, privates Bucket | Supervisor: nein, wie die Berichtsseite entschieden hat |
| 7.4 | 2026-10-11 | R2-Bucket, Region, Token? | Konrads Konto | `georep`, WEUR, privat, zwei Token | beantwortet 2026-10-13: kein Bucket, nicht nötig |
| 7.5 | 2026-10-11 | Takt täglich 04:17 Uhr plus bis 30 min? | Last und Aktualität | täglich | Supervisor: täglich |
| 7.6 | 2026-10-11 | Freigabe des Erstabrufs und der 50-PDF-Stichprobe? | ohne ihn keine echte Profilseite | Konrad startet die Einheit | freigegeben 2026-10-13, Supervisor startet den Lauf |
| 7.7 | 2026-10-11 | Datenplattform: Zenodo plus Hugging Face vorbereiten, GovData nicht? | Datensatzkarte, Lizenz, `CITATION.cff` | beides vorbereiten, nichts hochladen | Supervisor: vorbereiten, nichts hochladen |
| 7.8 | 2026-10-11 | Wörterbuch für die laufende Periode eingefroren? | Vergleichbarkeit | ja | Supervisor: ja (wie 2.2) |
| 7.9 | 2026-10-11 | Monatsreihe 2020 bis 2025 auch auf der Hauptseite (rund 20 KB)? | Budget | ja | Supervisor: ja, Abschnitt `55-monate` |
| 7.10 | 2026-10-11 | Monatlicher Volllauf ohne `modified_since`? | Lücken durch Server-Uhrzeitfehler | als Befehl dokumentiert, nicht im Timer | Supervisor: Annahme gilt |

## Option 8: Suche

| Nr. | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|
| 8.1 | 2026-10-11 | Originalschreibweise der Straßen und Orte in der Suche? | +90 KB, zwei Schreibweisen | kleingeschrieben | Supervisor: kleingeschrieben |
| 8.2 | 2026-10-11 | Ein Vorschlag je Straße mit vereinigten Dokumenten? | Zahlen weichen von den Schaltflächen ab | zusammengezogen | Supervisor: ja, mit Hinweis |
| 8.3 | 2026-10-11 | Platz der Suche: vor der Karte oder im Kopf? | erstes Bedienelement | eigener Abschnitt | Supervisor: Abschnitt `15-suche` |
| 8.4 | 2026-10-11 | Auch die 50 Stadtteile als Einträge? | braucht den Crosswalk | zunächst nur Wahlbezirksnamen | Supervisor: nach dem Merge von 05 (`unit_weights` liegt im Fundament) als eigener Commit, wenn die Zeit reicht |
| 8.5 | 2026-10-11 | Teilbare Adresse `#suche=…`? | zehn Zeilen | ja | Supervisor: ja |
| 8.6 | 2026-10-11 | Abschnittsmechanismus als Fundament? | drei Dateien oder drei Einfügestellen | ja | **Supervisor: erledigt im Fundament F1** |
| 8.7 | 2026-10-11 | Port der Vorschau je Worktree? | acht Agenten | 8777, bei Kollision 8708 | **Supervisor: 8700 + NN je Option** |
| 8.8 | 2026-10-11 | Wer setzt das Budget 1,5 MB im Test? | geteilte Zeile | diese Option | **Supervisor: erledigt im Fundament F6** |
