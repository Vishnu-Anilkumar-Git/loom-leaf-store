/* LOOM&LEAF staff dashboard interactions. */
(function () {
  "use strict";

  // Mobile navigation toggle.
  var toggle = document.querySelector("[data-dash-nav-toggle]");
  var nav = document.getElementById("dash-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var collapsed = nav.classList.toggle("is-collapsed");
      toggle.setAttribute("aria-expanded", String(!collapsed));
    });
  }

  // Confirmation before destructive actions (feature-detectable, no alerts as UX elsewhere).
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var message = form.getAttribute("data-confirm");
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });

  // Archive toggles on list rows.
  document.querySelectorAll("button[data-archive-confirm]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      var message = button.getAttribute("data-archive-confirm");
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
})();
