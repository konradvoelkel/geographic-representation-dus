# „Politik bei uns“: was es war, warum es steht, was ein Eigenbetrieb kosten würde

Recherche vom 2026-10-12. Alle Live-Prüfungen (HTTP-Abrufe, GitHub-API, OParl-Endpunktliste) an diesem Tag.
Kein Rechtsrat; der Abschnitt § 4 nennt die Fragen, nicht die Antworten.

## 1 Was es war

Eine bundesweite Suchoberfläche über die öffentlichen Teile kommunaler Ratsinformationssysteme (RIS):
Vorlagen, Sitzungen, Tagesordnungspunkte, Beschlüsse, Anlagen — durchsuchbar nach Stichwort *und* nach Ort
auf einer Karte. Die Begründung auf `politik-bei-uns.de/info/das-projekt` ist genau unsere: „Die Menschen in
einer Stadt denken nicht so sehr in Gremien und Antragstypen, sondern in geographischen Orten und
Stichworten.“ RIS sind Arbeitswerkzeuge für Verwaltung und Rat, nicht Bürgerangebote.

Linie:

| Jahr | Schritt |
| --- | --- |
| 2012 | `offeneskoeln.de`, Marian Steinbach: erster Nachweis, dass eine andere Ansicht machbar ist |
| 2013 | Ernesto Ruge adaptiert es als `OpenRuhr:RIS` für mehrere Städte in NRW; Scraper pro Stadt |
| 2013 | Start der OParl-Entwicklung, weil Scraper pro Stadt nicht skalieren |
| 2015 | Relaunch beider Portale als „Politik bei uns“; Moers veröffentlicht als erste Stadt RIS-Daten unter freier Lizenz; „Ausgezeichneter Ort im Land der Ideen“ |
| 2016-07 | OParl 1.0 |
| 2017 | Open.NRW-Förderung; Treiber neben der OKFN das kommunale Rechenzentrum KDVZ Rhein-Erft-Rur mit über 20 Kommunen. Komplette Neuentwicklung („Politik bei uns 2“) und OParl-Schnittstellen in über 25 Kommunen bei drei RIS-Herstellern finanziert |
| 2018 | OParl 1.1 |
| 2020-03-09 | Ruge erklärt öffentlich, dass der Betrieb ehrenamtlich nicht zu halten ist |
| heute | Seite online, Daten eingefroren, kein Support |

Betreiber ist die Open Knowledge Foundation Deutschland e. V. (Singerstraße 109, Berlin), die Arbeit lag
maßgeblich bei Ernesto Ruge.

Stand des eingefrorenen Datenbestands (Statistikseite, 2026-10-12 abgerufen): **1.408.749 Objekte aus 56
Körperschaften**. Zwei Klassen: OParl-Kommunen (vollständig, aktualisierbar) und „Politik bei uns 1“-Kommunen
(aus dem Scraping, fehlerbehaftet, nicht aktualisierbar — darunter Köln, Bochum, Wuppertal, Ulm und zwölf
Berliner Bezirke; dort stehen nur Vorlagen, Dateien und Orte, keine Gremien oder Sitzungen).

Technisch (Repos unter `github.com/politik-bei-uns`): `daemon` (Python, Abruf und Veredelung),
`frontend` (Flask + gulp/webpack/React 16/mapbox-gl 1), `oparl` (gibt die veredelten Daten wieder als OParl
heraus). Veredelung = Georeferenzierung über OpenStreetMap, Textextraktion aus PDF, OCR, Thumbnails.
Stack laut `INSTALL.md`: Linux, Python 3.5, MongoDB 3, Minio, ElasticSearch 5, ghostscript, pdftotext,
abiword, jpegoptim. Letzte Pushes: `frontend` 2023-01-04 (27 offene Issues), `daemon` 2020-03-20,
`oparl` 2019-07-16. Lizenz im alten Web-Repo BSD-3-Clause, in den aktiven drei keine Lizenzdatei.

## 2 Warum es steht

Nicht Recht, nicht Technik, nicht Datenmangel. Der maßgebliche Text ist Ruges „OpenData: bisschen Prototyp,
und das war's dann?“ (binary-butterfly.de, 2020-03-09, Nachträge bis 2021-04) — darauf verlinkt der Banner
auf jeder Seite von `politik-bei-uns.de`. Seine Punkte:

1. **Professionelle Ansprüche auf ehrenamtlichen Betrieb.** Das Portal war erfolgreich, kam über Suchmaschinen
   zu vielen Nutzern — und damit zu Erwartungen an Reaktionszeiten, Fehlerbehebung, neue Städte. „Ich muss mich
   für mein ehrenamtliches Baby immer wieder beschimpfen lassen, warum ich nicht zeitnah reagiere.“
2. **Förderungen passen strukturell nicht.** Sie fördern Neues, nie den Betrieb; wer den Betrieb über neue
   Features finanziert, baut mehr Dinge, die kaputtgehen; Eigenanteil setzt ein Geschäftsmodell voraus, das ein
   gemeinwohlorientiertes Portal nicht hat; dazu Papierkrieg und rechtliches Risiko.
3. **Behörden könnten verstetigen, sammeln aber keine Prototypen ein** — und kleinen Kommunen fehlt IT-Personal,
   um überhaupt Dienstleister abzunehmen.
4. **Kein Träger für Dienste, von denen viele profitieren und keiner allein zahlen will.** Seine Folgerung: nur
   kommunalübergreifende Finanzierung oder ein kommerzielles Produkt („stabiler Betrieb gegen Geld“) — mit der
   offenen Frage, ob mehr als eine Handvoll Kommunen zahlen würde.

Es ist also nie abgeschaltet worden, sondern erfroren. Dieselbe Welle traf `kleineanfragen.de` (dicht),
`offenedaten.de` (Abwicklung), `offenerhaushalt.de` (unvollständig/veraltet), `wo-ist-markt.de` (zeitweise weg).

## 3 Ökosystem am 2026-10-12 geprüft

| Was | Befund |
| --- | --- |
| `politik-bei-uns.de` | online, HTTP 200, Suche funktioniert; Daten eingefroren, kein Support |
| `oparl.politik-bei-uns.de/system` | **lebt**, liefert OParl 1.0, `/bodies` gibt alle 56 Körperschaften in 0,2 s |
| `mirror.oparl.org` (OParl-Spiegel) | **tot**, keine Verbindung |
| `meine-stadt-transparent` (Django, MIT) | GitHub **archiviert 2023-11-25**, letzter Push 2023-07-10, 15 Forks; `meine-stadt-transparent.de` DNS tot; Stack MariaDB + ElasticSearch 7.9 + MinIO + Node 18 |
| `muenchen-transparent.de` | online |
| `oparl.org` | online, letzter Blogeintrag der Kategorie „Allgemein“ 2018-02-12 |
| `OParl/spec` auf GitHub | letzter Push 2020-09-17, 25 offene Issues, nicht archiviert. 1.1 von 2018 ist der Stand; 2.0 wird seit 2018 diskutiert |
| `dev.oparl.org/api/endpoints` | **127 bekannte Endpunkte**, davon 98 mit erreichbarem System-Objekt, 29 ohne; 77× OParl 1.1, 19× 1.0; Herstellerverteilung dominiert von Sternberg (76), dann more! software (10), vereinzelt CC e-gov, Eigenbauten. Alle Einträge zuletzt am 2026-01-17 nachgeschaut — die Liste ist neun Monate alt |

Der Standard lebt also in der Breite (die Hersteller liefern OParl aus), die Anwendungsschicht darüber ist leer.
Das interkommunale NRW-Transparenzportal (KDVZ Rhein-Erft-Rur, Frechen federführend, 24 Verwaltungen) nennt
`politik-bei-uns.de` weiterhin als seinen Ausgabekanal — der Kanal, der eingefroren ist.

Düsseldorf steht in der Endpunktliste, über denselben Endpunkt, den wir benutzen: ITK Rheinland,
`ris-oparl.itk-rheinland.de/Oparl/system`, Somacos Session, OParl-Modul 1.6.0, Schnittstellenstand 2025-04-22,
Body 0015 `oparlSince`/`licenseValidSince` 2025-04-30. **Das `license`-Feld des Systems enthält den String
`"Open"`** — kein Lizenz-URL, am Body gar kein `license`-Feld. Juristisch ist das nichts.

## 4 Was ein Eigenbetrieb erfordert

### 4.1 Daten

- 127 Endpunkte, einzeln zu überwachen: Versionen 1.0 und 1.1 gemischt, 29 davon zuletzt nicht erreichbar,
  Herstellerbugs pro Produkt verschieden. Das ist der Posten, der dauerhaft Zeit frisst, nicht der Server.
- Crawl-Kosten: unser Endpunkt brauchte am 2026-10-09 **85 s pro Metadatenseite** (`timeout_s = 180` in den
  Defaults steht deswegen so). Ein Vollabzug ist eine Sache von Stunden bis Tagen pro Körperschaft, kein
  Minutenjob — und inkrementell muss er trotzdem täglich laufen.
- Volumen, gemessen an unserem Bestand: 200 Düsseldorfer PDFs im Cache, Mittel 141 KB, Median 115 KB. Für die
  19 108 Dokumente einer Wahlperiode also **rund 2,8 GB** je Stadt und Wahlperiode, plus etwa die Hälfte für
  extrahierten Text. 56 Körperschaften über mehrere Wahlperioden: Größenordnung **150–300 GB**. Mit OCR für
  Scans deutlich mehr Rechenzeit, nicht mehr Platz.
- Die historischen Daten von „Politik bei uns“ (1,4 Mio. Objekte, darunter nicht wiederherstellbare
  Scraper-Bestände für Köln, Bochum, Wuppertal, Berlin) hängen an einem einzelnen Server eines einzelnen
  Ehrenamtlichen. Wer sie haben will, holt sie jetzt: die API läuft und ist schnell.

### 4.2 Software — drei Wege

1. **Alten Stack reanimieren.** MongoDB 3 → 7, ElasticSearch 5 → OpenSearch 2, Python 3.5 → 3.14,
   Flask-Frontend mit gulp/React 16/mapbox-gl 1 neu bauen, 27 offene Issues, keine Tests, keine Lizenzdatei
   (Lizenz vorher mit Ruge/OKFN klären). Realistisch Monate Portierungsarbeit für Code, der danach immer noch
   fünf Dienste zum Betrieb braucht. Nicht empfohlen.
2. **`meine-stadt-transparent` forken.** Moderner und aufgeräumter (Django, MIT, Docker, Poetry, Abo-Mails pro
   Suchbegriff), aber seit 2023 archiviert: Django- und ElasticSearch-7.9-Upgrade fällig. Von Haus aus eine
   Instanz pro Stadt gedacht — das passt gut auf „eine Stadt“ und schlecht auf „bundesweit“.
3. **Auf unserer Pipeline aufsetzen.** Wir haben den OParl-Abruf (`georep.oparl`, `Transport`-Protokoll,
   Stamps mit Settings-Fingerprint), PDF → Text, das Geomatching gegen OSM und Wikidata, den Golden Master und
   eine in sich geschlossene statische Berichtsseite. Was fehlt: Mehrmandantenfähigkeit, Volltextsuche
   (SQLite-FTS5 oder tantivy statt eines ElasticSearch-Clusters), Dokumentenauslieferung bzw. Deep-Links,
   inkrementelle Updates, Abos/Benachrichtigungen, Indexierbarkeit für Suchmaschinen — Letzteres war laut Ruge
   der Hauptgrund, warum solche Seiten überhaupt gefunden werden. Vorteil: eine statisch ausgelieferte Seite
   hat keinen Datenbank-, Index- und Objektspeicher-Betrieb, und genau dieser Betrieb hat das Original erledigt.

### 4.3 Recht (zu klären, nicht geklärt)

- **Urheberrecht.** § 5 Abs. 2 UrhG (amtliche Werke, mit Änderungsverbot und Quellenangabe) deckt nicht pauschal
  alles: in Anlagen stecken Gutachten, Pläne, Fotos und Karten Dritter. Dass Moers 2015 als *erste* Stadt eine
  freie Lizenz gesetzt hat, zeigt, wie der Normalfall aussieht — Düsseldorfs `license` ist der String `"Open"`.
  Die FragDenStaat-Rechtsprechung (LG und KG Berlin: dem amtlichen Dokument fehlte die Schutzhöhe) hilft im
  Einzelfall, ist aber kein Freibrief für das Spiegeln von 19 108 Dateien.
- **Datenschutz.** Wer spiegelt, wird selbst Verantwortlicher: Vorlagen und Niederschriften enthalten Namen von
  Petenten, Einwohnerfragen, mitunter Adressen. Dazu Rechtsgrundlage (Art. 6 Abs. 1 lit. e oder f),
  Verarbeitungsverzeichnis, Auskunfts- und Löschbegehren, und der Verstärkungseffekt der Suchmaschinen: viele
  Städte sperren ihr RIS per `robots.txt`, ein Aggregator hebelt das aus. Das ist der Posten, der ein solches
  Projekt kippen kann, und er fällt erst an, wenn die Seite erfolgreich ist.
- **Träger.** Haftung, Impressum, Löschprozess brauchen jemanden mit beschränkter Haftung hinter sich — bei
  „Politik bei uns“ war das die OKFN. Eine Privatperson als Betreiber einer gefundenen Plattform ist riskant.
- **Risikoarme Variante:** PDFs *nicht* spiegeln, sondern nur Metadaten und einen eigenen Volltextindex halten
  und auf das städtische RIS tief verlinken. Senkt Urheberrechts- und Datenschutzfläche erheblich, kostet
  Offline-Fähigkeit und Zitierbarkeit.

### 4.4 Geld und Zeit

- Infrastruktur ist der kleine Posten. Mongo + ElasticSearch + MinIO über 1,4 Mio. Objekte und ~200 GB heißt
  ein dedizierter Server mit viel RAM und NVMe: grob 60–120 € pro Monat. Die statische Variante (Objektspeicher
  plus CDN, Crawler auf einer kleinen Maschine) liegt bei einigen Euro im Monat.
- Personenzeit ist der große. Ruges Zahlen von 2020: ein Entwickler 5.000 € brutto im Monat und aufwärts, ein
  mittelgroßes Unternehmen rechnet mit 150.000 € Jahresumsatz pro Entwickler, größere mit über 200.000 €.
  Für Dauerbetrieb reicht kein Vollzeitäquivalent, aber „jemand, der zuverlässig in Tagen reagiert“ — und genau
  diese Zusage ist ehrenamtlich nicht einlösbar. Das ist die eigentliche Lehre aus dem Fall.

## 5 Empfehlung

Nicht bundesweit antreten. Der Reiz ist groß, aber der Grund des Scheiterns war nie die Technik, sondern die
Verstetigung, und unsere Lage ist dieselbe wie Ruges 2020.

Realistischer Schnitt, der auf dem aufsetzt, was hier schon läuft:

1. **Archivieren, solange es geht:** einen Vollabzug von `oparl.politik-bei-uns.de` ziehen (56 Körperschaften,
   die API antwortet in 0,2 s). Rein lesend, einmalig, und es sichert Scraper-Bestände, die niemand neu erzeugen
   kann.
2. **Auf den eigenen Endpunkt zielen:** derselbe ITK-Rheinland-Endpunkt trägt neben Düsseldorf (0015) auch Neuss
   (0009), Mönchengladbach (0011), Grevenbroich (0013) und den Rhein-Kreis Neuss (0019) — fünf Körperschaften,
   deren Datenform unser Code schon kennt. Das ist ein Angebot mit Publikum und ohne 127 Endpunkte Pflege.
3. **Statisch bauen, Dokumente verlinken statt spiegeln.** Mehrmandantenfähigkeit und Volltextsuche in die
   bestehende Pipeline, Ausgabe wie `data/site/index.html` heute: eine Seite ohne Server-Backend.
4. **Lizenz vorher schriftlich klären** — bei ITK Rheinland und der Landeshauptstadt, mit der Bitte, das
   OParl-`license`-Feld auf eine echte Lizenz (DL-DE-BY-2.0 oder CC BY 4.0) zu setzen. Das nützt auch allen
   anderen, die den Endpunkt nutzen.
5. **Erst Träger und Zusage, dann Öffentlichkeit.** Keine Versprechen über Aktualität, bevor klar ist, wer im
   Krankheitsfall den Crawler wieder anwirft. Lieber eine Seite, die ehrlich „Stand: Datum“ sagt, als eine, die
   Tagesaktualität behauptet.

## Quellen

- <https://politik-bei-uns.de/> sowie `/info/das-projekt`, `/info/daten`, `/info/ueber-uns`, `/info/mitmachen`, `/info/schnittstelle` (abgerufen 2026-10-12)
- Ernesto Ruge, „OpenData: bisschen Prototyp, und das war's dann?“, 2020-03-09: <https://binary-butterfly.de/artikel/opendata-bisschen-prototyp-und-das-wars-dann/>
- <https://github.com/politik-bei-uns> (`daemon/INSTALL.md`, `frontend/README.md`, GitHub-API 2026-10-12)
- <https://github.com/meine-stadt-transparent/meine-stadt-transparent> (archiviert 2023-11-25)
- <https://oparl.org/anwendungsbeispiele/>, <https://dev.oparl.org/spezifikation>, <https://dev.oparl.org/api/endpoints>
- <https://interkommunales.nrw/projekt/transparenzportal-fuer-gremiendaten/>, <https://open.nrw/Kommunen-OParl>
- <https://ris-oparl.itk-rheinland.de/Oparl/system> und `/Oparl/bodies/0015` (abgerufen 2026-10-12)
