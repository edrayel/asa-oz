/* Asa-OZ shared site behavior (replaces legacy shared.js client-side chrome).
 * Server now renders header/footer/mobile menu; this wires interactions.
 */
(function () {
  'use strict';

  // Year in footer
  var yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // ---- Back to top ----
  (function () {
    var btn = document.getElementById('backToTop');
    if (!btn) return;
    var threshold = 600;
    function update() {
      btn.classList.toggle('visible', window.scrollY > threshold);
    }
    update();
    window.addEventListener('scroll', update, { passive: true });
    btn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  })();

  // ---- Mobile menu ----
  (function () {
    var menu = document.getElementById('mobileMenu');
    var toggle = document.getElementById('menuToggle');
    var close = document.getElementById('menuClose');
    if (!menu || !toggle || !close) return;

    function openMenu() {
      menu.classList.add('is-open');
      menu.setAttribute('aria-hidden', 'false');
      toggle.setAttribute('aria-expanded', 'true');
      document.body.style.overflow = 'hidden';
    }
    function closeMenu() {
      menu.classList.remove('is-open');
      menu.setAttribute('aria-hidden', 'true');
      toggle.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    }
    toggle.addEventListener('click', function () {
      if (menu.classList.contains('is-open')) closeMenu(); else openMenu();
    });
    close.addEventListener('click', closeMenu);
    menu.addEventListener('click', function (e) { if (e.target === menu) closeMenu(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.classList.contains('is-open')) { closeMenu(); toggle.focus(); }
    });
    menu.querySelectorAll('.mobile-menu-nav a').forEach(function (link) {
      link.addEventListener('click', closeMenu);
    });
  })();

  // ---- Cart drawer ----
  (function () {
    var drawer = document.getElementById('cartDrawer');
    var overlay = document.getElementById('cartOverlay');
    var toggle = document.getElementById('cartToggle');
    var close = document.getElementById('cartClose');
    if (!drawer || !overlay) return;

    function openCart() {
      drawer.classList.add('open');
      overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
    function closeCart() {
      drawer.classList.remove('open');
      overlay.classList.remove('open');
      document.body.style.overflow = '';
    }
    if (toggle) toggle.addEventListener('click', openCart);
    if (close) close.addEventListener('click', closeCart);
    overlay.addEventListener('click', closeCart);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeCart(); });

    // Refresh the cart count badge after any htmx swap touches the cart.
    document.body.addEventListener('htmx:afterSwap', function (e) {
      var isCartOp = e.detail && e.detail.target && e.detail.target.id === 'cartBody';
      if (isCartOp) {
        var countBadge = document.getElementById('cartCount');
        var count = document.querySelectorAll('#cartBody .cart-item').length;
        if (countBadge) {
          countBadge.textContent = count;
          countBadge.style.display = (count > 0) ? '' : 'none';
        }
        // Open the drawer when an item is added.
        if (e.detail && e.detail.requestConfig && /\/cart\/add/.test(e.detail.requestConfig.path)) {
          openCart();
        }
      }
    });
  })();

  // ---- Booking overlay ----
  (function () {
    var overlay = document.getElementById('bookingOverlay');
    if (!overlay) return;
    var form = document.getElementById('bookingForm');
    var closeBtn = document.getElementById('bookingClose');
    var cancelBtn = document.getElementById('bookingCancel');
    var headerTrigger = document.getElementById('headerBookingTrigger');

    function openBooking() {
      overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
    function closeBooking() {
      overlay.classList.remove('open');
      document.body.style.overflow = '';
    }
    function resetForm() {
      if (!form) return;
      form.reset();
      Object.keys(form.elements).forEach(function (k) {
        var el = form.elements[k];
        var field = el.closest ? el.closest('.booking-field') : null;
        if (field) field.classList.remove('is-invalid');
      });
    }

    document.addEventListener('click', function (e) {
      if (e.target && e.target.classList && e.target.classList.contains('pricing-btn')) {
        e.preventDefault(); openBooking();
      }
      if (e.target && e.target.id === 'bookingTrigger') { e.preventDefault(); openBooking(); }
    });
    if (headerTrigger) {
      headerTrigger.addEventListener('click', function (e) { e.preventDefault(); openBooking(); });
      headerTrigger.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openBooking(); }
      });
    }
    if (closeBtn) closeBtn.addEventListener('click', function () { closeBooking(); resetForm(); });
    if (cancelBtn) cancelBtn.addEventListener('click', function () { closeBooking(); resetForm(); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) { closeBooking(); resetForm(); } });

    if (form) {
      function validateField(field) {
        var input = field.querySelector('input');
        if (!input) return true;
        if (input.hasAttribute('required') && !input.value.trim()) { field.classList.add('is-invalid'); return false; }
        if (input.type === 'email' && input.value.trim()) {
          if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value.trim())) { field.classList.add('is-invalid'); return false; }
        }
        field.classList.remove('is-invalid');
        return true;
      }
      form.addEventListener('input', function () {
        form.querySelectorAll('.booking-field').forEach(function (f) { validateField(f); });
      });
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var fields = form.querySelectorAll('.booking-field');
        var valid = true;
        fields.forEach(function (f) { if (!validateField(f)) valid = false; });
        if (!valid) return;
        var fd = new FormData(form);
        fetch(form.action || '/booking', { method: 'POST', body: fd, headers: { 'X-HTML': '1' } })
          .then(function (res) { return res.text(); })
          .then(function (html) {
            var body = document.getElementById('bookingBody');
            if (body) body.innerHTML = html;
            setTimeout(closeBooking, 4000);
          })
          .catch(function () {
            var body = document.getElementById('bookingBody');
            if (body) body.innerHTML = '<div class="booking-confirmation" style="display:flex;"><p>Something went wrong. Please email <a href="mailto:info@asa-oz.com">info@asa-oz.com</a>.</p></div>';
          });
      });
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && overlay.classList.contains('open')) { closeBooking(); resetForm(); }
    });
  })();

  // ---- Cookie consent (GDPR / ePrivacy) ----
  (function () {
    var STORE_KEY = 'asa-oz-consent';
    var bar = document.getElementById('cookieBar');
    if (!bar) return;
    function setConsent(value) {
      try { localStorage.setItem(STORE_KEY, value); } catch (e) {}
      bar.classList.remove('show');
      bar.classList.add('is-hidden');
      if (value === 'all') { /* hook for analytics load here */ }
    }
    var stored = null;
    try { stored = localStorage.getItem(STORE_KEY); } catch (e) {}
    if (stored === 'all' || stored === 'necessary') {
      bar.classList.add('is-hidden');
    } else {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { bar.classList.add('show'); });
      });
    }
    var accept = document.getElementById('ckAccept');
    var reject = document.getElementById('ckReject');
    if (accept) accept.addEventListener('click', function () { setConsent('all'); });
    if (reject) reject.addEventListener('click', function () { setConsent('necessary'); });
  })();

  // ---- Scroll reveal ----
  var items = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          var el = e.target;
          el.classList.add('in');
          io.unobserve(el);
        }
      });
    }, { threshold: 0.15 });
    items.forEach(function (el, i) { el.dataset.delay = (i % 6) * 90; io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add('in'); });
  }

  // ---- Waitlist / feedback / contact forms (server-driven) ----
  function wireAjaxForm(formId, msgId) {
    var form = document.getElementById(formId);
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var msg = document.getElementById(msgId);
      var fd = new FormData(form);
      fetch(form.action, { method: 'POST', body: fd })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          if (msg) msg.innerHTML = html;
          form.reset && form.reset();
        })
        .catch(function () { if (msg) msg.innerHTML = '<p class="msg" style="color:#b5482c;">Something went wrong. Please try again.</p>'; });
    });
  }
  wireAjaxForm('waitform', 'formMsg');
  wireAjaxForm('feedbackForm', 'feedbackMsg');
  wireAjaxForm('contactForm', 'contactMsg');

})();