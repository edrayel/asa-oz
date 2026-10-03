/* Admin shell interactions: the off-canvas sidebar drawer and the appbar
   profile dropdown.

   The drawer follows the same shape as the public site's mobile menu
   (static/js/site.js): a state class, aria attributes, a body scroll lock, and
   closing on Escape (returning focus to the trigger). Unlike the public site,
   which wires three separate document-level outside-click listeners, this is a
   single pair of controllers. */
(function () {
  var DESKTOP = window.matchMedia('(min-width: 800px)');

  /* ---- Sidebar: sticky column on desktop, drawer below 800px ---- */
  (function () {
    var sidebar = document.getElementById('adminSidebar');
    var scrim = document.getElementById('adminScrim');
    var toggle = document.getElementById('adminMenuToggle');
    if (!sidebar || !scrim || !toggle) return;

    var open = false;

    function apply(returnFocus) {
      sidebar.classList.toggle('is-open', open);
      scrim.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      // Only hide from assistive tech while it is genuinely off-canvas, or the
      // desktop sidebar would become unreachable to a screen reader.
      if (open || DESKTOP.matches) sidebar.removeAttribute('aria-hidden');
      else sidebar.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = open ? 'hidden' : '';
      if (returnFocus) toggle.focus();
    }

    function setOpen(next, returnFocus) {
      if (next === open) return;
      open = next;
      apply(returnFocus);
    }

    toggle.addEventListener('click', function () { setOpen(!open, true); });
    scrim.addEventListener('click', function () { setOpen(false, true); });

    sidebar.querySelectorAll('.admin-nav a').forEach(function (link) {
      link.addEventListener('click', function () { setOpen(false, false); });
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setOpen(false, open);
    });

    // Crossing back to desktop widths with the drawer open would otherwise
    // leave the page scroll-locked behind a sidebar that is no longer a drawer.
    DESKTOP.addEventListener('change', function () { setOpen(false, false); apply(false); });

    apply(false);
  })();

  /* ---- Appbar profile dropdown ---- */
  (function () {
    var toggle = document.getElementById('adminProfileToggle');
    var menu = document.getElementById('adminProfileMenu');
    if (!toggle || !menu) return;

    var open = false;

    function apply(returnFocus) {
      menu.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (returnFocus) toggle.focus();
    }

    function setOpen(next, returnFocus) {
      if (next === open) return;
      open = next;
      apply(returnFocus);
    }

    toggle.addEventListener('click', function (e) {
      // Keep the document-level listener below from immediately closing it.
      e.stopPropagation();
      setOpen(!open, true);
    });

    document.addEventListener('click', function (e) {
      if (open && !menu.contains(e.target)) setOpen(false, false);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setOpen(false, open);
    });

    apply(false);
  })();
})();
