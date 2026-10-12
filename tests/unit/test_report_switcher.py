"""Das gemeinsame Umschaltermuster der Seite (Punkt 46): Markup, Skala, Legenden, JavaScript.

Ein Umschalter ist ein ``fieldset.switcher`` mit einem Radio je Variante; die Elemente tragen die
Varianten als ``data-class-<value>`` (Stufe der Farbskala), ``data-text-<value>`` (angezeigte Zahl)
und ``data-value-<value>`` (Sortierwert), die Legenden heißen ``#legend-<value>``. Ein Muster für
alle Abschnitte, darum ein eigener Test; die Varianten selbst prüfen die Tests ihrer Abschnitte.
"""

from __future__ import annotations

import re

MACRO_CALL = 'class="switcher"'


def _fieldsets(page: str) -> list[str]:
    return re.findall(r"<fieldset[^>]*>.*?</fieldset>", page, re.S)


def test_every_switcher_is_a_fieldset_with_a_legend_and_radios(mini_page: str) -> None:
    found = [f for f in _fieldsets(mini_page) if MACRO_CALL in f]
    assert found, "die Seite hat keinen Umschalter"
    for fieldset in found:
        assert "<legend>" in fieldset  # die Beschriftung der Gruppe für Screenreader
        radios = re.findall(r'<input type="radio" name="(\w+)" value="([\w-]+)"', fieldset)
        assert len(radios) >= 2, fieldset
        assert len({name for name, _ in radios}) == 1  # eine Gruppe, ein Name
        assert fieldset.count(" checked>") == 1  # genau eine Standardvariante ohne JavaScript


def test_the_variants_of_one_group_do_not_clash_with_another(mini_page: str) -> None:
    """Der Umschalter wirkt über Abschnittsgrenzen (Karte und Tabelle je Wahlbezirk).

    Darum trennt nicht der Abschnitt die Gruppen, sondern der Name der Variante: zwei Gruppen
    dürfen keinen ``value`` teilen, sonst schaltete eine die Spalten der anderen um.
    """
    values: list[str] = []
    for fieldset in (f for f in _fieldsets(mini_page) if MACRO_CALL in f):
        values += re.findall(r'value="([\w-]+)"', fieldset)
    assert len(values) == len(set(values)), values


def test_a_variant_names_a_scale_only_if_the_page_defines_it(mini_page: str) -> None:
    """Ohne ``data-scale`` nimmt das JavaScript die sequenzielle Rampe ``q``.

    Jede andere Rampe muss als CSS-Variablen und als Klassen da sein, sonst färbt der Umschalter
    die Flächen mit einer Klasse ohne Regel und die Karte wird weiß.
    """
    scales = set(re.findall(r'data-scale="(\w+)"', mini_page))
    assert scales <= {"d"}  # heute gibt es genau eine zweite Rampe
    for ramp in scales | {"d"}:
        for step in range(5):
            assert f"--{ramp}{step}:" in mini_page
            assert f".{ramp}{step} {{ fill: var(--{ramp}{step}); }}" in mini_page


def test_the_base_script_switches_classes_texts_values_and_legends(mini_page: str) -> None:
    script = mini_page.split("window.georep", 1)[0]
    for needle in (
        "fieldset.switcher",
        'input[type="radio"]',
        '"[data-class-" + value + "]"',
        '"[data-text-" + value + "]"',
        '"[data-value-" + value + "]"',
        'getElementById("legend-" + ',
        'radio.dataset.scale || "q"',
    ):
        assert needle in script, needle


def test_every_legend_belongs_to_a_variant(mini_page: str) -> None:
    legends = set(re.findall(r'class="legend[^"]*" id="legend-([\w-]+)"', mini_page))
    values = set(re.findall(r'<input type="radio" name="\w+" value="([\w-]+)"', mini_page))
    assert legends and legends <= values, legends - values
