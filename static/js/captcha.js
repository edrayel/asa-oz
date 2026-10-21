/* The ALTCHA captcha driver.

   The widget itself is silent (auto="off", display="invisible"): it draws
   nothing and does not intercept the form. This script drives it, so the
   same flow works for a plain form, an HTMX form and the forms this site
   submits with fetch: the first submit is held back, the browser solves
   the proof of work, and only then is the form sent. The visitor sees one
   line under the button while it happens.

   It is loaded on its own (not from site.js) because the admin pages do
   not load site.js. */
(function () {
  function noteFor(form) {
    var el = form.querySelector('.captcha-note');
    if (!el) {
      el = document.createElement('p');
      el.className = 'captcha-note';
      el.setAttribute('role', 'status');
      el.setAttribute('aria-live', 'polite');
      var button = form.querySelector('button[type="submit"], input[type="submit"]');
      if (button) {
        button.insertAdjacentElement('afterend', el);
      } else {
        form.appendChild(el);
      }
    }
    return el;
  }

  function say(form, message, state) {
    var el = noteFor(form);
    el.textContent = message;
    el.className = 'captcha-note' + (state ? ' is-' + state : '');
    // The note sits under the submit button, which is often at the bottom
    // of the form: scroll by exactly what is needed so the visitor can
    // read it. The measurement waits for the next frame, so the note has
    // its final height by then. scrollIntoView is not used here — it aims
    // at the element's edge and leaves the last line below the fold.
    window.requestAnimationFrame(function () {
      var box = el.getBoundingClientRect();
      var delta = 0;
      if (box.bottom > window.innerHeight) {
        delta = box.bottom - window.innerHeight + 8;
      } else if (box.top < 0) {
        delta = box.top - 8;
      }
      if (delta) {
        // 'instant': the site sets scroll-behavior: smooth, which would
        // leave the note half off the screen while it animated.
        try {
          window.scrollBy({ top: delta, behavior: 'instant' });
        } catch (e) {
          window.scrollBy(0, delta);
        }
      }
    });
  }

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form || form.tagName !== 'FORM') return;
    var widget = form.querySelector('altcha-widget');
    if (!widget) return;
    if (form.dataset.captchaVerified === '1') {
      // The second attempt — the real one — is left alone.
      delete form.dataset.captchaVerified;
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    say(form, 'Checking you are human…', 'checking');

    var done = false;
    function finish(ok) {
      if (done) return;
      done = true;
      if (!ok) {
        say(form, 'We could not check that you are human. Please try again.', 'failed');
        try { widget.reset(); } catch (e) {}
        return;
      }
      say(form, 'Thank you — sending…', 'done');
      form.dataset.captchaVerified = '1';
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }

    widget.addEventListener('verified', function () { finish(true); }, { once: true });
    widget.addEventListener('statechange', function (ev) {
      var state = ev.detail && ev.detail.state;
      if (state === 'error' || state === 'expired') finish(false);
    });
    var result;
    try {
      result = widget.verify();
    } catch (err) {
      finish(false);
      return;
    }
    if (result && typeof result.catch === 'function') {
      result.catch(function () { finish(false); });
    }
  }, true);
})();
