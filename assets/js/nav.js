/* Site navigation: mobile menu + accessible dropdowns. Vanilla JS, no dependencies. */
(function () {
  'use strict';

  var toggle = document.getElementById('nav-toggle');
  var menu = document.getElementById('nav-menu');
  var dropdowns = Array.prototype.slice.call(document.querySelectorAll('.nav-item--dropdown'));

  function setOpen(li, open) {
    li.classList.toggle('is-open', open);
    var link = li.querySelector('.nav-link--has-dropdown');
    if (link) { link.setAttribute('aria-expanded', open ? 'true' : 'false'); }
  }

  function closeAll(except) {
    dropdowns.forEach(function (li) { if (li !== except) { setOpen(li, false); } });
  }

  function closeMenu() {
    if (menu && toggle && menu.classList.contains('is-open')) {
      menu.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      return true;
    }
    return false;
  }

  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      var open = menu.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  dropdowns.forEach(function (li) {
    var link = li.querySelector('.nav-link--has-dropdown');
    var arrow = li.querySelector('.nav-arrow');
    if (!link) { return; }
    link.setAttribute('aria-haspopup', 'true');
    link.setAttribute('aria-expanded', 'false');

    // Tapping the arrow opens the submenu without leaving the page (touch + mobile menu).
    if (arrow) {
      arrow.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var open = !li.classList.contains('is-open');
        closeAll(li);
        setOpen(li, open);
      });
    }

    // Keyboard: ArrowDown opens and moves into the submenu, Esc closes and returns focus.
    link.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        closeAll(li);
        setOpen(li, true);
        var first = li.querySelector('.nav-dropdown a');
        if (first) { first.focus(); }
      }
    });
    li.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && li.classList.contains('is-open')) {
        e.stopPropagation();
        setOpen(li, false);
        link.focus();
      }
    });
  });

  document.addEventListener('click', function (e) {
    if (!e.target.closest('.nav-item--dropdown')) { closeAll(); }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeAll();
      if (closeMenu() && toggle) { toggle.focus(); }
    }
  });

  // Moving to a different language or leaving the page should not leave the menu open on bfcache restore.
  window.addEventListener('pageshow', function () { closeAll(); closeMenu(); });
})();
