/* Light/dark theme for the public site and the staff dashboard.
   Loaded in <head> (not deferred) so the saved theme is applied before the
   page paints — no flash. With no saved choice the visitor's system setting
   decides. Old values ("forest", "ivory") were both light themes and are
   treated as light. Any element with id="themeToggle" becomes the switch;
   an <i id="themeIcon"> inside it shows the theme you will switch TO. */
(function () {
  var KEY = 'phf-theme';
  var root = document.documentElement;
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function saved() {
    try {
      var v = localStorage.getItem(KEY);
      return (v === 'light' || v === 'dark') ? v : null;
    } catch (e) { return null; }   // storage blocked
  }
  function systemTheme() { return media && media.matches ? 'dark' : 'light'; }
  function current() { return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'; }

  function apply(theme) {
    theme = theme === 'dark' ? 'dark' : 'light';
    root.setAttribute('data-theme', theme);
    root.setAttribute('data-bs-theme', theme);   // Bootstrap 5.3 colour mode
    var icon = document.getElementById('themeIcon');
    if (icon) icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    var btn = document.getElementById('themeToggle');
    if (btn) {
      var label = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
      btn.title = label;
      btn.setAttribute('aria-label', label);
      btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }
  }

  function toggle() {
    var next = current() === 'dark' ? 'light' : 'dark';
    apply(next);
    try { localStorage.setItem(KEY, next); } catch (e) { /* storage blocked */ }
  }

  apply(saved() || systemTheme());

  document.addEventListener('DOMContentLoaded', function () {
    apply(current());   // sync the button now that it exists
    var btn = document.getElementById('themeToggle');
    if (btn) btn.addEventListener('click', toggle);
  });

  // Follow system changes until the visitor picks a theme themselves.
  if (media && media.addEventListener) {
    media.addEventListener('change', function (e) { if (!saved()) apply(e.matches ? 'dark' : 'light'); });
  }

  // Another tab changed the theme.
  window.addEventListener('storage', function (e) { if (e.key === KEY && saved()) apply(saved()); });

  window.phfTheme = { apply: apply, toggle: toggle, current: current };
})();
