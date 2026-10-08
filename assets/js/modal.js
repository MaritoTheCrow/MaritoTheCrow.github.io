/* Accessible modals for report access buttons.
   Progressive enhancement: without JS the buttons are plain links (mailto / subscribe page).
   Provides: focus trap, Esc to close, focus return, inert background, aria attributes. */
(function () {
  'use strict';

  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  var current = null;
  var lastFocus = null;

  function visibleFocusables(root) {
    return Array.prototype.filter.call(root.querySelectorAll(FOCUSABLE), function (el) {
      return el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement;
    });
  }

  function open(modal, opener) {
    if (current) { close(true); }
    lastFocus = opener || document.activeElement;
    // Move the dialog to <body> so the whole page (header, nav, main, footer) can be made inert.
    if (modal.parentNode !== document.body) { document.body.appendChild(modal); }
    Array.prototype.forEach.call(document.body.children, function (el) {
      if (el !== modal && el.tagName !== 'SCRIPT') {
        el.setAttribute('inert', '');
        el.setAttribute('data-mv-inert', '');
      }
    });
    current = modal;
    modal.hidden = false;
    document.body.classList.add('mv-modal-open');
    var panel = modal.querySelector('.mv-modal__panel');
    var first = modal.querySelector('input:not([type="hidden"]), textarea, select') || visibleFocusables(modal)[0] || panel;
    if (first && first.focus) { first.focus(); }
  }

  function close(silent) {
    if (!current) { return; }
    current.hidden = true;
    current = null;
    document.body.classList.remove('mv-modal-open');
    Array.prototype.forEach.call(document.querySelectorAll('[data-mv-inert]'), function (el) {
      el.removeAttribute('inert');
      el.removeAttribute('data-mv-inert');
    });
    if (!silent && lastFocus && typeof lastFocus.focus === 'function') { lastFocus.focus(); }
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) { el.textContent = text || ''; }
  }

  function openContact(btn) {
    var modal = document.getElementById('mv-modal-contact');
    if (!modal) { return false; }
    var id = btn.getAttribute('data-report-id') || '';
    var title = btn.getAttribute('data-report-title') || '';
    var label = btn.querySelector('span');
    setText('mv-req-title', title);
    setText('mv-req-id', id);
    var hid = document.getElementById('mv-req-hid-id');
    var hit = document.getElementById('mv-req-hid-title');
    var subj = document.getElementById('mv-req-subject');
    if (hid) { hid.value = id; }
    if (hit) { hit.value = title; }
    if (subj) { subj.value = '[MCB Advisor] ' + (label ? label.textContent.trim() : 'Request') + ': ' + id; }
    open(modal, btn);
    return true;
  }

  function openSubscriber(btn) {
    var modal = document.getElementById('mv-modal-subscriber');
    if (!modal) { return false; }
    setText('mv-sub-title', btn.getAttribute('data-report-title'));
    setText('mv-sub-id', btn.getAttribute('data-report-id'));
    var link = document.getElementById('mv-sub-link');
    if (link) { link.setAttribute('href', btn.getAttribute('href')); }
    open(modal, btn);
    return true;
  }

  document.addEventListener('click', function (e) {
    var closer = e.target.closest('[data-close]');
    if (closer && current && current.contains(closer)) {
      e.preventDefault();
      close();
      return;
    }
    var btn = e.target.closest('.js-access');
    if (!btn) { return; }
    var kind = btn.getAttribute('data-access');
    var handled = false;
    if (kind === 'contact') { handled = openContact(btn); }
    else if (kind === 'subscriber') { handled = openSubscriber(btn); }
    if (handled) { e.preventDefault(); }
  });

  document.addEventListener('keydown', function (e) {
    if (!current) { return; }
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close();
      return;
    }
    if (e.key === 'Tab') {
      var items = visibleFocusables(current);
      if (!items.length) { e.preventDefault(); return; }
      var first = items[0];
      var last = items[items.length - 1];
      var active = document.activeElement;
      if (!current.contains(active)) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && (active === first || active === current.querySelector('.mv-modal__panel'))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, true);
})();
