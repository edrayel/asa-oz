/* The ALTCHA captcha driver.

   The widget is hidden until the form is submitted: nothing is shown while
   the visitor reads and fills the form in. When the button is pressed, this
   script shows the widget's own UI (the checkbox with the circular progress
   spinner) and lets it solve the proof of work. Only then is the form sent.

   It is a separate file because the admin pages do not load site.js, and
   it has to run after the widget (loaded with defer). */
(function () {
  'use strict';

  function show(widget) {
    widget.setAttribute('display', 'standard');
  }

  function hide(widget) {
    widget.setAttribute('display', 'invisible');
    try { widget.reset(); } catch (e) {}
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
    // Let the browser's own validation run first: an empty required field
    // must not be sent to the server just because the captcha solved.
    if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
      if (typeof form.reportValidity === 'function') form.reportValidity();
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    show(widget);

    var done = false;
    function finish(ok) {
      if (done) return;
      done = true;
      if (!ok) {
        hide(widget);
        return;
      }
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
