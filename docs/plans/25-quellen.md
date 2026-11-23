# Vorhaben 25: Quellen der Wahlprogramme und Ratsvereinbarungen

Bestandsaufnahme vom 2026-11-23, Sammel-Agent für Vorhaben 25
([plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „25“; Freigabe für
Fremddaten: § 10, Frage 8). Nur Sammlung, noch keine Auswertung. Die Dateien und ihre Textauszüge
liegen auf xtraspace unter `fremddaten/programme/` (README dort mit derselben Tabelle); **die Texte
sind urheberrechtlich geschützt und kommen nicht ins Repository**. Hier stehen nur Quellenangaben,
Zahlen und Beschreibungen in eigenen Worten.

## 1. Wer im Rat saß

Amtliche Endergebnisse von IT.NRW (`a111000kw20.pdf` mit Vergleich 2014, `a111000kw25.pdf` mit
Vergleich 2020, beide unter `fremddaten/programme/belege/`). IT.NRW nennt Wählergruppen nur mit
Nummer; die Namen stammen aus Wikipedia („Ergebnisse der Kommunalwahlen in Düsseldorf“, „Düsseldorf“,
Abschnitt Stadtrat, Wikitext abgerufen 2026-11-23).

| Partei / Wählergruppe | Sitze 2014 (82) | Sitze 2020 (90) | Sitze 2025 (92) |
|---|---|---|---|
| CDU | 31 | 30 | 31 |
| SPD | 24 | 16 | 14 |
| GRÜNE | 11 | 22 | 20 |
| FDP | 6 | 8 | 5 |
| DIE LINKE | 4 | 4 | 6 |
| AfD | 2 | 3 | 10 |
| PIRATEN | 1 | – | – |
| REP (Die Republikaner) | 1 | – | – |
| Tierschutzpartei (Partei Mensch Umwelt Tierschutz) | 1 | – | – |
| Freie Wähler (Wählergruppe; 2020 und 2025 „Wählergruppe 1“) | 1 | 1 | 1 |
| Die PARTEI | – | 2 | 1 |
| Volt | – | 2 | 2 |
| TIERSCHUTZ hier! | – | 1 | 1 |
| Klimaliste Düsseldorf (Wählergruppe 2) | – | 1 | – |
| BSW | – | – | 1 |

Fraktionsbildungen ändern die Lage im Rat, nicht die Programme: SPD und Volt bilden seit dem
2020-11-01 eine Fraktion (wieder ab 2025), Die PARTEI 2020–2025 die „PARTEI-Klima-Fraktion“ (dass
ihr drittes Mitglied von der Klimaliste kam, liegt nahe, ist aber nicht belegt), Freie Wähler,
TIERSCHUTZ hier! und Die PARTEI ab 2025 eine Ratsgruppe (Profil `duesseldorf.toml`, Wikipedia mit NRZ
vom 2025-10-07 und 2025-11-03).

## 2. Vereinbarungen im Rat

| Periode | Partner | Dokument | Beleg |
|---|---|---|---|
| 2014–2020 | SPD, GRÜNE, FDP („Ampel“-Kooperation unter OB Geisel) | Kooperationsvereinbarung 2014–2020 | Dokument selbst; Wikipedia „Düsseldorf“ (erste Ampel-Kooperation nach der Wahl 2014) |
| 2020–2025 | CDU, GRÜNE | Kooperationsvereinbarung „Gestaltungsbündnis …“, Januar 2021 | Dokument selbst; Wikipedia mit RP vom 2021-01-19 (Unterzeichnung) |
| 2025– | CDU, GRÜNE | Koalitionsvertrag „Gemeinsam für Düsseldorf …“, Dezember 2025 (Datei vom 2025-11-30) | Dokument selbst; Wikipedia mit WDR und RP; zusammen 51 von 92 Sitzen |

Alle drei liegen vor, je als Volltext-PDF mit Textebene.

## 3. Bestand

✓ = Programm liegt vor (L = Langfassung, K = Kurzfassung, H = nur als HTML-Seite), ✗ = nicht gefunden,
– = nicht im Rat.

| Partei | 2014 | 2020 | 2025 |
|---|---|---|---|
| CDU | ✓ L | ✓ L | ✓ L |
| SPD | ✓ L | ✓ L + K | ✓ L |
| GRÜNE | ✓ L | ✓ L | ✓ L |
| FDP | ✓ L | ✓ L | ✓ L |
| DIE LINKE | ✗ | ✓ L + K | ✓ L |
| AfD | ✗ | ✗ | ✓ L |
| PIRATEN | ✓ H | – | – |
| REP | ✗ | – | – |
| Tierschutzpartei | ✗ | – | – |
| Freie Wähler | ✗ | ✗ | ✗ |
| Die PARTEI | – | ✗ | ✓ H |
| Volt | – | ✓ L | ✓ L + K |
| TIERSCHUTZ hier! | – | ✓ L | ✗ |
| Klimaliste | – | ✗ | – |
| BSW | – | – | ✓ L |
| **Vereinbarung** | ✓ | ✓ | ✓ |
| **Sitze mit Programm** | 73 von 82 | 83 von 90 | 90 von 92 |

24 Programme (21 Lang-, 3 Kurzfassungen) und 3 Vereinbarungen, 27 Dateien, 68,5 MB, 1 292 PDF-Seiten,
410 609 Wörter.

## 4. Dateien

Größe in Bytes, Seiten laut pypdf 7.1.0, Wörter = Folgen aus mindestens zwei Buchstaben im
Textauszug. „Archivkopie“ heißt: die Partei liefert die Datei nicht mehr aus, sie kommt aus dem
Internet Archive (Rohbytes der Aufnahme, SHA-1-Digest gegen die CDX-Liste geprüft).

| Jahr | Partei | Titel (wörtlich) | Art | Datei | Quelle | Abruf | Größe (Bytes) | Seiten | Wörter | SHA-256 | Rechte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2014 | CDU | „Düsseldorf 2020plus. Zukunftsprogramm der CDU Düsseldorf für die Kommunalwahl 2014“ (Kreisparteitags-Beschluss vom 29. April 2014) | Langfassung | `2014/cdu/Duesseldorf2020plus_Druckfassung_doppelseitig.pdf` | http://www.cdu-fraktion-duesseldorf.de/sites/default/files/media/Dokumente/Kommunalwahl%202014/D%C3%BCsseldorf2020plus%20Druckfassung%20doppelseitig.pdf (Archivkopie, web.archive.org, Aufnahme 2017-03-22) | 2026-11-23 | 375173 | 36 | 8850 | `110a58d29a848b40d7fd765ecdf6da8c972478a4091f72271b9f9e92dd6690a9` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2014 | SPD | „Wir alle sind Düsseldorf - Unsere Stadt kann mehr.“ (Dateiname: Beschluss des Kommunalwahlprogramm der SPD Düsseldorf 2014 – Zukunftsbilder Düsseldorf – Stadt für alle) | Langfassung | `2014/spd/Beschluss_Kommunalwahlprogramm_SPD_2014_Zukunftsbilder.pdf` | https://www.spd-duesseldorf.de/wp-content/uploads/sites/198/2018/01/Beschluss_des_Kommunalwahlprogramm_der_SPD_D__sseldorf_2014_-_Zukunftsbilder_D__sseldorf_-_Stadt_f__r_alle_-.pdf (Archivkopie, web.archive.org, Aufnahme 2024-06-18) | 2026-11-23 | 1084238 | 24 | 8608 | `51e634a6827fabd734bd3a42ec307be13cdd3f9bdcd9c291ae3979b638054ec7` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2014 | GRÜNE | „Mehr Grün für Düsseldorf. Kommunalwahlprogramm 2014–2020“ (beschlossen auf der Mitgliederversammlung am 15. März 2014) | Langfassung | `2014/gruene/GrueneKW_Wahlprogramm_fin.pdf` | https://www.gruene-duesseldorf.de/wp-content/uploads/2016/07/GrueneKW_Wahlprogramm_fin.pdf (Archivkopie, web.archive.org, Aufnahme 2019-09-23) | 2026-11-23 | 1021930 | 66 | 21101 | `42d7690f0a5538a492709fafcbebe72b58533251aa19a008df0afbf483bac1aa` | Impressum: „Alle Rechte sind vorbehalten“; Nachdruck und Aufnahme in elektronische Datenbanken nur mit schriftlicher Genehmigung des Kreisverbands |
| 2014 | FDP | „Weiter stark für Düsseldorf. Wahlprogramm zur Kommunalwahl 2014.“ | Langfassung | `2014/fdp/fdp-kommunalwahlprogramm_2014.pdf` | https://www.fdp-duesseldorf.de/images/pdf/programme/fdp-kommunalwahlprogramm_2014.pdf | 2026-11-23 | 368929 | 23 | 9188 | `d54ccbe89175d401c7e1cf197e6b6c53db3bc776eb6b0f6572d7fc659cb5a5d0` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2014 | PIRATEN | „Wahlprogramm“ (Seite „Kommunalwahl 2014“; Vorwort „Unsere Idee von einer ‚Bürger Stadt‘ Düsseldorf, transparent und bürgernah.“) | Langfassung (HTML-Seite) | `2014/piraten/wahlprogramm.html` | https://duesseldorf.piratenpartei-nrw.de/kommunalwahl-2014/wahlprogramm/ | 2026-11-23 | 109256 | – (HTML) | 5489 | `77efcf2e3dd6c2b6a3a2605a2dcef08f88d59df8c7fbf249143ee92ece235c0f` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2014 | SPD, GRÜNE, FDP | „Kooperationsvereinbarung 2014 – 2020 für die Landeshauptstadt Düsseldorf“ („Chancen Ermöglichen - Nachhaltig Wirtschaften - Transparent Gestalten“) | Vereinbarung | `2014/vereinbarung-spd-gruene-fdp/KOOP-2014-2020.pdf` | https://www.gruene-duesseldorf.de/wp-content/uploads/2015/10/KOOP-2014-2020.pdf (Archivkopie, web.archive.org, Aufnahme 2019-09-20) | 2026-11-23 | 572433 | 48 | 15735 | `6590c70b0dbb12d6b510f3b7fabbfe314fa53f53f926de70a4d7863c8ae81e01` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | CDU | „Der Düsseldorf-Plan. Zukunftsprogramm der CDU Düsseldorf. Programm zur Oberbürgermeister- und Kommunalwahl 2020“ | Langfassung | `2020/cdu/wahlprogramm_cdu_duesseldorf_07-07-2020_12-30.pdf` | https://www.cduduesseldorf.de/sites/www.cduduesseldorf.de/files/downloads/wahlprogramm_cdu_duesseldorf_07-07-2020_12-30.pdf | 2026-11-23 | 603343 | 64 | 19827 | `ce1b0fa999758a039d985b75153cd72111ce3798b0086ce2657e85aa44d92a97` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | SPD | Wahlprogramm 2020 (Deckblatt ohne Textebene; erstes Kapitel „Gelebte Nachbarschaft: Wir machen Düsseldorf für Alle“) | Langfassung | `2020/spd/Wahlprogramm2020-Final.pdf` | https://www.spd-duesseldorf.de/wp-content/uploads/sites/198/2020/07/Wahlprogramm2020-Final.pdf (Archivkopie, web.archive.org, Aufnahme 2024-02-26) | 2026-11-23 | 1534069 | 80 | 27523 | `e9a99dfb043707d47d8dddde2451ece39a10a32cc81abb6021b93723c4fab074` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | SPD | Wahlprogramm 2020 kompakt (Deckblatt ohne Textebene; Kapitel wie die Langfassung) | Kurzfassung | `2020/spd/Wahlprogramm2020-Kompakt.pdf` | https://www.spd-duesseldorf.de/wp-content/uploads/sites/198/2020/08/Wahlprogramm2020-Kompakt.pdf (Archivkopie, web.archive.org, Aufnahme 2023-03-09) | 2026-11-23 | 1104377 | 24 | 6425 | `5ecfd56c36ecdf18bd39336b5e83e5b12d90cff3a889e8db4cd308e40ef8d4ea` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | GRÜNE | „BÜNDNIS 90/DIE GRÜNEN Kreisverband Düsseldorf: Programm zur Kommunalwahl 2020“ (PDF-Titel) | Langfassung | `2020/gruene/b90-gruene-kv-duesseldorf-wahlprogramm-kommunalwahl-2020.pdf` | https://www.gruene-duesseldorf.de/wp-content/uploads/2020/07/b90-gru%CC%88ne-kv-du%CC%88sseldorf-wahlprogramm-kommunalwahl-2020.pdf (Archivkopie, web.archive.org, Aufnahme 2025-02-24) | 2026-11-23 | 2148756 | 114 | 36979 | `ceb242682a0a1986a31d6742bb4d0d48c61741365fef7232615334138c6643c0` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | FDP | „Das Wahlprogramm der Freien Demokraten. Kommunalwahl 2020. Düsseldorf verstehen.“ | Langfassung | `2020/fdp/fdp-kommunalwahlprogramm_2020.pdf` | https://www.fdp-duesseldorf.de/images/pdf/programme/fdp-kommunalwahlprogramm_2020.pdf | 2026-11-23 | 442026 | 66 | 21990 | `3a0513c77c63391a57c1df2aaac796cd01532fca5ec2b22a533610ff2788696e` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | DIE LINKE | „Radikal menschlich. Unser Programm für Düsseldorf“ | Langfassung | `2020/linke/programm.pdf` | https://www.die-linke-duesseldorf.de/fileadmin/kvduesseldorf/Wahlkaempfe/Kommunalwahl_2020/programm.pdf | 2026-11-23 | 24880705 | 37 | 9088 | `9ab4a42897fc51871a3a841eaee9e98bea6b6d9be70b3c07cdfcf3ecbbb4bd1f` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | DIE LINKE | „Kurz und Knackig! Unser Programm für Düsseldorf.“ | Kurzfassung | `2020/linke/kurz_druck_website.pdf` | https://www.die-linke-duesseldorf.de/fileadmin/kvduesseldorf/Wahlkaempfe/Kommunalwahl_2020/kurz_druck_website.pdf | 2026-11-23 | 64412 | 8 | 971 | `ca1b7422ac56b97a09bd798f992693c8aa5550dc76bcc4f08d82d6acf3f9f342` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | Volt | „Wahlprogramm zur Kommunalwahl 2020“ („#machDUSbesser“) | Langfassung; unter der Original-URL liegt heute das Programm 2025 | `2020/volt/kommunalwahlprogramm_duesseldorf_2020.pdf` | https://voltdeutschland.org/storage/assets-duesseldorf/pdf/kommunalwahlprogramm_duesseldorf_2020.pdf (Archivkopie, web.archive.org, Aufnahme 2025-02-25) | 2026-11-23 | 490355 | 56 | 13332 | `404156300ae8455fe33a72665d223ada88ccc1b0b1bf80669d5fbf246101b9a9` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | TIERSCHUTZ hier! | „Wahlprogramm Düsseldorf Kommunalwahl 2020. Das Programm des Kreisverbandes Düsseldorf der Aktion Partei für Tierschutz – TIERSCHUTZ hier!“ | Langfassung | `2020/tierschutz-hier/Wahlprogramm-Duesseldorf.pdf` | https://tierschutz-hier.de/wp-content/uploads/2020/09/Wahlprogramm-Duesseldorf.pdf | 2026-11-23 | 205400 | 6 | 1977 | `b28fe9a05cc2ec648a46a37074bac222e49e21782b1b5cea1e03de38a7b0e6ce` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2020 | CDU, GRÜNE | „Gestaltungsbündnis für ein zukunftsfestes Düsseldorf. Kooperationsvereinbarung zwischen CDU Düsseldorf und BÜNDNIS 90/DIE GRÜNEN Düsseldorf“ (Düsseldorf, Januar 2021) | Vereinbarung | `2020/vereinbarung-cdu-gruene/Koop-vereinbarung-CDU-GRUENE_2021-02.pdf` | https://www.gruene-duesseldorf.de/wp-content/uploads/2021/02/Koop-vereinbarung-CDU-GRUENE.pdf (Archivkopie, web.archive.org, Aufnahme 2023-03-14) | 2026-11-23 | 1504122 | 91 | 34941 | `5ce18909fa67dd3dd02315bfec408441465c9ec9d7e75ec4b44470fcb5028cd0` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | CDU | „Düsseldorf machen! Klar weiter. Klar besser. Klar CDU. Programm zur Oberbürgermeister- und Kommunalwahl 2025“ | Langfassung | `2025/cdu/duesseldorf_machen_klar_weiter._klar_besser._klar_cdu.pdf` | https://www.cduduesseldorf.de/sites/www.cduduesseldorf.de/files/duesseldorf_machen_klar_weiter._klar_besser._klar_cdu.pdf | 2026-11-23 | 1597060 | 101 | 32312 | `51fb4de2433a39ce19960a8a15563ca16460aec4bc46f52bde793df1587d1be3` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | SPD | „Ein guter Plan. Für Düsseldorf. Für dich. Wahlprogramm der SPD Düsseldorf zur Kommunalwahl 2025“ | Langfassung | `2025/spd/Wahlprogramm.pdf` | https://www.spd-duesseldorf.de/wp-content/uploads/sites/198/2025/07/Wahlprogramm.pdf | 2026-11-23 | 4604307 | 36 | 13896 | `cf3e2f8a91cb4407962f1d8674a2ae37b3c407e347322391193c217bac4a8af4` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | GRÜNE | „Kommunalwahlprogramm 2025“ (Linktext der Quelle; Deckblatt ohne Textebene) | Langfassung | `2025/gruene/Kommunalwahlprogramm_2025.pdf` | https://gruene-duesseldorf.de/content/files/2026/07/Kommunalwahlprogramm_2025.pdf | 2026-11-23 | 731631 | 66 | 23585 | `f5de440e99692c050f604fbc65e3baa20252f4156ddaec03d92127ba460f7740` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | FDP | „FDP Kommunalwahlprogramm 2025“ (Linktext der Quelle; erstes Kapitel „Für ein starkes, modernes Düsseldorf“) | Langfassung | `2025/fdp/fdp-kommunalwahlprogramm_2025.pdf` | https://www.fdp-duesseldorf.de/images/pdf/programme/fdp-kommunalwahlprogramm_2025.pdf | 2026-11-23 | 833778 | 81 | 25213 | `3f2a596846722fd4372e90176d5bf417c1284e471fb1e2808b47ff461571470b` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | DIE LINKE | „Düsseldorf für alle! Sozial. Klimagerecht. Antifaschistisch.“ | Langfassung | `2025/linke/Wahlprogramm.pdf` | https://www.die-linke-duesseldorf.de/fileadmin/kvduesseldorf/Kommunalwahl_2025/Wahlprogramme/Wahlprogramm.pdf | 2026-11-23 | 1197110 | 64 | 14721 | `5402b9c73b2fcf06533756bc80b2a721150d467f6ac0e16e4c5f0a9aa07082ac` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | AfD | „Düsseldorfer Kommunalwahlprogramm 2025“ („Mit Augenmaß und Verstand zu Freiheit, Sicherheit und Wohlstand“) | Langfassung | `2025/afd/Broschuere_Kommunalwahlprogramm.pdf` | https://afd-duesseldorf.de/files/docs/platforms/Broschuere_Kommunalwahlprogramm.pdf | 2026-11-23 | 9688110 | 44 | 8207 | `708ce4e1643d571f97e2d091b454723c4c48c140cdbd29e5717499735efae197` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | Volt | „Wahlprogramm Kommunalwahl 2025 in Düsseldorf. Europas beste Ideen für unsere Stadt“ | Langfassung | `2025/volt/wahlprogramm_volt_duesseldorf_2025.pdf` | https://voltdeutschland.org/storage/assets-duesseldorf/pdf/wahlprogramm_volt_duesseldorf_2025.pdf | 2026-11-23 | 6004034 | 74 | 23163 | `f9723ceeb673ddf61770fa5e42677896c77e7e76419651537038256b767d8170` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | Volt | „Kurzversion Wahlprogramm Kommunalwahl 2025 in Düsseldorf“ | Kurzfassung | `2025/volt/wahlprogramm_volt_duesseldorf_2025_vf_kurzwahlprogramm.pdf` | https://voltdeutschland.org/storage/assets-duesseldorf/pdf/2025-kommunalwahl-kurzwahlprogramme/wahlprogramm_volt_duesseldorf_2025_vf_kurzwahlprogramm.pdf | 2026-11-23 | 4873067 | 14 | 4771 | `2d7e62a396418d4eb80248d92864c9513316e47d65c45131b3854058bc87967e` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | Die PARTEI | „00 – Wahlprogramm für die Kommunalwahl“ (Motto „Hauptsache schön“) | Langfassung (HTML-Seite) | `2025/partei/wahlprogramm-kw.html` | https://die-partei-duesseldorf.de/wahlen/kommunalwahl/wahlprogramm-kw/ | 2026-11-23 | 78511 | – (HTML) | 575 | `bc3a721e90de66b223c1dc31f13e99cf5a4b560af6ad7af21683e81dda00709b` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | BSW | „BSW-Wahlprogramm für Düsseldorf. Kommunalwahl 14. September 2025“ | Langfassung | `2025/bsw/BSW-Wahlprogramm_Duesseldorf-1.pdf` | https://duesseldorf.bsw-vg.nrw/wp-content/uploads/sites/30/2025/08/BSW-Wahlprogramm_Duesseldorf-1.pdf | 2026-11-23 | 1792621 | 12 | 2898 | `43781e51e0d9c0bd7ca01dfe5a4abc1c97820013244bc83d675d609baf909b8c` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |
| 2025 | CDU, GRÜNE | „Gemeinsam für Düsseldorf: Verantwortung übernehmen, Fortschritt gestalten. Koalitionsvertrag zwischen CDU Düsseldorf und BÜNDNIS 90/DIE GRÜNEN Düsseldorf“ (Düsseldorf, Dezember 2025) | Vereinbarung | `2025/vereinbarung-cdu-gruene/251130-KOA-Vertrag-CDU-GRUeNE-2025-2030-final.pdf` | https://gruene-duesseldorf.de/content/files/2026/07/251130-KOA-Vertrag-CDU-GRUeNE-2025-2030-final.pdf | 2026-11-23 | 604058 | 57 | 19244 | `97917f3f05c2992d8f405f3cbfa25f027711f8150e0b65ff8d0d6eed924f3f6f` | keine Lizenzangabe; urheberrechtlich geschützt, nur lokal |

Rechtehinweis: Keines der Dokumente trägt eine freie Lizenz. Nur das GRÜNEN-Programm 2014 nennt
ausdrücklich einen Vorbehalt (Nachdruck und Aufnahme in elektronische Datenbanken nur mit Genehmigung).
Für alle gilt darum: lokal lesen und auswerten, ins Repository und auf die Seite nur abgeleitete
Angaben (Labels, Zählungen, Zuordnungen mit Fundstelle), keine Textauszüge.

## 5. Was fehlt oder nicht frei zugänglich ist

| Jahr | Partei | Stand | Gesucht in |
|---|---|---|---|
| 2014 | DIE LINKE | nicht gefunden | Website `die-linke-duesseldorf.de` und `kvduesseldorf.dielinke-nrw.de` im Internet Archive (Wahlseite 2014 archiviert, das Programm nicht; ein verlinktes Wahlkampf-PDF ist nie archiviert worden), Websuche |
| 2014 | AfD | nicht gefunden | `afd-duesseldorf.de` hat Archivaufnahmen erst ab 2016 (drei) und 2024; Websuche |
| 2020 | AfD | nicht gefunden | wie 2014; zwei mögliche Domains der Ratsfraktion ohne Programm im Archiv; Websuche |
| 2014 | REP | nicht gefunden | Websuche |
| 2014 | Tierschutzpartei | nicht gefunden | Websuche; laut englischer Wikipedia gründeten unabhängige Kandidaten 2017 in Düsseldorf TIERSCHUTZ hier! |
| 2014, 2020, 2025 | Freie Wähler (Unabhängige Wählergemeinschaft für Düsseldorf) | nicht gefunden | `fw-duesseldorf.de` im Archiv fast nur 2012–2013, ohne Programm; keine heutige Website gefunden; Websuche |
| 2014 | PIRATEN | nur als HTML-Seite | `duesseldorf.piratenpartei-nrw.de/kommunalwahl-2014/wahlprogramm/` (lebt noch); kein PDF |
| 2020 | Die PARTEI | nicht gefunden | Seite „Kommunalwahl 2020“ (archiviert) sammelt nur Unterstützungsunterschriften |
| 2020 | Klimaliste | nicht gefunden | `klimaliste-duesseldorf.de` erst ab 2021 archiviert; eine Projektseite auf wechange.de ist nicht geöffnet worden; Websuche |
| 2025 | TIERSCHUTZ hier! | nicht gefunden | Website der Partei (Seiten „Kommunalwahl NRW 2025“, „Kreisverband Düsseldorf“, OB-Kandidaten) nennt kein Programm |
| – | ULB Düsseldorf, elektronisches Pflichtexemplar (`e-pflicht.ulb.hhu.de`) | nicht benutzt | die Suche zeigt eine Browserprüfung („Verifying your browser“); nicht umgangen. Dort könnten Parteischriften als Pflichtexemplar liegen |

Kurzfassungen: Für CDU, GRÜNE und FDP ist keine Kurzfassung gesucht und keine nebenbei gefunden worden;
die drei Kurzfassungen (SPD 2020, LINKE 2020, Volt 2025) lagen neben der Langfassung.

## 6. Local Manifesto Project

- **Quelle**: Projektseite `localpartymanifestos.de` (Martin Gross, LMU München; Michael Jankowski,
  Universität Oldenburg); Zitierweise Gross und Jankowski (2020), West European Politics 43 (1),
  S. 74–101. Die LMU-Seite zum Nachfolgeprojekt (`en.localpolitics.gsi.uni-muenchen.de/project/`)
  nennt „mehr als tausend“ Programme und Koalitionsvereinbarungen aus Großstädten seit 1990.
- **Erreichbarkeit am 2026-11-23**: `http://www.localpartymanifestos.de/` antwortet mit 404, HTTPS mit
  einem selbstsignierten Zertifikat. Die letzte Archivaufnahme der Startseite (2022-01-21) beschreibt
  das Angebot: mehr als 800 Programme aus Städten über 100 000 Einwohnern, die meisten aus den
  2000er Jahren, dazu eine Shiny-App für Skalierung und Themenmodelle.
- **Form**: Rohtexte, kein Codierschema wie beim Manifesto Project (keine Quasi-Satz-Codes);
  zwei ZIP-Archive über Dropbox-Links: alle Programme als `.txt` in UTF-8 (18 612 095 Bytes) und alle
  Koalitionsvereinbarungen als `.txt` (1 684 501 Bytes). Beide Links antworten heute noch mit 200
  (nur Kopfzeilen abgefragt). Die Shiny-App antwortet auf eine Kopfzeilenanfrage mit 405.
- **Bedingungen**: keine Registrierung, keine Zustimmung zu Bedingungen, **keine Lizenz genannt**, nur
  die Bitte um Zitierung. Die Texte selbst bleiben Werke der Parteien.
- **Düsseldorf**: ob und welche Düsseldorfer Programme enthalten sind, lässt sich ohne das ZIP nicht
  sagen. Das Paper wertet Wahlen bis 2016 aus, die Seite nennt 2022 „die meisten aus den 2000er
  Jahren“; für Vorhaben 25 käme also höchstens 2014 in Frage (genau das Jahr mit den größten Lücken:
  LINKE, AfD, Kleinparteien).
- **Nicht geladen**, weil ZIP nicht zu den freigegebenen Dateiarten gehört (nur PDF, HTML, Text).
  Frage an den Supervisor in § 9.

## 7. Mönchengladbach (optional, nur begonnen)

Ratssitze laut IT.NRW (`belege/wahlergebnis-mg-2025/a116000kw25.pdf`): 2020 (76) CDU 26, SPD 20,
GRÜNE 16, AfD 5, FDP 4, LINKE 3, Die PARTEI 2; 2025 (70) CDU 24, SPD 20, AfD 11, GRÜNE 6, LINKE 4,
FDP 2, Die PARTEI 1, Volt 1, BSW 1. Welche Vereinbarungen 2020 und 2025 gelten, war in zwei Suchen
nicht zu belegen (gefunden nur die Ampel-Vereinbarung 2009–2014 auf einer Lokalzeitungsseite). Programme
sind nicht gesammelt. Ein Ansatzpunkt aus der Websuche: ein Programmtext „Empathisch in die Zukunft:
Für ein soziales Mönchengladbach“ auf `programm2025.antragsgruen.de` (Partei nicht geprüft).

## 8. Was das für Vorhaben 25 heißt

### 8.1 Umfang

Langfassungen in Seiten / Wörtern (Kurzfassungen in Klammern):

| Partei | 2014 | 2020 | 2025 |
|---|---|---|---|
| CDU | 36 / 8 850 | 64 / 19 827 | 101 / 32 312 |
| SPD | 24 / 8 608 | 80 / 27 523 (24 / 6 425) | 36 / 13 896 |
| GRÜNE | 66 / 21 101 | 114 / 36 979 | 66 / 23 585 |
| FDP | 23 / 9 188 | 66 / 21 990 | 81 / 25 213 |
| DIE LINKE | – | 37 / 9 088 (8 / 971) | 64 / 14 721 |
| AfD | – | – | 44 / 8 207 |
| Volt | – | 56 / 13 332 | 74 / 23 163 (14 / 4 771) |
| PIRATEN | HTML / 5 489 | – | – |
| TIERSCHUTZ hier! | – | 6 / 1 977 | – |
| BSW | – | – | 12 / 2 898 |
| Die PARTEI | – | – | HTML / 575 |
| Vereinbarung | 48 / 15 735 | 91 / 34 941 | 57 / 19 244 |

Zusammen rund 329 000 Wörter Langfassung, 12 000 Wörter Kurzfassung und 70 000 Wörter Vereinbarung.
Die Programme wachsen von 2014 auf 2020 deutlich (CDU, SPD, FDP etwa auf das Zwei- bis Dreifache); die
vier Parteien mit allen drei Jahren (CDU, SPD, GRÜNE, FDP) tragen 249 000 Wörter.

### 8.2 Sprache, Gliederung, Textqualität

- Alles Deutsch; Volt bietet das Kurzprogramm 2025 zusätzlich auf Englisch, Niederländisch und
  Japanisch an (nicht geladen). Gendern wechselt zwischen Dokumenten (Sternchen, Doppelform, keines);
  die Fassungen der Kooperationsvereinbarung 2021 unterscheiden sich genau darin.
- Alle Programme gliedern nach Politikfeldern (Mobilität, Wohnen, Bildung, Wirtschaft, Umwelt, Soziales,
  Kultur, Sicherheit …), oft mit Vorwort an die Wählerinnen und Wähler. Die Kapitel passen gut auf die
  Hauptthemen des CAP (Vorhaben 19), was eine Vorauswahl der Antragspaare je Thema erlaubt.
- Zwei Bauarten: **Listen** (GRÜNE 2014 und 2020, Volt 2025, LINKE 2025, CDU 2020, FDP 2014 und 2025,
  CDU 2025 mit Spiegelstrichen und fett gesetztem Stichwort) und **Fließtext** (SPD alle Jahre, CDU 2014,
  GRÜNE 2025, AfD 2025, alle drei Vereinbarungen). Bei Listen ist ein Punkt meist ein Versprechen; bei
  Fließtext muss die Zerlegung satzweise geschehen.
- Das CDU-Programm 2025 trennt in jedem Kapitel „Das haben wir erreicht (2020−2025)“ von „Das haben
  wir vor (2025−2030)“ (19 Abschnitte) — eine Selbstauskunft zur Erfüllung früherer Versprechen, die
  sich gegen die Anträge und Beschlüsse der Periode und gegen das Programm 2020 prüfen lässt.
- Alle PDF haben eine Textebene; OCR ist nicht nötig. Einige Deckblätter sind reine Bilder (SPD 2020,
  GRÜNE 2025), die LINKE 2020 hat Bildseiten ohne Text (31 von 37 Seiten mit Text). Silbentrennung am
  Zeilenende bleibt im Auszug stehen und muss vor jedem Abgleich entfernt werden; das Inhaltsverzeichnis
  der LINKEN 2025 trägt Ersatzzeichen statt Füllpunkten.

### 8.3 Lassen sich Versprechen abgrenzen?

Grobe Zählung über den Textauszug (Regex, keine Messung; Wörter wie in § 4):
„Versprechensformeln“ = *wir wollen*, *wir werden*, *wir fordern*, *(wir) setzen uns … ein*,
*wir sind für/gegen*; „Listenpunkte“ = Zeilen, die mit einem Aufzählungszeichen beginnen (pypdf
verliert manche Zeichen, die Zahl ist eine Untergrenze); „Zahl/Frist“ = *bis 20xx*, Prozent,
Millionen, Kilometer, *neue/zusätzliche* nach einer Zahl; „prüfen“ = *prüfen*, *geprüft*, *Prüfauftrag*.

| Jahr | Dokument | Wörter | Versprechensformeln | je 1000 Wörter | Listenpunkte | Zahl/Frist | prüfen |
|---|---|---|---|---|---|---|---|
| 2014 | CDU | 8850 | 17 | 1,9 | 0 | 7 | 0 |
| 2014 | SPD | 8608 | 56 | 6,5 | 0 | 4 | 1 |
| 2014 | GRÜNE | 21101 | 130 | 6,2 | 329 | 31 | 5 |
| 2014 | FDP | 9188 | 36 | 3,9 | 104 | 16 | 7 |
| 2014 | PIRATEN | 5489 | 27 | 4,9 | 0 | 3 | 3 |
| 2014 | Vereinbarung SPD/GRÜNE/FDP | 15735 | 110 | 7,0 | 1 | 9 | 23 |
| 2020 | CDU | 19827 | 148 | 7,5 | 202 | 7 | 7 |
| 2020 | SPD | 27523 | 184 | 6,7 | 2 | 52 | 7 |
| 2020 | SPD (kurz) | 6425 | 86 | 13,4 | 0 | 15 | 2 |
| 2020 | GRÜNE | 36979 | 213 | 5,8 | 215 | 47 | 8 |
| 2020 | FDP | 21990 | 176 | 8,0 | 6 | 12 | 37 |
| 2020 | DIE LINKE | 9088 | 33 | 3,6 | 3 | 11 | 1 |
| 2020 | DIE LINKE (kurz) | 971 | 3 | 3,1 | 48 | 2 | 0 |
| 2020 | Volt | 13332 | 0 | 0,0 | 51 | 18 | 6 |
| 2020 | TIERSCHUTZ hier! | 1977 | 9 | 4,6 | 0 | 1 | 0 |
| 2020 | Vereinbarung CDU/GRÜNE | 34941 | 218 | 6,2 | 4 | 17 | 55 |
| 2025 | CDU | 32312 | 111 | 3,4 | 31 | 106 | 18 |
| 2025 | SPD | 13896 | 33 | 2,4 | 3 | 20 | 9 |
| 2025 | GRÜNE | 23585 | 195 | 8,3 | 9 | 19 | 19 |
| 2025 | FDP | 25213 | 169 | 6,7 | 103 | 12 | 15 |
| 2025 | DIE LINKE | 14721 | 70 | 4,8 | 272 | 21 | 4 |
| 2025 | AfD | 8207 | 27 | 3,3 | 0 | 5 | 5 |
| 2025 | Volt | 23163 | 106 | 4,6 | 377 | 35 | 7 |
| 2025 | Volt (kurz) | 4771 | 26 | 5,4 | 28 | 9 | 1 |
| 2025 | Die PARTEI | 575 | 5 | 8,7 | 0 | 4 | 0 |
| 2025 | BSW | 2898 | 19 | 6,6 | 4 | 4 | 2 |
| 2025 | Vereinbarung CDU/GRÜNE | 19244 | 112 | 5,8 | 3 | 19 | 36 |

Was die Zahlen nahelegen, mit Vorbehalt bis zur Messung in Stufe 1:

- Die Dichte der Formeln liegt meist bei 3 bis 8 je 1000 Wörter; ein Programm mit 20 000 Wörtern
  enthält also grob 100 bis 150 Sätze, die nach einem Versprechen klingen. Über alle 27 Dokumente sind
  das einige tausend Kandidaten — zu viele für Handarbeit, genug für ein Modell mit Stichprobe.
- Volt 2020 hat null Treffer, weil es in der dritten Person schreibt („Volt will …“, „Düsseldorf
  soll …“): Ein Extraktor auf festen Formeln verfehlt ganze Programme; er muss Modalverben und Subjekt
  frei lesen.
- Die Vereinbarungen kündigen oft nur eine **Prüfung** an (*prüfen* und verwandte Wörter: 23 Stellen
  2014, 55 in 2021, 36 in 2025). Das Codebuch nach Thomson u. a. muss vorab festlegen, ob „wir prüfen X“
  ein Versprechen ist (Vorschlag: eigene Klasse, erfüllt, wenn ein Prüfauftrag oder Bericht im Rat
  nachweisbar ist).

Drei Beispiele in eigenen Worten, von gut zu schlecht prüfbar:

1. Die Kooperationsvereinbarung 2021 sagt zu, die drei sogenannten Umweltspuren im ersten Quartal 2021
   wieder aufzuheben. Das ist ein Versprechen mit Gegenstand, Handlung und Frist; ob es erfüllt ist,
   zeigt ein Ratsbeschluss oder eine Verwaltungsvorlage mit Datum.
2. Der Koalitionsvertrag 2025 hält am Ziel fest, bis 2030 alle Privathaushalte mit Glasfaser zu
   versorgen. Das ist messbar, aber ein Ergebnis, das der Rat nicht allein herbeiführt; die Erfüllung
   verlangt Daten außerhalb der Ratsdokumente, die Zuordnung zu Anträgen nur Teilschritte.
3. Das GRÜNEN-Programm 2025 will sich für mehr Bewegungskitas einsetzen. Richtung ohne Menge und Frist:
   jeder einschlägige Antrag passt, und „erfüllt“ ist kaum zu entscheiden. Solche Sätze sind im
   Fließtext häufig; nach der Definition von Thomson u. a. ist ein Satz nur dann ein Versprechen, wenn
   sich objektiv feststellen lässt, ob die Handlung geschah oder das Ergebnis eintrat — diese hier
   fielen heraus, und das Codebuch muss die Grenze mit Beispielen ziehen.

Dazwischen liegt das CDU-Programm 2025, das als Vorhaben des Oberbürgermeisters ankündigt, die
U3-Betreuung im Umfang von 35 Wochenstunden beitragsfrei zu stellen: konkret, über die
Elternbeitragssatzung im Rat prüfbar.

### 8.4 Folgerungen

- **Umfang der Messung**: Vollständig sind CDU, SPD, GRÜNE und FDP über alle drei Wahlen und die drei
  Vereinbarungen; LINKE und Volt für 2020 und 2025. Damit lässt sich die Frage für die
  Mehrheitsparteien beider Perioden beantworten. Die Lücken 2014 (LINKE, AfD, vier Kleinparteien mit
  zusammen 9 Sitzen) und die AfD 2020 betreffen vor allem die Opposition; der Vergleich der
  Programmnähe (Frage nach 15) bleibt für 2014 unvollständig.
- **Perioden im Korpus**: Die Hauptperiode (Profil `duesseldorf`, Wahlperiode 2020–2025) gehört zu den
  Programmen 2020 und der Kooperationsvereinbarung 2021 — dort ist die Abdeckung gut (83 von 90
  Sitzen). Das Profil `duesseldorf-2014` (2014–2020) gehört zu den Programmen 2014 und der
  Ampel-Vereinbarung, `duesseldorf-2025` (laufende Periode) zu den Programmen 2025 und dem
  Koalitionsvertrag; dort ist die Erfüllung erst in Ansätzen zu messen.
- **Vorverarbeitung**: Silbentrennung entfernen, Deckblatt, Inhaltsverzeichnis und Impressum abschneiden,
  bei HTML nur den Inhaltsbereich nehmen (so geschehen). Die Wortzahlen hier zählen alles mit.
- **Weitere Quelle in Reichweite**: die Bezirksprogramme der GRÜNEN 2020 und 2025 (neun Bezirke im
  Archiv) passen zur geographischen Frage des Projekts, sind aber nicht geladen.

## 9. Fragen an den Supervisor (nicht blockierend)

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 25.1 | Darf das LMP-ZIP (18,6 MB, `.txt` in UTF-8, keine Registrierung) geladen werden, um nachzusehen, ob Düsseldorf 2014 enthalten ist? | Einzige Chance auf die fehlenden Programme 2014 (LINKE, AfD, Kleinparteien) | nicht laden |
| 25.2 | Sollen die Bezirksprogramme der GRÜNEN (2020, 2025) dazu? | Ortsbezug der Versprechen, Bezirksvertretungen | nicht laden |
| 25.3 | Mönchengladbach 2020 und 2025 weiter verfolgen? | Zweite Stadt im Projekt; Vereinbarungen dort unklar | ruhen lassen |
| 25.4 | Darf Konrad die Freien Wähler, die AfD (2014, 2020) und die LINKE (2014) direkt nach ihren Programmen fragen, oder bleibt es bei öffentlichen Quellen? | Schließt die Lücken 2014 und 2020 | öffentliche Quellen |

## 10. Werkzeuge

Abruf und Auszug liefen mit Hilfsskripten außerhalb des Repositorys
(`fremddaten/werkzeuge-programme/`: `dl.sh`, `dlw.sh`, `cdx.sh`, `extract.py`, `markers.py`,
`gen_table.py`; Zahlen in `stats.json` daneben), Text mit pypdf 7.1.0 aus dem Projekt-Venv, alles mit
`python -I`. Ein Messskript im Repository (`25-…-messung.py`) folgt mit Stufe 1.
