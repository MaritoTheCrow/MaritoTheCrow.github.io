/* Merval Analysis hub: instant search + filters, URL state, report results from merval.json.
   The full directory is rendered by Jekyll, so the page is readable without JavaScript. */
(function () {
  'use strict';

  var cfgEl = document.getElementById('mv-config');
  var controls = document.getElementById('mv-controls');
  if (!cfgEl || !controls) { return; }

  var cfg = JSON.parse(cfgEl.textContent);
  var L = cfg.L;
  var KEYS = ['sector', 'status', 'type', 'format', 'access'];
  var MAX_ROWS = 300;
  var SVG_NS = 'http://www.w3.org/2000/svg';

  var $ = function (id) { return document.getElementById(id); };
  var q = $('mv-q');
  var sel = {};
  KEYS.forEach(function (k) { sel[k] = $('mv-' + k); });
  var clearBtn = $('mv-clear');
  var countEl = $('mv-count');
  var emptyEl = $('mv-empty');
  var resultsBox = $('mv-report-results');
  var resultsTable = $('mv-report-table');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.mv-card'));
  var groups = Array.prototype.slice.call(document.querySelectorAll('.mv-group'));
  var data = null;
  var loading = false;
  var loadFailed = false;

  function norm(s) {
    s = (s == null ? '' : String(s)).toLowerCase();
    return s.normalize ? s.normalize('NFD').replace(/[̀-ͯ]/g, '') : s;
  }

  cards.forEach(function (c) {
    c._hay = norm(c.getAttribute('data-ticker') + ' ' + c.getAttribute('data-name'));
    c._ticker = c.getAttribute('data-ticker').toUpperCase();
  });

  // ---------- number formatting: 1.234,5 (period thousands, comma decimal, one decimal) ----------
  function fmt1(n) {
    var parts = (Math.round(n * 10) / 10).toFixed(1).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return parts[0] + ',' + parts[1];
  }
  function fmtSize(bytes) {
    if (!bytes) { return '—'; }
    return bytes >= 1048576 ? fmt1(bytes / 1048576) + ' MB' : fmt1(bytes / 1024) + ' KB';
  }

  // ---------- state <-> URL ----------
  function readURL() {
    var p;
    try { p = new URLSearchParams(window.location.search); } catch (e) { return; }
    q.value = p.get('q') || '';
    KEYS.forEach(function (k) {
      var v = p.get(k) || '';
      sel[k].value = v;
      if (sel[k].value !== v) { sel[k].value = ''; }
    });
  }

  function writeURL() {
    var p = new URLSearchParams();
    if (q.value.trim()) { p.set('q', q.value.trim()); }
    KEYS.forEach(function (k) { if (sel[k].value) { p.set(k, sel[k].value); } });
    var s = p.toString();
    try {
      window.history.replaceState(null, '', window.location.pathname + (s ? '?' + s : '') + window.location.hash);
    } catch (e) { /* file:// or sandboxed: ignore */ }
  }

  function state() {
    return {
      q: norm(q.value.trim()),
      sector: sel.sector.value,
      status: sel.status.value,
      type: sel.type.value,
      format: sel.format.value,
      access: sel.access.value
    };
  }

  function reportFiltersActive(st) { return !!(st.type || st.format || st.access); }

  function cardMatches(c, st) {
    if (st.q && c._hay.indexOf(st.q) === -1) { return false; }
    if (st.sector && c.getAttribute('data-sector') !== st.sector) { return false; }
    if (st.status && c.getAttribute('data-status') !== st.status) { return false; }
    return true;
  }

  function reportMatches(r, st) {
    if (r.pending) { return false; }
    if (st.type && r.type !== st.type) { return false; }
    if (st.format && r.format !== st.format) { return false; }
    if (st.access && r.access !== st.access) { return false; }
    return true;
  }

  // Fallback while merval.json is loading: any-of match on the data-* attributes of the card.
  function cardHasReportFallback(c, st) {
    function has(attr, v) { return !v || (' ' + c.getAttribute(attr) + ' ').indexOf(' ' + v + ' ') !== -1; }
    return has('data-types', st.type) && has('data-formats', st.format) && has('data-access', st.access);
  }

  function load() {
    if (data || loading || loadFailed) { return; }
    loading = true;
    fetch(cfg.json, { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
      .then(function (j) { data = j; loading = false; apply(); })
      .catch(function () { loading = false; loadFailed = true; apply(); });
  }

  // ---------- DOM helpers for the report results table ----------
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text != null) { n.textContent = text; }
    return n;
  }
  function icon(id, cls) {
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', 'icon' + (cls ? ' ' + cls : ''));
    svg.setAttribute('aria-hidden', 'true');
    var use = document.createElementNS(SVG_NS, 'use');
    use.setAttribute('href', '#ico-' + id);
    svg.appendChild(use);
    return svg;
  }
  function pick(obj) { return obj ? (obj[cfg.lang] || obj.en || '') : ''; }

  function accessButton(r) {
    var title = pick(r.title);
    var a;
    if (r.pending) {
      a = el('span', 'btn btn--sm btn--disabled', L.access.pending);
      a.setAttribute('aria-disabled', 'true');
      return a;
    }
    if (r.access === 'free' && r.url) {
      a = el('a', 'btn btn--sm btn--primary');
      a.href = r.url;
      a.setAttribute('download', '');
      a.appendChild(icon('download'));
      a.appendChild(el('span', null, L.access.download));
      a.appendChild(el('span', 'visually-hidden', ' — ' + title + ' (' + r.format.toUpperCase() + ')'));
      return a;
    }
    if (r.access === 'contact') {
      a = el('a', 'btn btn--sm btn--secondary js-access');
      var subject = '[MCB Advisor] ' + L.access.request + ': ' + r.id;
      var body = L.modal.report + ': ' + title + ' (' + r.id + ')\n\n' + L.modal.name + ':\n' + L.modal.company + ':';
      a.href = 'mailto:' + cfg.contact + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
      a.setAttribute('data-access', 'contact');
      a.appendChild(icon('mail'));
      a.appendChild(el('span', null, L.access.request));
    } else {
      a = el('a', 'btn btn--sm btn--outline js-access');
      a.href = cfg.subscribe + '?report=' + encodeURIComponent(r.id) + '&ticker=' + encodeURIComponent(r.ticker);
      a.setAttribute('data-access', 'subscriber');
      a.appendChild(icon('lock'));
      a.appendChild(el('span', null, L.access.subscribers_only));
    }
    a.setAttribute('data-report-id', r.id);
    a.setAttribute('data-report-title', title);
    a.appendChild(el('span', 'visually-hidden', ' — ' + title));
    return a;
  }

  function reportRow(r) {
    var tr = el('tr', 'rt-row');
    function td(cls, label) {
      var c = el('td', cls);
      c.setAttribute('data-label', label);
      tr.appendChild(c);
      return c;
    }
    td('rt-date', L.table.date).textContent = r.date;
    var tk = td('rt-ticker', L.table.ticker);
    var link = el('a', null, r.ticker);
    link.href = cfg.ticker_base + r.ticker.toLowerCase() + '/';
    tk.appendChild(link);
    td('rt-type', L.table.type).appendChild(el('span', 'badge badge--type', L.types[r.type] || r.type));
    var tt = td('rt-title', L.table.title);
    tt.appendChild(el('span', 'rt-title__text', pick(r.title)));
    var sum = pick(r.summary);
    if (sum) { tt.appendChild(el('span', 'rt-title__sum', sum)); }
    var fm = td('rt-format', L.table.format);
    fm.appendChild(icon(r.format, 'icon--file'));
    fm.appendChild(el('span', null, r.format.toUpperCase()));
    td('num', L.table.size).textContent = fmtSize(r.size_bytes);
    td('rt-lang', L.table.language).textContent = (L.langs && L.langs[r.language]) || r.language;
    var ac = td('rt-access', L.table.access);
    ac.appendChild(el('span', 'badge badge--' + r.access, L.access[r.access]));
    ac.appendChild(document.createTextNode(' '));
    ac.appendChild(accessButton(r));
    return tr;
  }

  function renderResults(list) {
    resultsTable.textContent = '';
    var wrap = el('div', 'table-wrap');
    var table = el('table', 'data-table');
    var thead = el('thead');
    var htr = el('tr');
    [['date', ''], ['ticker', ''], ['type', ''], ['title', ''], ['format', ''], ['size', 'num'], ['language', ''], ['access', '']].forEach(function (c) {
      var th = el('th', c[1], L.table[c[0]]);
      th.setAttribute('scope', 'col');
      htr.appendChild(th);
    });
    thead.appendChild(htr);
    table.appendChild(thead);
    var tbody = el('tbody');
    list.slice(0, MAX_ROWS).forEach(function (r) { tbody.appendChild(reportRow(r)); });
    table.appendChild(tbody);
    wrap.appendChild(table);
    resultsTable.appendChild(wrap);
  }

  // ---------- main update ----------
  function apply() {
    var st = state();
    var repActive = reportFiltersActive(st);
    if (repActive) { load(); }

    var tickersWithReport = null;
    var matchedReports = [];
    if (repActive && data) {
      tickersWithReport = {};
      data.reports.forEach(function (r) {
        if (reportMatches(r, st)) { tickersWithReport[r.ticker.toUpperCase()] = true; }
      });
    }

    var visible = 0;
    var visibleTickers = {};
    cards.forEach(function (c) {
      var ok = cardMatches(c, st);
      if (ok && repActive) {
        ok = tickersWithReport ? !!tickersWithReport[c._ticker] : cardHasReportFallback(c, st);
      }
      c.hidden = !ok;
      if (ok) { visible++; visibleTickers[c._ticker] = true; }
    });

    groups.forEach(function (g) {
      var any = g.querySelector('.mv-card:not([hidden])');
      g.hidden = !any;
    });
    emptyEl.hidden = visible !== 0;

    var msg = L.hub.showing + ' ' + visible + ' ' + L.hub.of + ' ' + cards.length + ' ' + L.hub.companies;

    if (repActive && data) {
      data.reports.forEach(function (r) {
        if (reportMatches(r, st) && visibleTickers[r.ticker.toUpperCase()]) { matchedReports.push(r); }
      });
      matchedReports.sort(function (a, b) { return a.date < b.date ? 1 : (a.date > b.date ? -1 : 0); });
      msg += ' · ' + matchedReports.length + ' ' + L.hub.reports_match;
      renderResults(matchedReports);
      resultsBox.hidden = false;
    } else {
      resultsBox.hidden = true;
      resultsTable.textContent = '';
    }
    countEl.textContent = msg;
    writeURL();
  }

  function reset() {
    q.value = '';
    KEYS.forEach(function (k) { sel[k].value = ''; });
    apply();
    q.focus();
  }

  controls.hidden = false;
  controls.addEventListener('submit', function (e) { e.preventDefault(); });
  q.addEventListener('input', apply);
  KEYS.forEach(function (k) { sel[k].addEventListener('change', apply); });
  clearBtn.addEventListener('click', reset);

  readURL();
  apply();
})();
