/* Report tables: clamp long descriptions to 2 lines with a "more / less" toggle.
   Without JS the full description is simply shown (the clamp class is added here). */
(function () {
  'use strict';

  function labels(cell) {
    var wrap = cell.closest('.table-wrap');
    return {
      more: (wrap && wrap.getAttribute('data-more')) || 'more',
      less: (wrap && wrap.getAttribute('data-less')) || 'less'
    };
  }

  function needsToggle(sum) {
    return sum.scrollHeight > sum.clientHeight + 1;
  }

  function setup(sum) {
    if (sum.getAttribute('data-clamped')) { return; }
    sum.setAttribute('data-clamped', '1');
    sum.classList.add('is-clamped');
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'link-btn rt-title__more';
    btn.setAttribute('aria-expanded', 'false');
    btn.hidden = true;
    sum.parentNode.appendChild(btn);
    var l = labels(sum);
    btn.textContent = l.more;
    btn.addEventListener('click', function () {
      var open = sum.classList.toggle('is-clamped') === false;
      btn.textContent = open ? l.less : l.more;
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    sum._btn = btn;
  }

  function refresh(sum) {
    if (!sum._btn) { return; }
    // Only measure while clamped; once expanded the button stays so it can be collapsed again.
    if (sum.classList.contains('is-clamped')) { sum._btn.hidden = !needsToggle(sum); }
  }

  function init(root) {
    var sums = (root || document).querySelectorAll('.rt-title__sum');
    Array.prototype.forEach.call(sums, function (s) { setup(s); refresh(s); });
  }

  window.MervalReports = { init: init };

  function all() { init(document); }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', all); } else { all(); }
  // Fonts and layout change line breaks: re-measure.
  if (document.fonts && document.fonts.ready) { document.fonts.ready.then(all); }
  var t;
  window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(all, 150); });
})();
