/* Vorhaben 15, akteure.html: der Umschalter der Matrix „Wer mit wem". Ohne JavaScript stehen beide
   Matrizen untereinander und der Umschalter bleibt verborgen; mit JavaScript zeigt er eine. Kein
   fieldset.switcher des Rahmens: der tauscht Klassen und Zahlen, hier wechselt die ganze Tabelle. */
(function () {
  "use strict";
  var fieldset = document.getElementById("matrix-ebene");
  if (!fieldset) return;
  var radios = Array.prototype.slice.call(fieldset.querySelectorAll('input[type="radio"]'));
  var blocks = Array.prototype.slice.call(document.querySelectorAll("[data-matrix]"));
  if (radios.length < 2) return;
  function show(value) {
    blocks.forEach(function (block) { block.hidden = block.getAttribute("data-matrix") !== value; });
  }
  radios.forEach(function (radio) {
    radio.addEventListener("change", function () { if (radio.checked) show(radio.value); });
  });
  var checked = radios.filter(function (radio) { return radio.checked; })[0] || radios[0];
  show(checked.value);
  fieldset.hidden = false;
})();
