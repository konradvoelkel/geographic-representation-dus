# Fragen an Konrad, gesammelt vom Supervisor

Protokoll: § 6 des Meta-Plans. Je Frage: Nummer, Option, Datum, Frage, warum sie zählt, Annahme ohne
Antwort, Status. Die sieben Fragen aus § 9 des Meta-Plans stehen hier zuerst, sobald Konrad geantwortet hat.

| Nr. | Option | Datum | Frage | Warum | Annahme | Status |
|---|---|---|---|---|---|---|
| 1 | 1, 2, 4, 7 | 2026-10-11 | Netzabrufe: Dauer und Freigabe | Netz-Optionen brauchen Daten vom OParl-Server und den Portalen | nur vorbereiten | beantwortet 2026-10-11: nur stichprobenartig, mit Rate-Limiting rund 5 Minuten am Stück; alles wesentlich Längere braucht Konrads Freigabe und sollte nicht nötig sein |
| 2 | alle | 2026-10-11 | Merge-Modus | wer merged, in welcher Reihenfolge | Supervisor merged | beantwortet 2026-10-11: der Supervisor merged nach Inspektion in angemessener Reihenfolge; er darf Unteragenten um Rebase bitten und iterativ vorgehen |
| 3 | 6 | 2026-10-11 | scikit-learn trotz nox-Verbot | Themenmodell für die Gewichtung | numpy | beantwortet 2026-10-11: scikit-learn ist voll in Ordnung; TF-IDF von Hand und gensim sind nicht nötig. Branch 06 nimmt es aus FORBIDDEN in noxfile.py und begründet das in decisions.md |
| 4 | 7 | 2026-10-11 | Ort und Speicher des wiederkehrenden Abrufs | Actions hat keinen dauerhaften Speicher | Timer auf Konrads Rechner | beantwortet 2026-10-11: zuerst auf kookaburra (Heimrechner) simulieren und prüfen, aber direkt für den VPS vorbereiten; größere aktualisierte Daten wie bei bubatzblick in ein Cloudflare-R2-Bucket (wenn ein zweites nichts kostet); fertige Datensätze bis 10 GB zum Download auf dem VPS; später eine Datenplattform, Vorschläge erwünscht; Kleines direkt auf kookaburra |
| 5 | 3 | 2026-10-11 | Fremddaten aus PDFs der Stadt | Quartiersatlas liegt vermutlich als PDF vor | ja, mit Lizenz | beantwortet 2026-10-11: Quartiersatlas ausdrücklich erlaubt; andere Daten dürfen mit Lizenz verarbeitet werden, dann muss auf der Seite stehen, was alles daraus abgeleitet wurde |
| 6 | alle | 2026-10-11 | Versionierung | Tag je Option oder gesammelt | je Option | beantwortet 2026-10-11: eine Sammelversion am Ende |
| 7 | alle | 2026-10-11 | Rechnerlast | acht Agenten parallel | Wellen zu vier | beantwortet 2026-10-11: 13 Kerne insgesamt und so viel RAM wie nötig; acht Agenten dürfen gleichzeitig nox laufen lassen |
