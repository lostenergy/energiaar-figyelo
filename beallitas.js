// ---------------------------------------------------------------------------
// EZT AZ EGY SORT KELL ÁTÍRNI: a nézegethető változat címe.
// Példa:  const ALKALMAZAS = "https://open-energia.streamlit.app";
// ---------------------------------------------------------------------------
const ALKALMAZAS = "";
// ---------------------------------------------------------------------------

// Innentől nincs teendő: a keretet és a gombok címét ez állítja be.
(function () {
  const cim = (ALKALMAZAS || "").replace(/\/+$/, "");
  document.addEventListener("DOMContentLoaded", function () {
    const hely = document.getElementById("keret");
    const gomb = document.getElementById("kulon");
    if (!cim) {
      if (gomb) gomb.style.display = "none";
      return;
    }
    if (gomb) gomb.href = cim;
    if (hely) {
      const keret = document.createElement("iframe");
      keret.src = cim + "/?embed=true&embed_options=light_theme";
      keret.title = "Energiaár-figyelő";
      hely.replaceChildren(keret);
    }
  });
})();
