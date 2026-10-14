"""georep: geografische Repräsentation in Ratsdokumenten.

Ortsmarker je Wahlbezirk aus OpenStreetMap, Wikidata und Wikipedia, Treffer in den OParl-Dokumenten des
Stadtrats, Zusammenhang mit der Wahlbeteiligung. Aufbau in ``docs/architecture.md``, Gründe in
``docs/decisions.md``. Vollständig typisiert, Polars für Tabellen, Parquet für Abgeleitetes, atomare
Schreibvorgänge, deal-Verträge an den Batch-Grenzen.
"""

__version__ = "0.13.0"
