/* Enhanced Login: small helpers for /auth/authorize.
   - after "Login aborted" (SSO redirect skipped) it selects the local account
     automatically, in any language (the integration itself only detects "Login aborted")
   - hides that intermediate step so it does not flash
   - adds a "Back" link on the local login when it was opened from the SSO welcome page
   Without this script everything stays usable; only the intermediate step is visible. */
(function () {
  "use strict";
  var root = document.documentElement;
  if (!document.querySelector("ha-authorize") && location.pathname !== "/auth/authorize") return;

  var done = false;
  var lastClick = 0;
  var started = Date.now();
  root.classList.add("el-await");

  function release() {
    done = true;
    root.classList.remove("el-await");
  }

  function update() {
    if (done) return;
    var flow = document.querySelector("ha-auth-flow");
    if (!flow) return;

    // Schon ein Eingabeformular (Benutzername/Passwort, MFA ...) -> nichts zu tun
    if (flow.querySelector("ha-auth-form, input")) return release();

    var picker = document.querySelector("ha-pick-auth-provider");
    var item = picker && picker.shadowRoot && picker.shadowRoot.querySelector("ha-list-item");
    var abortScreen = flow.querySelector(".action ha-button");
    if (abortScreen && item) {
      if (Date.now() - lastClick > 800) {
        lastClick = Date.now();
        item.click();
      }
      // Das Formular erscheint beim naechsten Durchlauf; bis dahin bleibt der Schritt verborgen
      return;
    }
    if (abortScreen && !item && Date.now() - started > 1200) release();
  }

  var observer = new MutationObserver(update);
  observer.observe(document.body, { childList: true, subtree: true });
  update();

  // Notanker: nie dauerhaft verstecken
  setTimeout(function () {
    release();
    observer.disconnect();
  }, 2500);
})();

/* Back link: after choosing the local account (skip_oidc_redirect), return to the choice page */
(function () {
  "use strict";
  if (location.pathname !== "/auth/authorize") return;
  if (!/[?&]skip_oidc_redirect=true(&|$)/.test(location.search)) return;

  function add() {
    var content = document.querySelector(".content");
    if (!content || content.querySelector(".el-back")) return !!content;
    var query = location.search
      .replace(/([?&])skip_oidc_redirect=true&?/, "$1")
      .replace(/[?&]$/, "");
    var original = location.origin + location.pathname + query;
    var link = document.createElement("a");
    link.className = "dl-back";
    link.href = "/auth/oidc/welcome?redirect_uri=" + encodeURIComponent(btoa(original));
    var lang = (document.documentElement.lang || navigator.language || "en").slice(0, 2).toLowerCase();
    link.textContent = lang === "de" ? "Zurück" : "Back";
    content.appendChild(link);
    return true;
  }

  if (!add()) document.addEventListener("DOMContentLoaded", add);
})();
