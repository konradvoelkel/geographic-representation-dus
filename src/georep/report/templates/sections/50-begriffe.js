/* Punkt 49: die Begriffe eines Wahlbezirks stehen in data/begriffe.json und nicht in der Seite.
   334 KB in 41 zugeklappten <details> waren der groesste Posten der Seite
   (docs/seitengroesse-2026-10.md, Paragraf 4); geholt wird beim ersten Aufklappen, einmal fuer
   alle Wahlbezirke (georep.loadJson haelt das Versprechen). Scheitert es -- aus dem Dateisystem
   geoeffnet verbietet der Browser fetch --, steht derselbe Satz da wie im Dokumentdialog. */
(function () {
  "use strict";
  var FILE = "data/begriffe.json";
  /* Tausender wie format_de: schmales Leerzeichen, damit eine nachgeladene Zahl aussieht wie eine
     gesetzte. Begriffe je Wahlbezirk bleiben meist dreistellig, aber nicht in jeder Stadt. */
  function num(value) {
    return String(value).replace(/\B(?=(\d{3})+$)/g, "\u202f");
  }
  function list(terms) {
    var ol = document.createElement("ol");
    ol.className = "terms";
    terms.forEach(function (entry) {
      var li = document.createElement("li");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "term";
      button.textContent = entry[0];
      var count = document.createElement("span");
      count.className = "count";
      count.textContent = num(entry[1]);
      li.appendChild(button);
      li.appendChild(document.createTextNode(" "));
      li.appendChild(count);
      ol.appendChild(li);
    });
    return ol;
  }
  document.querySelectorAll("details[data-terms]").forEach(function (box) {
    var slot = box.querySelector("p.note");
    var started = false;
    box.addEventListener("toggle", function () {
      if (!box.open || started || !slot) return;
      started = true;
      slot.textContent = "Lade " + FILE + " …";
      window.georep.loadJson(FILE).then(function (data) {
        var terms = data.districts[box.dataset.terms] || [];
        slot.replaceWith(list(terms));
      }).catch(function () {
        /* Vergessen heisst: ein zweites Aufklappen darf es noch einmal versuchen (ein Webserver
           kann zwischendurch anlaufen, und ein 404 ist kein Dauerzustand). */
        window.georep.forget(FILE);
        started = false;
        slot.textContent = window.georep.offlineNote("Die Begriffsliste", FILE);
      });
    });
  });
})();
