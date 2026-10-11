/* Suche nach Strasse, Ort oder Wahlbezirk (docs/plans/08-suche.md).

   Vertraege der Seite, die dieses Skript nutzt; aendert sich einer davon, aendert sich das Skript:
     #suche-daten                 das JSON aus georep.report.search.search_payload
     georep.rows[id].cells[1]     der Name eines Wahlbezirks aus der Tabelle #districts
     .pois circle[data-name]      die Ortskreise im Karten-SVG, fuer die Marke
     svg.map                      das Karten-SVG, an das die Gruppe .suchmarken kommt
     georep.select(ids, scroll)   markiert Bezirke in Karte, Tabelle und Streudiagramm
     georep.showDocuments(t, s)   Dialog mit den Dokumenten mehrerer Begriffe

   Das Skript kennt keine Sprachregel: die Abkuerzungen (strasse/str.) kommen aus dem JSON, die
   Umlaut-Faltung ist der zweite Schluessel je Eintrag. plain() und fold() spiegeln _plain() und
   _fold() in georep/report/search.py; tests/unit/test_report_js_fold.py vergleicht beide Seiten. */
(function () {
  "use strict";
  var node = document.getElementById("suche-daten");
  var input = document.getElementById("suche-feld");
  var list = document.getElementById("suche-liste");
  var status = document.getElementById("suche-status");
  var out = document.getElementById("suche-ergebnis");
  if (!node || !input || !list || !status || !out || !window.georep) return;
  var data = JSON.parse(node.textContent);
  var abbreviations = data.abbreviations || [];
  var LIMIT = 8;
  var SVGNS = "http://www.w3.org/2000/svg";

  /* --- Faltung: der Schluessel, auf dem verglichen wird ---------------------------------- */
  function plain(text, umlauts) {
    var folded = text.toLowerCase().normalize("NFC");
    if (umlauts) {
      folded = folded.replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue");
    }
    folded = folded.normalize("NFD").replace(/\p{M}/gu, "").replace(/ß/g, "ss");
    return folded.trim().replace(/\s+/g, " ");
  }
  function quoted(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
  function foldWith(text, umlauts) {
    var folded = plain(text, umlauts);
    for (var i = 0; i < abbreviations.length; i++) {
      var target = plain(abbreviations[i][0], umlauts);
      var short = abbreviations[i][1];
      folded = folded.split(plain(short, umlauts)).join(target);
      var stem = short.replace(/\.+$/, "");
      if (stem !== short) {
        /* „muenchener str" ohne Punkt: nur am Wortende, damit „strandbad" unberuehrt bleibt. */
        var pattern = new RegExp(quoted(plain(stem, umlauts)) + "(?![0-9a-z])", "g");
        folded = folded.replace(pattern, target);
      }
    }
    return folded;
  }
  function fold(text) { return foldWith(text, false); }
  function foldAscii(text) { return foldWith(text, true); }

  var items = data.entries.map(function (entry, position) {
    return {
      term: entry[0], districts: entry[1], documents: entry[2], kind: entry[3],
      key: fold(entry[0]), ascii: foldAscii(entry[0]), position: position
    };
  });

  /* --- Abgleich: Rang 1 Praefix, Rang 2 Wortanfang, Rang 3 Teilstring -------------------- */
  function rank(key, query) {
    var at = key.indexOf(query);
    if (at < 0) return 0;
    if (at === 0) return 1;
    return " -(".indexOf(key.charAt(at - 1)) >= 0 ? 2 : 3;
  }
  function search(query, limit) {
    var folded = fold(query), ascii = foldAscii(query);
    if (!folded && !ascii) return { hits: [], total: 0 };
    var found = [];
    for (var i = 0; i < items.length; i++) {
      var a = folded ? rank(items[i].key, folded) : 0;
      var b = ascii ? rank(items[i].ascii, ascii) : 0;
      var best = a && b ? Math.min(a, b) : a || b;
      if (best) found.push({ item: items[i], rank: best });
    }
    found.sort(function (x, y) { return x.rank - y.rank || x.item.position - y.item.position; });
    return {
      hits: found.slice(0, limit).map(function (f) { return f.item; }),
      total: found.length
    };
  }

  /* --- Vorschlagsliste (APG, Editable Combobox with List Autocomplete) ------------------- */
  var shown = [], active = -1, markers = null;

  function kindLabel(kind) {
    var parts = [];
    for (var i = 0; i < kind.length; i++) {
      if (data.kinds[kind.charAt(i)]) parts.push(data.kinds[kind.charAt(i)]);
    }
    return parts.join(" und ");
  }
  function nothing(query) {
    /* Der Ergebnisblock bleibt stehen, solange die Karte markiert ist; darum nennt die Meldung
       den gesuchten Text, damit beide nicht verwechselt werden. */
    return "keine Vorschläge für \u201e" + query.trim() + "\u201c";
  }
  function closeList() {
    list.hidden = true;
    list.textContent = "";
    shown = [];
    active = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }
  function highlight(index) {
    for (var i = 0; i < list.children.length; i++) {
      list.children[i].setAttribute("aria-selected", i === index ? "true" : "false");
    }
    active = index;
    if (index < 0) {
      input.removeAttribute("aria-activedescendant");
      return;
    }
    input.setAttribute("aria-activedescendant", "suche-opt-" + index);
    list.children[index].scrollIntoView({ block: "nearest" });
  }
  function openList(query) {
    var result = search(query, LIMIT);
    list.textContent = "";
    shown = result.hits;
    shown.forEach(function (item, i) {
      var option = document.createElement("li");
      option.id = "suche-opt-" + i;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", "false");
      var name = document.createElement("span");
      name.textContent = item.term;
      var art = document.createElement("span");
      art.className = "art";
      art.textContent = kindLabel(item.kind);
      option.appendChild(name);
      option.appendChild(art);
      list.appendChild(option);
    });
    list.hidden = shown.length === 0;
    input.setAttribute("aria-expanded", shown.length ? "true" : "false");
    highlight(-1);
    if (!query.trim()) status.textContent = "";
    else if (!result.total) status.textContent = nothing(query);
    else if (result.total > shown.length) {
      status.textContent = shown.length + " von " + result.total + " Vorschlägen";
    } else if (result.total === 1) status.textContent = "ein Vorschlag";
    else status.textContent = result.total + " Vorschläge";
  }

  /* --- Ergebnis, Markierung, Adresse ---------------------------------------------------- */
  function spellings(term) {
    var all = [term];
    abbreviations.forEach(function (pair) {
      if (term.indexOf(pair[0]) >= 0) all.push(term.split(pair[0]).join(pair[1]));
    });
    return all;
  }
  function districtName(id) {
    var row = window.georep.rows[id];
    return row && row.cells[1] ? row.cells[1].textContent : "";
  }
  function dropMarkers() {
    if (markers && markers.parentNode) markers.parentNode.removeChild(markers);
    markers = null;
  }
  function mark(item) {
    dropMarkers();
    var map = document.querySelector("svg.map");
    if (!map || item.kind.indexOf("o") < 0) return;
    /* Eine eigene Gruppe, weil die Ebene .pois standardmaessig display: none traegt und ein Kind
       das nicht ueberstimmen kann. Mehrere Kreise gleichen Namens sind moeglich („Itter"). */
    var found = [];
    document.querySelectorAll(".pois circle[data-name]").forEach(function (circle) {
      if (circle.getAttribute("data-name").toLowerCase() === item.term) found.push(circle);
    });
    if (!found.length) return;
    markers = document.createElementNS(SVGNS, "g");
    markers.setAttribute("class", "suchmarken");
    markers.setAttribute("aria-hidden", "true");
    found.forEach(function (circle) {
      var marker = document.createElementNS(SVGNS, "circle");
      marker.setAttribute("class", "suchmarke");
      marker.setAttribute("cx", circle.getAttribute("cx"));
      marker.setAttribute("cy", circle.getAttribute("cy"));
      marker.setAttribute("r", "7");
      markers.appendChild(marker);
    });
    map.appendChild(markers);
  }
  function button(text, action) {
    var element = document.createElement("button");
    element.type = "button";
    element.className = "term";
    element.textContent = text;
    element.addEventListener("click", action);
    return element;
  }
  function line(text) {
    var paragraph = document.createElement("p");
    paragraph.appendChild(document.createTextNode(text));
    return paragraph;
  }
  function show(item) {
    out.textContent = "";
    var heading = document.createElement("div");
    heading.className = "value";
    heading.textContent = item.term;
    var art = document.createElement("div");
    art.className = "label";
    art.textContent = kindLabel(item.kind);
    out.appendChild(art);
    out.appendChild(heading);

    var where = line(item.districts.length === 1 ? "Wahlbezirk " : "Wahlbezirke ");
    item.districts.forEach(function (id, i) {
      if (i) where.appendChild(document.createTextNode(", "));
      where.appendChild(button(id + " " + districtName(id), function () {
        window.georep.select(id);
      }));
    });
    out.appendChild(where);

    var many = spellings(item.term).length > 1;
    var count = line(
      (item.documents === 1 ? "ein Dokument" : item.documents + " Dokumente") +
      " mit Treffer" + (many ? " (beide Schreibweisen zusammen)" : "") +
      (item.documents ? ": " : ".")
    );
    if (item.kind === "w") {
      count.appendChild(document.createTextNode(
        "Dokumente je Begriff stehen unter "
      ));
      var jump = document.createElement("a");
      jump.href = "#begriffe";
      jump.textContent = "Begriffe je Wahlbezirk";
      count.appendChild(jump);
      count.appendChild(document.createTextNode("."));
    } else if (item.documents) {
      count.appendChild(button("Dokumente zeigen", function () {
        window.georep.showDocuments(spellings(item.term), item.term);
      }));
    }
    out.appendChild(count);

    var hint = line("Auf der ");
    var toMap = document.createElement("a");
    toMap.href = "#karte";
    toMap.textContent = "Karte";
    hint.appendChild(toMap);
    hint.appendChild(document.createTextNode(
      item.districts.length === 1 ? " markiert." : " sind alle markiert."
    ));
    hint.className = "note";
    out.appendChild(hint);
    out.hidden = false;
  }
  function writeHash(term) {
    var next = "#suche=" + encodeURIComponent(term);
    if (window.location.hash === next) return;
    try {
      history.replaceState(null, "", next);
    } catch (error) {
      window.location.hash = next;  /* file:// darf replaceState verweigern */
    }
  }
  function dropHash() {
    if (window.location.hash.indexOf("#suche=") !== 0) return;
    try {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    } catch (error) { /* dann bleibt die Adresse stehen; das Feld ist trotzdem leer */ }
  }
  function choose(item, share) {
    input.value = item.term;
    closeList();
    status.textContent = kindLabel(item.kind) + ", " + item.districts.length +
      (item.districts.length === 1 ? " Wahlbezirk" : " Wahlbezirke");
    show(item);
    window.georep.select(item.districts, false);
    mark(item);
    if (share !== false) writeHash(item.term);
  }
  function reset() {
    input.value = "";
    closeList();
    status.textContent = "";
    out.hidden = true;
    out.textContent = "";
    window.georep.select(null);
    dropMarkers();
    dropHash();
  }
  function first(query) {
    var result = search(query, 1);
    if (result.hits.length) return result.hits[0];
    status.textContent = nothing(query);
    return null;
  }

  /* --- Bedienung ------------------------------------------------------------------------ */
  input.addEventListener("input", function () { openList(input.value); });
  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (list.hidden) {
        openList(input.value);
        if (shown.length && !event.altKey) highlight(event.key === "ArrowDown" ? 0 : shown.length - 1);
        return;
      }
      if (!shown.length) return;
      var next = active + (event.key === "ArrowDown" ? 1 : -1);
      highlight(next >= shown.length ? 0 : next < 0 ? shown.length - 1 : next);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      var picked = active >= 0 && shown[active] ? shown[active] : first(input.value);
      if (picked) choose(picked);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      if (list.hidden) reset(); else closeList();
      return;
    }
    if (event.key === "Tab") closeList();
  });
  list.addEventListener("pointerdown", function (event) {
    var option = event.target.closest ? event.target.closest("li") : null;
    if (!option) return;
    event.preventDefault();  /* der Fokus bleibt im Feld (APG) */
    var index = Array.prototype.indexOf.call(list.children, option);
    if (index >= 0 && shown[index]) choose(shown[index]);
  });
  document.addEventListener("pointerdown", function (event) {
    if (list.hidden || !event.target.closest) return;
    if (!event.target.closest("#suche")) closeList();
  });
  if (input.form) {
    input.form.addEventListener("submit", function (event) {
      event.preventDefault();
      var picked = first(input.value);
      if (picked) choose(picked);
    });
  }

  /* Teilbare Adresse: index.html#suche=<begriff> zeigt das Ergebnis schon beim Laden. */
  (function fromHash() {
    var hash = window.location.hash || "";
    if (hash.indexOf("#suche=") !== 0) return;
    var query = "";
    try {
      query = decodeURIComponent(hash.slice("#suche=".length));
    } catch (error) {
      return;  /* kaputte Kodierung: leeres Feld, kein Fehler */
    }
    if (!query) return;
    input.value = query;
    var picked = first(query);
    if (picked) choose(picked, false);
  })();
})();
