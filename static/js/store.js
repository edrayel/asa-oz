/* Store page: filter controls drive the HTMX grid. */
(function () {
  'use strict';
  var grid = document.getElementById('storeGrid');
  if (!grid) return;

  document.querySelectorAll('.filter-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.filter-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var filter = btn.getAttribute('data-filter');
      if (window.htmx) {
        htmx.ajax('GET', '/store/partial?type=' + encodeURIComponent(filter), {
          target: grid,
          swap: 'innerHTML'
        });
      }
    });
  });
})();