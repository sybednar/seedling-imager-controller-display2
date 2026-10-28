/* Landing page scroll effects: sections fade up as they enter view,
   a progress line grows along the header, and the nav marks the
   section you're in. Without JS (or with reduced motion) the page
   renders fully visible and static.                                  */
(function () {
  var root = document.documentElement;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- reveal on scroll ----
  var groups = [
    '.section-head',
    '.apps-grid .app-card',
    '.whats-new .entry',
    '.whats-new .back-link',
    '.docs-grid .doc-card'
  ];

  if (!reduce && 'IntersectionObserver' in window) {
    root.classList.add('js-reveal');

    groups.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el, i) {
        el.classList.add('reveal');
        // stagger siblings in a grid/list so they arrive one after another
        el.style.transitionDelay = Math.min(i, 5) * 80 + 'ms';
      });
    });

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-visible');
        io.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });

    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
  }

  // ---- header progress line + active nav link ----
  var bar = document.querySelector('header.site .scroll-progress');
  var links = Array.prototype.slice.call(document.querySelectorAll('nav.top a[href^="#"]'));
  var sections = links.map(function (a) { return document.querySelector(a.getAttribute('href')); });
  var ticking = false;

  function update() {
    ticking = false;
    var max = root.scrollHeight - window.innerHeight;
    if (bar) bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(window.scrollY / max, 1) : 0) + ')';

    // the current section is the last one whose top has passed under the header
    var current = -1;
    var line = 100;
    sections.forEach(function (s, i) {
      if (s && s.getBoundingClientRect().top <= line) current = i;
    });
    // at the very bottom the last section may be too short to reach the line
    if (max > 0 && window.scrollY >= max - 2) current = sections.length - 1;

    links.forEach(function (a, i) {
      if (i === current) a.setAttribute('aria-current', 'true');
      else a.removeAttribute('aria-current');
    });
  }

  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; window.requestAnimationFrame(update); }
  }, { passive: true });
  window.addEventListener('resize', update);
  update();
})();
