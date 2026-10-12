/* Option 02: Punkte und Zeilen des Periodenvergleichs an die Markierung des Rahmens hängen.
   Der Rahmen bedient .district und .point; .dpoint und diese Tabelle gehören diesem Abschnitt. */
(function () {
  "use strict";
  if (!window.georep) return;
  function toggle(element, id) {
    element.addEventListener("click", function () {
      window.georep.select(element.classList.contains("selected") ? null : id);
    });
    element.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); element.click(); }
    });
  }
  document.querySelectorAll("svg.deltas .dpoint").forEach(function (point) {
    toggle(point, point.dataset.id);
  });
  document.querySelectorAll("#perioden-tabelle tbody tr").forEach(function (row) {
    toggle(row, row.dataset.id);
  });
})();
