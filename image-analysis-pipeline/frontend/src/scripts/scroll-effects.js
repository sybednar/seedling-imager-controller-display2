/* Scroll effects, shared by the landing page and the docs.
 *
 * Inlined in <head> (landing: src/pages/index.astro; docs: `head` in astro.config.mjs)
 * so the hidden starting state exists before first paint, with no flash of visible content.
 *
 *   1. Reveal on scroll: blocks fade + rise as they enter the viewport. Blocks that
 *      appear at the same moment are staggered.
 *   2. Reading-progress bar along the top of docs pages.
 *   3. Smooth scrolling for anchor links (sidebar "On this page", nav jumps).
 *
 * Reveal + smooth scroll are skipped for prefers-reduced-motion, and content is only ever
 * hidden by this script, so no-JS visitors and print see everything. The progress bar stays
 * for reduced-motion users: it is a position indicator, not motion.
 *
 * To remove all of it: delete this file and its two references. Editing it while
 * `npm run dev` is running needs a dev-server restart (astro.config.mjs reads it at start).
 */
(function () {
  var root = document.documentElement;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var canReveal = !reduce && 'IntersectionObserver' in window;

  // What reveals. Landing: hero copy + chart, section heads, cards, footer.
  // Docs: steps, callouts, boxed sections, code blocks, headings, figures, pager.
  // Only the outermost match animates, so nested blocks never animate twice.
  var SEL = [
    '.hero-copy > *', '.chart-panel', '.head', '.grid3 > .card', '.grid2 > .card',
    '.doc-grid > .doc-card', '.site-foot',
    'section.step', '.sl-steps > li', '.starlight-aside', '.doc-box', '.compare', '.placeholder-shot',
    '.sl-markdown-content .expressive-code', '.sl-markdown-content .sl-heading-wrapper',
    '.pagination-links a',
  ].join(',');
  var TOP = ':is(' + SEL + '):not(:is(' + SEL + ') *)';

  var EASE = 'cubic-bezier(0.22, 0.7, 0.2, 1)';
  var DURATION = 600; // ms
  var STAGGER = 70; // ms between blocks revealed together
  var MAX_STEPS = 4; // stagger cap, so a long batch never lags

  var css =
    '@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }' +
    '.scroll-progress { position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 100;' +
    ' background: var(--moss, #2F6B3F); transform-origin: 0 50%; transform: scaleX(0); pointer-events: none; }' +
    '@media print { .scroll-progress { display: none; } }';

  if (canReveal) {
    root.classList.add('reveal-on');
    css +=
      'html.reveal-on ' + TOP + ':not(.rv) { opacity: 0; transform: translateY(16px); }' +
      'html.reveal-on ' + TOP + '.rv-anim {' +
      ' transition: opacity ' + DURATION + 'ms ' + EASE + ' var(--rv-delay, 0ms),' +
      ' transform ' + DURATION + 'ms ' + EASE + ' var(--rv-delay, 0ms); }' +
      '@media print { html.reveal-on ' + TOP + ':not(.rv) { opacity: 1 !important; transform: none !important; } }';
  }

  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  function reveal(el, delay) {
    el.style.setProperty('--rv-delay', delay + 'ms');
    el.classList.add('rv-anim', 'rv');
    // Once the transition has played, drop it so the element's own hover transitions return.
    setTimeout(function () {
      el.classList.remove('rv-anim');
      el.style.removeProperty('--rv-delay');
    }, DURATION + delay + 60);
  }

  function initReveal() {
    var io = new IntersectionObserver(
      function (entries) {
        var n = 0;
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          io.unobserve(entry.target);
          reveal(entry.target, Math.min(n++, MAX_STEPS) * STAGGER);
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -6% 0px' }
    );
    document.querySelectorAll(TOP).forEach(function (el) { io.observe(el); });
  }

  function initProgress() {
    if (!document.querySelector('.sl-markdown-content')) return; // docs pages only
    var bar = document.createElement('div');
    bar.className = 'scroll-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    var queued = false;
    function update() {
      queued = false;
      var max = root.scrollHeight - window.innerHeight;
      bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, window.scrollY / max) : 0) + ')';
    }
    window.addEventListener('scroll', function () {
      if (!queued) { queued = true; requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener('resize', update);
    update();
  }

  function init() {
    if (canReveal) initReveal();
    initProgress();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
