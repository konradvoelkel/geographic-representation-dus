# Prüfliste des Snowball-Stemmers für Deutsch (Vorhaben 18)

`deutsch.tsv`: Wort und Stamm, durch einen Tabulator getrennt, eine Zeile je Paar. Es ist **jedes
17. Paar ab dem ersten** (Zeilen 1, 18, 35, …) der Beispielliste des Snowball-Projekts zur
klassischen Fassung des deutschen Stemmers, also 2 061 von 35 033 Paaren.
`tests/unit/test_search_stem.py` prüft `georep.search.stem.stem` an jedem Paar.

| Angabe | Wert |
|---|---|
| Quelle | Datenrepositorium des Snowball-Projekts, auf das snowballstem.org für Vokabular und Ausgabe verlinkt: `https://raw.githubusercontent.com/snowballstem/snowball-data/8d35251e4561/german/voc.txt` und `…/german/output.txt` |
| Fassung | Commit `8d35251e4561` (2009-12-16), der letzte Stand von `german/output.txt` vor Snowball 3.0 („Replace german with german2", 2023-09-22); das ist der Algorithmus, den die Messung benutzt hat (`docs/plans/18-einbettungen.md`, § 3.1) |
| Abrufdatum | 2026-11-24 |
| Lizenz | BSD-3-Clause, Copyright (c) 2001 Dr Martin Porter, Copyright (c) 2004, 2005 Richard Boulton (`COPYING` des Datenrepositoriums) |
| `voc.txt`, voll | 369 893 Bytes, SHA-256 `f680b1d49eb56bd6145a0ca03484fa489f0c79073ec406e80fef71d924c475af` |
| `output.txt`, voll | 308 522 Bytes, SHA-256 `926d096d73280f3bcd2dcc9aaf9945a1b460c121c043e93978ca04d364c546f8` |
| `deutsch.tsv`, diese Teilmenge | 2 061 Zeilen, SHA-256 `fa0bf3b910764147ae57076ac67c901451a7cb23c64ffe2260f340975c47e7ba` |

Die volle Liste bleibt lokal unter `/media/konrad/xtraspace/georep/fremddaten/snowball-german/`
(mit README und `COPYING`); dort stimmt der Stemmer in allen 35 033 Paaren (geprüft am
2026-11-24). Erzeugt mit

```bash
paste voc.txt output.txt | awk 'NR % 17 == 1' > deutsch.tsv
```

Die Lizenz verlangt bei der Weitergabe den Copyright-Vermerk, die Bedingungen und den
Haftungsausschluss:

> Redistribution and use in source and binary forms, with or without modification, are permitted
> provided that the following conditions are met: (1) Redistributions of source code must retain
> the above copyright notice, this list of conditions and the following disclaimer. (2)
> Redistributions in binary form must reproduce the above copyright notice, this list of
> conditions and the following disclaimer in the documentation and/or other materials provided
> with the distribution. (3) Neither the name of the Snowball project nor the names of its
> contributors may be used to endorse or promote products derived from this software without
> specific prior written permission.
>
> THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
> IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
> FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
> CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
> CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
> SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
> THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
> OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
> POSSIBILITY OF SUCH DAMAGE.
