/* Option 03: ein Klick auf einen Punkt der partiellen Streudiagramme markiert den Wahlbezirk
   ueberall auf der Seite. Die Punkte tragen nur data-id, darum bindet das Basis-Skript sie nicht. */
document.querySelectorAll(".avp-point").forEach(function (point) {
  point.addEventListener("click", function () {
    var id = point.dataset.id;
    window.georep.select(point.classList.contains("selected") ? null : id);
  });
  point.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); point.click(); }
  });
});
