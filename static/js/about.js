/* About page: the portrait film interlude.
 * Autoplays muted while it is in view, but only when the visitor has not asked
 * for reduced motion, is not on a metered connection, and is on a precise
 * pointer. Otherwise the poster stays put and the play control drives it.
 */
(function () {
  'use strict';

  var plate = document.getElementById('filmPlate');
  var video = document.getElementById('aboutFilm');
  if (!plate || !video) return;

  var playBtn = document.getElementById('filmPlay');
  var soundBtn = document.getElementById('filmSound');

  function sync() {
    plate.classList.toggle('is-playing', !video.paused);
    plate.classList.toggle('is-muted', video.muted);
    if (playBtn) playBtn.setAttribute('aria-label', video.paused ? 'Play the film' : 'Pause the film');
    if (soundBtn) {
      soundBtn.setAttribute('aria-label', video.muted ? 'Turn sound on' : 'Turn sound off');
      soundBtn.setAttribute('aria-pressed', video.muted ? 'false' : 'true');
    }
  }

  function attemptPlay() {
    var p = video.play();
    if (p && typeof p.catch === 'function') p.catch(function () {});
  }

  if (playBtn) {
    playBtn.addEventListener('click', function () {
      if (video.paused) attemptPlay();
      else video.pause();
    });
  }

  if (soundBtn) {
    soundBtn.addEventListener('click', function () {
      video.muted = !video.muted;
      if (!video.muted && video.paused) attemptPlay();
    });
  }

  video.addEventListener('play', sync);
  video.addEventListener('pause', sync);
  video.addEventListener('volumechange', sync);

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var metered = !!(navigator.connection && navigator.connection.saveData);
  var precise = window.matchMedia('(pointer: fine)').matches;

  if (!reduced && !metered && precise && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) attemptPlay();
        else if (!video.paused) video.pause();
      });
    }, { threshold: 0.45 });
    io.observe(video);
  }

  sync();
})();
