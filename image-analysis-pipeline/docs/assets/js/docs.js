/* Doc pages: number badges on step headings, date lines on changelog
   entries, and a section rail that grows down the page as you read.
   Without JS the pages still read top to bottom as plain markdown.    */
(function () {
  var main = document.querySelector('.doc-body .doc-main');
  if (!main) return;

  // Wrap a leading pattern in the heading's first text node with a span.
  function badge(h, re, cls, keep) {
    var node = h.firstChild;
    if (!node || node.nodeType !== 3) return;
    var m = node.nodeValue.match(re);
    if (!m) return;
    var span = document.createElement('span');
    span.className = cls;
    if (keep) {
      // keep the word for screen readers; the badge shows only the number
      var hidden = document.createElement('span');
      hidden.className = 'visually-hidden';
      hidden.textContent = keep;
      span.appendChild(hidden);
    }
    span.appendChild(document.createTextNode(m[1]));
    node.nodeValue = node.nodeValue.slice(m[0].length);
    h.insertBefore(span, node);
  }

  var headings = main.querySelectorAll('h1, h2, h3');
  var railItems = [];
  var title = main.querySelector('h1');

  headings.forEach(function (h) {
    var label = h.textContent.trim();
    if (h.tagName === 'H2' || h.tagName === 'H3') {
      badge(h, /^Step (\d+):\s*/, 'step-num', 'Step ');
      badge(h, /^(\d+)\.\s+/, 'step-num');
    }
    if (h.tagName === 'H2') badge(h, /^(\d{4}-\d{2}-\d{2}):\s*/, 'date-tag');

    if (!h.id || h === title) return;
    if (h.tagName === 'H1') railItems.push({ el: h, label: label, kind: 'group' });
    else if (h.tagName === 'H2') railItems.push({ el: h, label: label, kind: 'item' });
  });

  // Pages with OS groups (install) nest their h2s under each group.
  var grouped = railItems.some(function (i) { return i.kind === 'group'; });
  if (railItems.length < 3) return;

  var rail = document.createElement('nav');
  rail.className = 'doc-rail';
  rail.setAttribute('aria-label', 'On this page');
  var heading = document.createElement('p');
  heading.className = 'rail-title';
  heading.textContent = 'On this page';
  var list = document.createElement('ol');
  var grow = document.createElement('span');
  grow.className = 'rail-grow';
  grow.setAttribute('aria-hidden', 'true');
  list.appendChild(grow);

  var inGroup = false;
  railItems.forEach(function (item) {
    var li = document.createElement('li');
    if (item.kind === 'group') { li.className = 'group'; inGroup = true; }
    else if (grouped && inGroup) li.className = 'sub';
    var a = document.createElement('a');
    a.href = '#' + item.el.id;
    a.textContent = item.label;
    li.appendChild(a);
    list.appendChild(li);
    item.link = a;
  });

  rail.appendChild(heading);
  rail.appendChild(list);
  var wrap = main.parentNode;
  wrap.insertBefore(rail, main);
  wrap.classList.add('has-rail');
  document.body.classList.add('has-rail');

  // Highlight the section currently under the navbar and grow the root to it.
  var offset = 110;
  var current = null;
  function update() {
    var active = null;
    for (var i = 0; i < railItems.length; i++) {
      if (railItems[i].el.getBoundingClientRect().top - offset <= 0) active = railItems[i];
      else break;
    }
    if (active === current) return;
    current = active;
    var passed = true;
    railItems.forEach(function (item) {
      item.link.classList.toggle('active', item === active);
      item.link.classList.toggle('passed', passed && !!active);
      if (item === active) passed = false;
      if (item === active) item.link.setAttribute('aria-current', 'location');
      else item.link.removeAttribute('aria-current');
    });
    if (active) {
      var li = active.link.parentNode;
      grow.style.height = (li.offsetTop + li.offsetHeight / 2) + 'px';
      // keep the active node in view when the rail is taller than the window
      var top = li.offsetTop + list.offsetTop;
      if (top < rail.scrollTop + 40 || top + li.offsetHeight > rail.scrollTop + rail.clientHeight - 40) {
        rail.scrollTop = top - rail.clientHeight / 2;
      }
    } else {
      grow.style.height = '0px';
    }
  }

  var ticking = false;
  window.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () { ticking = false; update(); });
  }, { passive: true });
  window.addEventListener('resize', function () { current = undefined; update(); });
  update();
})();
