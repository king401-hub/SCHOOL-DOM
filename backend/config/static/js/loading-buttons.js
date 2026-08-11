/**
 * SchoolDom shared loading-button utility.
 *
 * Adds an inline spinner + disabled state to submit buttons/inputs the
 * instant a <form> is submitted (classic full-page POST/GET navigations,
 * the vast majority of buttons across the Control Panel / Django admin,
 * the superadmin dashboard, and auth pages), so users get feedback instead
 * of a form that appears to do nothing until the next page loads.
 *
 * Framework-free: no jQuery/Alpine/htmx dependency. Safe to load standalone
 * on any page. Where htmx is also present (config/templates/base.html),
 * the inline htmx-config script additionally calls window.SDLoadingButtons
 * directly from its own event handlers for button/link-triggered requests.
 *
 * Opt out per-form or per-button with a `data-sd-no-spinner` attribute.
 */
(function () {
  if (window.__sdLoadingButtonsInit) return;
  window.__sdLoadingButtonsInit = true;

  var STYLE_ID = "sd-loading-buttons-style";
  var SAFETY_TIMEOUT_MS = 15000;
  var SPIN_SVG =
    '<svg class="sd-btn-spinner" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-opacity="0.25"/>' +
    '<path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>';

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent =
      ".sd-btn-spinner{animation:sd-btn-spin .7s linear infinite;vertical-align:-2px;margin-right:6px;display:inline-block}" +
      "@keyframes sd-btn-spin{to{transform:rotate(360deg)}}" +
      "[data-sd-loading]{pointer-events:none;opacity:.75;cursor:not-allowed}";
    document.head.appendChild(style);
  }

  function shouldSkip(submitter, form) {
    if (!submitter) return true;
    if (submitter.tagName !== "BUTTON" && submitter.tagName !== "INPUT") return true;
    if (submitter.type === "reset") return true;
    if (submitter.dataset.sdNoSpinner !== undefined) return true;
    if (form && form.dataset.sdNoSpinner !== undefined) return true;
    return false;
  }

  function setLoading(submitter) {
    if (submitter.dataset.sdLoading === "1") return;
    submitter.dataset.sdLoading = "1";
    submitter.setAttribute("data-sd-loading", "");
    submitter.disabled = true;
    if (submitter.tagName === "BUTTON") {
      submitter.dataset.sdOriginalHtml = submitter.innerHTML;
      submitter.innerHTML = SPIN_SVG + (submitter.dataset.sdLoadingText || submitter.textContent.trim());
    } else {
      submitter.dataset.sdOriginalValue = submitter.value;
      submitter.value = submitter.dataset.sdLoadingText || (submitter.value + "…");
    }
    submitter.dataset.sdTimeoutId = window.setTimeout(function () { restore(submitter); }, SAFETY_TIMEOUT_MS);
  }

  function restore(submitter) {
    if (submitter.dataset.sdLoading !== "1") return;
    window.clearTimeout(Number(submitter.dataset.sdTimeoutId));
    delete submitter.dataset.sdLoading;
    submitter.removeAttribute("data-sd-loading");
    submitter.disabled = false;
    if (submitter.tagName === "BUTTON" && submitter.dataset.sdOriginalHtml !== undefined) {
      submitter.innerHTML = submitter.dataset.sdOriginalHtml;
    } else if (submitter.dataset.sdOriginalValue !== undefined) {
      submitter.value = submitter.dataset.sdOriginalValue;
    }
  }

  document.addEventListener("submit", function (evt) {
    var form = evt.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.sdNoSpinner !== undefined) return;
    var submitter = evt.submitter;
    if (shouldSkip(submitter, form)) return;
    injectStyle();
    setLoading(submitter);
  }, true);

  window.addEventListener("pageshow", function () {
    document.querySelectorAll("[data-sd-loading]").forEach(restore);
  });

  window.SDLoadingButtons = { setLoading: setLoading, restore: restore, injectStyle: injectStyle };
})();
