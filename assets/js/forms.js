/* Subscribe page: pre-fill the form from the URL (?ticker=AGRO&report=agro-2026-01-30-valuation-model-xlsx). */
(function () {
  'use strict';
  var params;
  try { params = new URLSearchParams(window.location.search); } catch (e) { return; }
  var ticker = (params.get('ticker') || '').toUpperCase().replace(/[^A-Z0-9, ]/g, '');
  var report = (params.get('report') || '').replace(/[^A-Za-z0-9_.\-]/g, '');

  var tickersField = document.getElementById('sub-tickers');
  if (tickersField && ticker && !tickersField.value) { tickersField.value = ticker; }

  var hidden = document.getElementById('sub-report');
  var note = document.getElementById('sub-prefill');
  var noteId = document.getElementById('sub-prefill-id');
  if (report && hidden) {
    hidden.value = report;
    if (note && noteId) {
      noteId.textContent = report;
      note.hidden = false;
    }
  }
})();
