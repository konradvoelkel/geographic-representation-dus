/* Die Karte der Startseite (docs/plan-startseite-2026-11.md, § 4 bis § 7). Die Schaltflächen der
   Orte heißen start-place und nicht term: auf button.term hört der Rahmen und öffnet die Dokumente
   eines Begriffs. Ohne Skript und aus dem
   Dateisystem bleibt die Choroplethe stehen, die der Bau rechnet; mit Skript laedt diese Datei
   data/karte.json und zeichnet je Ort einen Kreis, dessen Flaeche der Zahl der Dokumente im
   Zeitraum folgt. Zeitraum und Gremium stehen in der Adresse (#zeitraum=2024-10..2025-09&gremium=OVA). */
(function () {
  "use strict";
  var root = document.getElementById("start-karte"), g = window.georep;
  if (!root || !g) return;
  var SRC = "data/karte.json", NS = "http://www.w3.org/2000/svg", TAP = 24;
  var MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
  var svg = document.getElementById("start-map"), full = svg.getAttribute("viewBox");
  var $ = function (id) { return document.getElementById(id); };
  /* Tausender mit schmalem Leerzeichen wie format_de auf der Seite */
  var fmt = function (n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202f"); };
  g.loadJson(SRC).then(start).catch(function () {
    var note = $("start-offline");
    note.textContent = g.offlineNote("Die Daten der Karte", SRC);
    note.hidden = false;
  });

  function start(k) {
    var places = k.places, docs = k.docs, bodies = k.gremien, n = k.months.length;
    var y0 = +k.start.slice(0, 4), m0 = +k.start.slice(5, 7) - 1;
    var areas = Array.prototype.slice.call(svg.querySelectorAll(".start-area"));
    var byNumber = {};
    areas.forEach(function (a) { byNumber[a.dataset.wb] = a; });
    var st = { von: k.window[0], bis: k.window[1], art: "", body: "", mode: "punkte" };
    var atPlace = places.map(function () { return []; }), atDistrict = {};
    docs.forEach(function (d, i) {
      var seen = {};
      for (var j = 2; j < d.length; j++) {
        var w = d[j] < 0 ? -d[j] : places[d[j]][2];
        if (d[j] >= 0) atPlace[d[j]].push(i);
        if (!seen[w]) { seen[w] = 1; (atDistrict[w] = atDistrict[w] || []).push(i); }
      }
    });

    function month(i) { var t = m0 + i; return [y0 + Math.floor(t / 12), t % 12]; }
    function monthLabel(i) { var m = month(i); return MONTHS[m[1]] + " " + m[0]; }
    function monthKey(i) { var m = month(i); return m[0] + "-" + (m[1] < 9 ? "0" : "") + (m[1] + 1); }
    function monthIndex(text) {
      var p = /^(\d{4})-(\d{2})$/.exec(text);
      return p ? (+p[1] - y0) * 12 + (+p[2] - 1 - m0) : NaN;
    }
    function windowLabel() {
      var text = st.von === st.bis ? monthLabel(st.von) : monthLabel(st.von) + " bis " + monthLabel(st.bis);
      if (st.bis === n - 1 && k.ended) text += ", Ende der Wahlperiode";
      return text;
    }
    function kindLabel(kind) {
      for (var i = 0; i < k.arten.length; i++) if (k.arten[i][0] === kind) return k.arten[i][1];
      return kind;
    }
    function bodyLabel() {
      if (st.body) for (var i = 0; i < bodies.length; i++) if (bodies[i][0] === st.body) return bodies[i][1];
      return st.art ? kindLabel(st.art) : "alle Gremien";
    }

    /* --- Bedienung: Zeitraum, Gremium, Ansicht, Ausschnitt ------------------------------------ */
    var von = $("start-von"), bis = $("start-bis");
    [von, bis].forEach(function (input) { input.max = n - 1; });
    function setRange(a, b) {
      a = Math.max(0, Math.min(n - 1, a)); b = Math.max(0, Math.min(n - 1, b));
      st.von = Math.min(a, b); st.bis = Math.max(a, b);
    }
    function showRange() {
      von.value = st.von; bis.value = st.bis;
      von.setAttribute("aria-valuetext", monthLabel(st.von));
      bis.setAttribute("aria-valuetext", monthLabel(st.bis));
      $("start-range").textContent = windowLabel();
    }
    von.addEventListener("input", function () { setRange(+von.value, Math.max(+von.value, st.bis)); update(false); });
    bis.addEventListener("input", function () { setRange(Math.min(+bis.value, st.von), +bis.value); update(false); });
    [von, bis].forEach(function (input) { input.addEventListener("change", function () { update(true); }); });
    function button(parent, text, onclick) {
      var b = document.createElement("button");
      b.type = "button"; b.textContent = text;
      b.addEventListener("click", function () { onclick(); update(true); });
      parent.appendChild(b);
      return b;
    }
    var presets = $("start-presets");
    button(presets, "letzte 12 Monate", function () { setRange(k.window[1] - 11, k.window[1]); });
    button(presets, "ganze Periode", function () { setRange(0, n - 1); });
    for (var year = month(0)[0]; year <= month(n - 1)[0]; year++) {
      (function (y) {
        button(presets, String(y), function () { setRange((y - y0) * 12 - m0, (y - y0) * 12 - m0 + 11); });
      })(year);
    }
    var art = $("start-art"), body = $("start-gremium");
    k.arten.forEach(function (a) { art.add(new Option(a[1], a[0])); });
    function fillBodies() {
      body.textContent = "";
      body.add(new Option(st.art ? "alle " + kindLabel(st.art) : "erst eine Art wählen", ""));
      bodies.forEach(function (b) { if (st.art && b[2] === st.art) body.add(new Option(b[1], b[0])); });
      body.disabled = !st.art;
      art.value = st.art; body.value = st.body;
    }
    art.addEventListener("change", function () { st.art = art.value; st.body = ""; fillBodies(); update(true); });
    body.addEventListener("change", function () { st.body = body.value; update(true); });
    document.querySelectorAll('input[name="start-mode"]').forEach(function (radio) {
      radio.addEventListener("change", function () { st.mode = radio.value; update(true); });
    });
    var zoom = $("start-zoom");
    zoom.addEventListener("change", function () { svg.setAttribute("viewBox", zoom.value || full); update(false); });
    function zoomTo(sb) {
      for (var i = 0; i < zoom.options.length; i++) {
        if (zoom.options[i].dataset.sb === String(sb)) { zoom.selectedIndex = i; svg.setAttribute("viewBox", zoom.value); update(false); return; }
      }
    }

    /* --- Adresse ------------------------------------------------------------------------------ */
    function readHash() {
      (location.hash.slice(1) || "").split("&").forEach(function (part) {
        var kv = part.split("="), value = decodeURIComponent(kv[1] || "");
        if (kv[0] === "zeitraum") {
          var span = value.split("..").map(monthIndex);
          if (span.length === 2 && span.every(isFinite)) setRange(span[0], span[1]);
        } else if (kv[0] === "gremium") {
          if (value.indexOf("art:") === 0) { st.art = value.slice(4); st.body = ""; }
          else bodies.forEach(function (b) { if (b[0] === value && value) { st.art = b[2]; st.body = value; } });
        }
      });
    }
    function writeHash() {
      var hash = "#zeitraum=" + monthKey(st.von) + ".." + monthKey(st.bis);
      if (st.body) hash += "&gremium=" + encodeURIComponent(st.body);
      else if (st.art) hash += "&gremium=art:" + st.art;
      if (history.replaceState) history.replaceState(null, "", hash);
    }

    /* --- Zeichnen ----------------------------------------------------------------------------- */
    var layer = svg.querySelector(".start-points"), circles = [];
    var total = places.map(function (p, i) { return atPlace[i].length; });
    places.map(function (p, i) { return i; })
      .sort(function (a, b) { return total[b] - total[a]; })
      .forEach(function (i) {
        var c = document.createElementNS(NS, "circle");
        c.setAttribute("cx", places[i][0]); c.setAttribute("cy", places[i][1]);
        circles[i] = c;
        layer.appendChild(c);
      });
    var counts = new Int32Array(places.length), dcount = {}, selected = [], wanted = [];
    function okBody(b) { var x = bodies[b]; return (!st.art || x[2] === st.art) && (!st.body || x[0] === st.body); }
    /* SVG-Einheiten je Bildschirmpixel; die Karte ist mittig eingepasst (meet), also zählt die
       knappere Richtung */
    function scale() {
      var box = svg.viewBox.baseVal, r = svg.getBoundingClientRect();
      return Math.max(box.width / (r.width || 1), box.height / (r.height || 1));
    }
    /* Auf einer schmalen Karte (Handy) werden die Kreise bis auf die Hälfte kleiner, sonst
       verdeckten sie die Stadt; die Legende folgt mit (point_radius in startkarte.py ist k = 1) */
    function shrink() {
      var drawn = svg.viewBox.baseVal.width / scale();
      return Math.max(0.5, Math.min(1, drawn / 800));
    }
    function radius(count, s) { return (2.5 + 1.2 * Math.sqrt(count)) * shrink() * s; }
    /* Quantilklassen wie charts.classify (statistics.quantiles, method="inclusive") */
    function classify(values) {
      var sorted = values.slice().sort(function (a, b) { return a - b; });
      var distinct = sorted.filter(function (v, i) { return i === 0 || v !== sorted[i - 1]; }).length;
      var count = Math.min(5, distinct), bounds = [];
      for (var i = 1; i < count; i++) {
        var m = sorted.length - 1, j = Math.floor(i * m / count), delta = i * m - j * count;
        bounds.push((sorted[j] * (count - delta) + sorted[j + 1] * delta) / count);
      }
      return bounds;
    }
    function klass(bounds, value) { var c = 0; while (c < bounds.length && bounds[c] <= value) c++; return c; }
    /* wie count_label: ganze Zahlen ohne, sonst mit einer Nachkommastelle */
    function number(v) {
      if (Math.round(v) === v) return fmt(v);
      var tenths = Math.round(v * 10);
      return fmt(Math.floor(tenths / 10)) + "," + (tenths % 10);
    }
    var last = { ms: 0 };
    function update(final) {
      var t0 = performance.now();
      var oks = bodies.map(function (b, i) { return okBody(i); });
      counts.fill(0); dcount = {}; selected = []; var many = [];
      areas.forEach(function (a) { dcount[a.dataset.wb] = 0; });
      for (var i = 0; i < docs.length; i++) {
        var d = docs[i];
        if (d[0] < st.von || d[0] > st.bis || !oks[d[1]]) continue;
        selected.push(i);
        if (d[2] < 0) many.push(i);
        var seen = {};
        for (var j = 2; j < d.length; j++) {
          var w = d[j] < 0 ? -d[j] : places[d[j]][2];
          if (d[j] >= 0) counts[d[j]]++;
          if (!seen[w]) { seen[w] = 1; dcount[w] = (dcount[w] || 0) + 1; }
        }
      }
      var s = scale(), shown = 0, best = -1;
      svg.style.setProperty("--label", (11 * s).toFixed(1) + "px");  /* Namen in 11 px, bei jedem Ausschnitt */
      /* Namen nur, wo Platz ist: auf einer schmalen Karte erst im Ausschnitt eines Stadtbezirks */
      svg.classList.toggle("start-showlabels", svg.viewBox.baseVal.width / s >= 520 || !!zoom.value);
      document.querySelectorAll(".start-sizes circle").forEach(function (c) {
        if (!c.dataset.r) c.dataset.r = c.getAttribute("r");
        c.setAttribute("r", (c.dataset.r * shrink()).toFixed(1));
      });
      for (var p = 0; p < places.length; p++) {
        var c = circles[p];
        if (counts[p] && st.mode === "punkte") {
          c.setAttribute("r", radius(counts[p], s).toFixed(1));
          c.removeAttribute("display");
        } else c.setAttribute("display", "none");
        if (counts[p]) { shown++; if (best < 0 || counts[p] > counts[best]) best = p; }
      }
      svg.classList.toggle("start-plain", st.mode === "punkte");
      var values = areas.map(function (a) { return dcount[a.dataset.wb]; });
      var bounds = classify(values), topArea = null;
      areas.forEach(function (a, i) {
        a.setAttribute("class", "start-area q" + klass(bounds, values[i]));
        a.firstChild.textContent = "Wahlbezirk " + a.dataset.wb + " " + a.dataset.name + ": " + fmt(values[i]) + " Dokumente";
        if (!topArea || values[i] > dcount[topArea.dataset.wb]) topArea = a;
      });
      legendAreas(bounds);
      $("start-legend-points").hidden = st.mode !== "punkte";
      $("start-legend-areas").hidden = st.mode === "punkte";
      showRange();
      $("start-caption").textContent = (st.mode === "punkte" ? "Orte mit Dokumenten, " : "Dokumente je Wahlbezirk, ") + windowLabel() + ", " + bodyLabel();
      var line = $("start-many");
      line.hidden = !many.length;
      line.firstChild.textContent = fmt(many.length) + (many.length === 1 ? " Dokument" : " Dokumente") + " im Zeitraum " + (many.length === 1 ? "nennt" : "nennen") + " mehr als " + k.max_places + " Orte und " + (many.length === 1 ? "steht" : "stehen") + " darum nicht als Punkt. ";
      line.dataset.ids = many.join(" ");
      fillList();
      last.ms = performance.now() - t0;
      root.dataset.redrawMs = last.ms.toFixed(1);
      if (final) {
        writeHash();
        var text = fmt(selected.length) + " Dokumente an " + fmt(shown) + " Orten, " + windowLabel() + ", " + bodyLabel();
        if (best >= 0 && st.mode === "punkte") text += "; die meisten an " + places[best][4] + " im Wahlbezirk " + places[best][2] + " (" + fmt(counts[best]) + " Dokumente)";
        else if (topArea && dcount[topArea.dataset.wb]) text += "; die meisten im Wahlbezirk " + topArea.dataset.wb + " " + topArea.dataset.name + " (" + fmt(dcount[topArea.dataset.wb]) + " Dokumente)";
        $("start-status").textContent = text + ".";
      }
    }
    function legendAreas(bounds) {
      var items = $("start-legend-areas").querySelectorAll("li");
      var labels = !bounds.length ? ["alle"] : ["unter " + number(bounds[0])];
      for (var i = 1; i < bounds.length; i++) labels.push(number(bounds[i - 1]) + " bis unter " + number(bounds[i]));
      if (bounds.length) labels.push("ab " + number(bounds[bounds.length - 1]));
      items.forEach(function (li, i) { li.hidden = i >= labels.length; if (i < labels.length) li.lastChild.textContent = labels[i]; });
    }
    function fillList() {
      var order = [];
      for (var p = 0; p < places.length; p++) if (counts[p]) order.push(p);
      order.sort(function (a, b) { return counts[b] - counts[a] || (places[a][4] < places[b][4] ? -1 : 1); });
      var tbody = $("start-list-body");
      tbody.textContent = "";
      order.slice(0, 20).forEach(function (p) {
        var tr = tbody.insertRow(), cell = tr.insertCell(), b = document.createElement("button");
        b.type = "button"; b.className = "start-place"; b.textContent = places[p][4];
        b.addEventListener("click", function () { openPlace(p); });
        cell.appendChild(b);
        cell = tr.insertCell(); cell.className = "num"; cell.dataset.value = places[p][2]; cell.textContent = places[p][2];
        cell = tr.insertCell(); cell.className = "num"; cell.dataset.value = counts[p]; cell.textContent = fmt(counts[p]);
      });
    }

    /* --- Dialog ------------------------------------------------------------------------------- */
    function inView(ids) {
      var oks = bodies.map(function (b, i) { return okBody(i); });
      return ids.filter(function (i) { var d = docs[i]; return d[0] >= st.von && d[0] <= st.bis && oks[d[1]]; });
    }
    function phrase(count) {
      return fmt(count) + (count === 1 ? " Dokument" : " Dokumente") + ", " + windowLabel() + ", " + bodyLabel() + ", neueste zuerst.";
    }
    function districtName(w) { var a = byNumber[w]; return a ? a.dataset.name : ""; }
    function openPlace(p) {
      var place = places[p], ids = inView(atPlace[p]);
      var also = [];
      places.forEach(function (q, i) { if (i !== p && q[4] === place[4]) also.push(q[2]); });
      var text = phrase(ids.length) + " Lage: " + k.arts[place[3]] + "." + (also.length ? " Liegt auch in Wahlbezirk " + also.sort(function (a, b) { return a - b; }).join(", ") + "." : "");
      g.showDocumentList(ids, place[4] + ", Wahlbezirk " + place[2] + " " + districtName(place[2]), text,
        ["details.html#suche=" + encodeURIComponent(place[4].toLowerCase()), "Alle Zahlen zu diesem Begriff"]);
    }
    function openDistrict(w) {
      var ids = inView(atDistrict[w] || []);
      g.showDocumentList(ids, "Wahlbezirk " + w + " " + districtName(w), phrase(ids.length) + " Jedes Dokument nennt einen Ort aus dem Wörterbuch des Wahlbezirks.");
    }
    function openPlaces(list) {
      var dialog = $("docs"), ol = dialog.querySelector("ol");
      dialog.querySelectorAll(".extra").forEach(function (x) { x.remove(); });
      dialog.querySelector("h3").textContent = list.length + " Orte hier";
      dialog.querySelector("p").textContent = "Welcher Ort? Je Ort die Dokumente im Zeitraum.";
      ol.textContent = "";
      list.forEach(function (p) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button"; b.className = "start-place";
        b.textContent = places[p][4] + " (Wahlbezirk " + places[p][2] + ", " + fmt(counts[p]) + ")";
        b.addEventListener("click", function () { openPlace(p); });
        li.appendChild(b); ol.appendChild(li);
      });
      if (typeof dialog.showModal === "function") { if (!dialog.open) dialog.showModal(); } else dialog.setAttribute("open", "");
    }
    $("start-many").querySelector("button").addEventListener("click", function () {
      var ids = ($("start-many").dataset.ids || "").split(" ").filter(Boolean).map(Number);
      g.showDocumentList(ids, "Dokumente mit mehr als " + k.max_places + " Orten", phrase(ids.length));
    });

    /* --- Tippen und Zeigen: Abstandssuche im Umkreis von 24 Pixeln (WCAG 2.5.8) --------------- */
    function toUser(event) {
      var pt = svg.createSVGPoint(); pt.x = event.clientX; pt.y = event.clientY;
      return pt.matrixTransform(svg.getScreenCTM().inverse());
    }
    function near(event) {
      if (st.mode !== "punkte") return [];
      var u = toUser(event), limit = TAP * scale(), found = [];
      for (var p = 0; p < places.length; p++) {
        if (!counts[p]) continue;
        var dx = places[p][0] - u.x, dy = places[p][1] - u.y, dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= Math.max(limit, radius(counts[p], scale()))) found.push([dist, p]);
      }
      return found.sort(function (a, b) { return a[0] - b[0]; }).map(function (x) { return x[1]; });
    }
    function activate(area, list) {
      if (list.length === 1) openPlace(list[0]);
      else if (list.length > 1) openPlaces(list.slice(0, 12));
      else if (area && !zoom.value) zoomTo(area.dataset.sb);
      else if (area) openDistrict(area.dataset.wb);
    }
    svg.addEventListener("click", function (event) {
      var area = event.target.closest ? event.target.closest(".start-area") : null;
      activate(area, near(event));
    });
    areas.forEach(function (a) {
      a.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(a, []); }
      });
    });
    var tip = $("tooltip");
    svg.addEventListener("pointermove", function (event) {
      if (event.pointerType !== "mouse") return;
      var list = near(event);
      if (!list.length) { tip.hidden = true; return; }
      var p = list[0];
      tip.textContent = places[p][4] + ", Wahlbezirk " + places[p][2] + ": " + fmt(counts[p]) + (counts[p] === 1 ? " Dokument" : " Dokumente") + (list.length > 1 ? " (und " + (list.length - 1) + " weitere hier)" : "");
      tip.hidden = false;
      tip.style.left = (event.pageX + 14) + "px"; tip.style.top = (event.pageY + 14) + "px";
    });
    svg.addEventListener("pointerleave", function () { tip.hidden = true; });

    /* --- Monatsleiste aus der Monatsreihe ----------------------------------------------------- */
    var strip = $("start-strip"), top = Math.max.apply(null, k.months.concat([1])), bars = [];
    strip.setAttribute("viewBox", "0 0 " + n + " 20");
    k.months.forEach(function (count, i) {
      var r = document.createElementNS(NS, "rect");
      r.setAttribute("x", i + 0.1); r.setAttribute("width", 0.8);
      r.setAttribute("y", 20 - 20 * count / top); r.setAttribute("height", 20 * count / top);
      strip.appendChild(r); bars.push(r);
    });
    var drawStrip = function () { bars.forEach(function (r, i) { r.setAttribute("class", i >= st.von && i <= st.bis ? "in" : ""); }); };
    var plain = update;
    update = function (final) { plain(final); drawStrip(); };

    readHash();
    fillBodies();
    $("start-controls").hidden = false;
    window.addEventListener("resize", function () { update(false); });
    update(true);
    /* Messpunkt fuer docs/plans/startseite-messung.py: ein Neuzeichnen mit dem aktuellen Zustand */
    root.redraw = function () { update(false); return last.ms; };
  }
})();
