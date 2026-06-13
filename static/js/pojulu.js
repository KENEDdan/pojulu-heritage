/* ═══════════════════════════════════════
   POJULU HERITAGE FOUNDATION — pojulu.js
═══════════════════════════════════════ */

// ── THEME ─────────────────────────────────────
function toggleTheme() {
  const html = document.documentElement;
  const next = html.getAttribute('data-theme') === 'forest' ? 'ivory' : 'forest';
  applyTheme(next);
  localStorage.setItem('phf-theme', next);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('themeIcon');
  if (icon) icon.className = theme === 'ivory' ? 'bi bi-moon-stars-fill' : 'bi bi-sun-fill';
}

// ── LANGUAGE ──────────────────────────────────
const LANG_LABELS = { en: 'EN', ar: 'AR' };

function setLang(lang) {
  const isAr = lang === 'ar';
  document.documentElement.setAttribute('lang', lang);
  document.documentElement.setAttribute('dir', isAr ? 'rtl' : 'ltr');

  // Swap all data-en / data-ar text
  document.querySelectorAll('[data-en]').forEach(el => {
    const val = el.getAttribute('data-' + lang) || el.getAttribute('data-en');
    if (val) el.innerHTML = val;
  });

  // Swap placeholder attributes
  document.querySelectorAll('[data-placeholder-en]').forEach(el => {
    el.placeholder = el.getAttribute('data-placeholder-' + lang) || el.getAttribute('data-placeholder-en');
  });

  // Update dropdown button label
  const label = document.getElementById('langLabel');
  if (label) label.textContent = LANG_LABELS[lang] || 'EN';

  localStorage.setItem('phf-lang', lang);
}

// ── SEARCH OVERLAY ────────────────────────────
function openSearch() {
  const overlay = document.getElementById('searchOverlay');
  if (!overlay) return;
  overlay.classList.add('active');
  setTimeout(() => overlay.querySelector('input')?.focus(), 100);
}

function closeSearch() {
  document.getElementById('searchOverlay')?.classList.remove('active');
}

// Close on Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeSearch();
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); openSearch(); }
});

// Close overlay clicking outside input
document.getElementById('searchOverlay')?.addEventListener('click', function(e) {
  if (e.target === this) closeSearch();
});

// ── COUNTERS ──────────────────────────────────
function animateCounter(el) {
  const target = parseInt(el.dataset.target || el.textContent.replace(/\D/g, ''), 10);
  if (!target) return;
  let cur = 0;
  const step = Math.max(1, Math.ceil(target / 60));
  const t = setInterval(() => {
    cur = Math.min(cur + step, target);
    el.textContent = cur.toLocaleString();
    if (cur >= target) clearInterval(t);
  }, 20);
}

// ── TABS ──────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.phf-tab[data-target]').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.closest('[data-tab-group]') || btn.parentElement;
      group.querySelectorAll('.phf-tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.phf-tab-pane').forEach(p => { if (group.contains(btn) || document.getElementById(btn.dataset.target)) p.style.display = 'none'; });
      btn.classList.add('active');
      const pane = document.getElementById(btn.dataset.target);
      if (pane) pane.style.display = 'block';
    });
  });
}

// ── AUTO SUBMIT SELECTS ────────────────────────
function initAutoSubmit() {
  document.querySelectorAll('.phf-auto-submit').forEach(el => {
    el.addEventListener('change', () => el.closest('form')?.submit());
  });
}

// ── INIT ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Restore theme
  applyTheme(localStorage.getItem('phf-theme') || 'forest');

  // Restore language
  const savedLang = localStorage.getItem('phf-lang') || 'en';
  if (savedLang !== 'en') setLang(savedLang);

  // Animated counters
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { animateCounter(e.target); obs.unobserve(e.target); } });
  }, { threshold: 0.4 });
  document.querySelectorAll('[data-counter]').forEach(el => obs.observe(el));

  initTabs();
  initAutoSubmit();

  // Navbar scroll shadow
  window.addEventListener('scroll', () => {
    document.getElementById('mainNav')?.classList.toggle('phf-nav-scrolled', window.scrollY > 50);
  });

  // Auto-dismiss alerts
  setTimeout(() => {
    document.querySelectorAll('.alert-dismissible .btn-close').forEach(btn => btn.click());
  }, 5000);
});