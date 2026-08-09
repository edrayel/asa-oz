/* Auto-grow textareas to fit their content.
 * Empty textareas keep their rows attribute height (3-4 rows); as the user
 * types (or content is set programmatically) the field grows to fit.
 */
(function () {
  'use strict';

  function grow(ta) {
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  }

  function init(root) {
    (root || document).querySelectorAll('textarea').forEach(grow);
  }

  document.addEventListener('input', function (e) {
    if (e.target && e.target.tagName === 'TEXTAREA') grow(e.target);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(); });
  } else {
    init();
  }

  window.__growTextarea = grow;
})();
