/* Asa-OZ homepage behaviors (countdown, cookie bar, testimonial rotator,
 * founder carousel, gallery arch-deck, pricing toggle). Server-driven forms
 * and cart/booking chrome live in site.js.
 */
(function () {
  'use strict';

  // ---- Gallery: Arch Deck ----
  (function () {
    var track = document.getElementById('galleryTrack');
    var prevBtn = document.getElementById('galleryPrev');
    var nextBtn = document.getElementById('galleryNext');
    var captionEl = document.getElementById('galleryCaption');
    var stageEl = document.getElementById('galleryStage');
    if (!track) return;
    var images = [
      { src: 'https://picsum.photos/seed/asaoz-culture/600/800', alt: 'Cultural gathering and storytelling' },
      { src: 'https://picsum.photos/seed/asaoz-travel/600/800', alt: 'Meaningful travel and exploration' },
      { src: 'https://picsum.photos/seed/asaoz-community/600/800', alt: 'Community connection and belonging' },
      { src: 'https://picsum.photos/seed/asaoz-nature/600/800', alt: 'Nature and reflection' },
      { src: 'https://picsum.photos/seed/asaoz-heritage/600/800', alt: 'Heritage and identity' }
    ];
    var currentIndex = 0;
    var isAnimating = false;
    var cards = [];
    var isMobile = window.innerWidth <= 560;
    var isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var hasFinePointer = window.matchMedia('(pointer: fine)').matches;

    function archPose(index, total) {
      var mid = Math.floor(total / 2);
      var offset = index - mid;
      var dir = offset === 0 ? 0 : offset / Math.abs(offset);
      var dist = Math.abs(offset);
      var depth = isMobile ? 0 : (hasFinePointer ? 1 : 0.5);
      var scale = Math.max(0.72, 1 - dist * 0.08 * depth);
      var translateY = dist * 30 * depth;
      var rotate = dir * dist * 2.5 * depth;
      return { scale: scale, translateY: translateY, rotate: rotate };
    }

    function applyMobileClass() {
      if (stageEl) stageEl.classList.toggle('is-mobile', isMobile && !isReducedMotion);
    }

    function render() {
      var total = images.length;
      cards.forEach(function (card, i) {
        var pose = archPose(i, total);
        var isActive = i === currentIndex;
        card.classList.toggle('active', isActive);
        if (!isMobile && !isReducedMotion) {
          card.style.transform = 'translateY(' + pose.translateY + 'px) scale(' + pose.scale + ') rotate(' + pose.rotate + 'deg)';
        }
        card.style.zIndex = isActive ? 3 : (total - Math.abs(i - currentIndex));
      });
      captionEl.textContent = images[currentIndex].alt;
      applyMobileClass();
    }

    function goTo(index) {
      if (isAnimating) return;
      isAnimating = true;
      currentIndex = (index + images.length) % images.length;
      render();
      setTimeout(function () { isAnimating = false; }, 700);
    }

    images.forEach(function (img, i) {
      var card = document.createElement('div');
      card.className = 'gallery-card reveal';
      var image = document.createElement('img');
      image.src = img.src;
      image.alt = img.alt;
      image.loading = 'lazy';
      image.decoding = 'async';
      card.appendChild(image);
      track.appendChild(card);
      cards.push(card);
    });

    render();
    prevBtn.addEventListener('click', function () { goTo(currentIndex - 1); });
    nextBtn.addEventListener('click', function () { goTo(currentIndex + 1); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') goTo(currentIndex - 1);
      if (e.key === 'ArrowRight') goTo(currentIndex + 1);
    });
    var startX = 0;
    if (track) {
      track.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; }, { passive: true });
      track.addEventListener('touchend', function (e) {
        var diff = e.changedTouches[0].clientX - startX;
        if (Math.abs(diff) > 40) { diff > 0 ? goTo(currentIndex - 1) : goTo(currentIndex + 1); }
      });
    }
    window.addEventListener('resize', function () {
      isMobile = window.innerWidth <= 560;
      render();
    });
    if (hasFinePointer && !isReducedMotion && stageEl) {
      stageEl.addEventListener('mousemove', function (e) {
        var rect = stageEl.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        var centerX = rect.width / 2;
        var centerY = rect.height / 2;
        var rotateY = ((x - centerX) / centerX) * 4;
        var rotateX = ((centerY - y) / centerY) * 2;
        track.style.transform = 'rotateX(' + rotateX + 'deg) rotateY(' + rotateY + 'deg)';
      });
      stageEl.addEventListener('mouseleave', function () {
        track.style.transform = 'rotateX(0deg) rotateY(0deg)';
      });
    }
  })();

  // ---- Testimonial ribbon rotator ----
  (function () {
    var quoteEl = document.getElementById('testimonialQuote');
    var authorEl = document.getElementById('testimonialAuthor');
    var testimonialPhotoEl = document.getElementById('testimonialPhoto');
    if (!quoteEl || !authorEl) return;
    var testimonials = [
      { text: 'Asa-OZ helped me reconnect with a part of myself I thought was lost forever. The journey was more than travel — it was a return.', name: 'Margaret', location: 'Ireland', role: 'Community Member', photo: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=200&q=80' },
      { text: 'I arrived alone, unsure of what to expect. I left with friendships that feel like home and a sense of belonging I haven\'t felt in years.', name: 'Thomas', location: 'Ireland', role: 'Journey Participant', photo: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&q=80' },
      { text: 'The cultural storytelling sessions reminded me that my heritage has something to say. I felt seen, heard, and valued for the first time in a long while.', name: 'Eileen', location: 'Co. Clare', role: 'Identity Circle Member', photo: 'https://images.unsplash.com/photo-1554151228-14d9def656ec?w=200&q=80' }
    ];
    var tIndex = 0;
    var tInterval;
    var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function showTestimonial(index) {
      var t = testimonials[index];
      quoteEl.style.opacity = '0';
      quoteEl.style.transform = 'translateY(8px)';
      authorEl.style.opacity = '0';
      authorEl.style.transform = 'translateY(8px)';
      if (testimonialPhotoEl) { testimonialPhotoEl.style.opacity = '0'; testimonialPhotoEl.style.transform = 'translateY(6px)'; }
      setTimeout(function () {
        quoteEl.innerHTML = '<p>&ldquo;' + t.text + '&rdquo;</p>';
        authorEl.innerHTML = t.name + ', ' + t.location + '<span>' + t.role + '</span>';
        if (testimonialPhotoEl && t.photo) {
          var img = testimonialPhotoEl.querySelector('img');
          if (img) { img.src = t.photo; img.alt = t.name + ', ' + t.role; }
          testimonialPhotoEl.style.display = '';
        } else if (testimonialPhotoEl) {
          testimonialPhotoEl.style.display = 'none';
        }
        quoteEl.style.opacity = '1';
        quoteEl.style.transform = 'none';
        authorEl.style.opacity = '1';
        authorEl.style.transform = 'none';
        if (testimonialPhotoEl) { testimonialPhotoEl.style.opacity = '1'; testimonialPhotoEl.style.transform = 'none'; }
      }, reducedMotion ? 0 : 400);
    }

    function startAuto() {
      tInterval = setInterval(function () {
        tIndex = (tIndex + 1) % testimonials.length;
        showTestimonial(tIndex);
      }, 8000);
    }
    function resetAuto() { clearInterval(tInterval); startAuto(); }
    quoteEl.addEventListener('click', function () { tIndex = (tIndex + 1) % testimonials.length; showTestimonial(tIndex); resetAuto(); });
    authorEl.addEventListener('click', function () { tIndex = (tIndex + 1) % testimonials.length; showTestimonial(tIndex); resetAuto(); });
    if (!reducedMotion) startAuto();
  })();

  // ---- Founder photo carousel ----
  (function () {
    var carousel = document.getElementById('founderCarousel');
    if (!carousel) return;
    var slides = document.getElementById('founderSlides');
    var prev = document.getElementById('founderPrev');
    var next = document.getElementById('founderNext');
    var dotsWrap = document.getElementById('founderDots');
    var imgs = slides ? slides.children : [];
    var index = 0;
    var total = imgs.length;
    if (!dotsWrap || total < 2) return;

    for (var i = 0; i < total; i++) {
      var dot = document.createElement('button');
      dot.type = 'button';
      dot.setAttribute('aria-label', 'Go to photo ' + (i + 1));
      dot.addEventListener('click', (function (i) { return function () { go(i); }; })(i));
      dotsWrap.appendChild(dot);
    }
    var dots = dotsWrap.children;

    function go(i) {
      index = (i + total) % total;
      slides.style.transform = 'translateX(-' + (index * 100) + '%)';
      for (var d = 0; d < dots.length; d++) dots[d].classList.toggle('active', d === index);
    }

    prev.addEventListener('click', function () { go(index - 1); });
    next.addEventListener('click', function () { go(index + 1); });
    carousel.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { e.preventDefault(); go(index - 1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); go(index + 1); }
    });
    go(0);
  })();

  // ---- Launch countdown ----
  var TARGET = new Date('2026-08-03T00:00:00+01:00').getTime();
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var cd = {
    D: document.getElementById('cdD'),
    H: document.getElementById('cdH'),
    M: document.getElementById('cdM'),
    S: document.getElementById('cdS'),
    bar: document.getElementById('countdownBar')
  };
  if (cd.bar) {
    function humanize(ms) {
      var days = Math.floor(ms / 86400000);
      if (days < 1) return 'less than a day';
      if (days === 1) return '1 day';
      if (days < 14) return days + ' days';
      if (days < 60) return Math.round(days / 7) + ' weeks';
      return Math.round(days / 30) + ' months';
    }
    function tick() {
      var diff = TARGET - Date.now();
      if (diff <= 0) {
        cd.bar.classList.add('is-past');
        cd.bar.querySelector('.cd-label').innerHTML = 'The Asa-OZ website is live. Welcome — you don’t have to begin again alone.';
        clearInterval(timer);
        return;
      }
      var s = Math.floor(diff / 1000);
      cd.D.textContent = Math.floor(s / 86400);
      cd.H.textContent = pad(Math.floor((s % 86400) / 3600));
      cd.M.textContent = pad(Math.floor((s % 3600) / 60));
      cd.S.textContent = pad(s % 60);
      var human = document.getElementById('cdHuman');
      if (human) human.textContent = humanize(diff);
    }
    tick();
    var timer = setInterval(tick, 1000);
  }

  // Cookie consent now lives in site.js (shared across all pages)

  // ---- Pricing toggle ----
  (function () {
    var pricingSection = document.querySelector('.pricing-section');
    var pricingToggle = document.getElementById('pricingToggle');
    if (!pricingToggle || !pricingSection) return;
    pricingToggle.addEventListener('click', function (e) {
      if (e.target.tagName !== 'BUTTON') return;
      var period = e.target.getAttribute('data-period');
      pricingToggle.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
      e.target.classList.add('active');
      var prices = pricingSection.querySelectorAll('.price');
      prices.forEach(function (p) {
        var text = p.getAttribute('data-' + period);
        var suffix = period === 'monthly' ? '<span style="font-size:0.9rem; font-weight:400; color:var(--muted);">/mo</span>' : '<span style="font-size:0.9rem; font-weight:400; color:var(--muted);">/yr</span>';
        p.innerHTML = text + suffix;
      });
    });
  })();

  // ---- Wall of Moments (lazy Three.js easter egg) ----
  // Faithful port of the original: a full 360° ring of community photos you can
  // drag to rotate, scroll to spin, fling with inertia, with a gentle idle
  // drift and an entrance reveal. Falls back to a static grid if Three.js
  // cannot load (e.g. no internet) so the moment is never a dead click.
  (function () {
    var overlay = document.getElementById('wallOverlay');
    var closeBtn = document.getElementById('wallClose');
    var trigger = document.querySelector('.wall-trigger');
    var canvasWrap = document.getElementById('wallCanvasWrap');
    var loadingEl = document.getElementById('wallLoading');
    var hintsEl = document.getElementById('wallHints');
    if (!overlay || !trigger) return;

    // Full 360° ring. COLS is derived from the live image count so the ring
    // tiles seamlessly with no visible seam.
    var ROWS = 3;
    var RADIUS = 4.5;
    var PHI_MIN = -0.35;
    var PHI_MAX = 0.35;
    var DRAG_SENS = 0.0035;
    var DAMPING = 0.94;
    var EPS = 0.0001;

    var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0) || window.matchMedia('(pointer: coarse)').matches;
    var THREE_CDN = 'https://unpkg.com/three@0.160.0/build/three.min.js';

    var renderer = null, scene = null, camera = null;
    var tiles = [], rafId = null, isOpen = false;
    var theta = 0, phi = 0;
    var velocityTheta = 0, velocityPhi = 0;
    var isDragging = false;
    var prevPointer = { x: 0, y: 0 };
    var textureLoader = null;
    var hintsVisible = false;
    var urlsCache = [];

    function getWallImages() {
      return (window.WALL_OF_MEMORIES && window.WALL_OF_MEMORIES.length)
        ? window.WALL_OF_MEMORIES.slice()
        : urlsCache.slice();
    }

    // Refresh the live image list from the server at open time so newly
    // uploaded photos are picked up automatically.
    function refreshImages(cb) {
      var current = getWallImages();
      if (!current.length) { renderFallback(); return; }
      fetch('/api/wall').then(function (res) { return res.json(); }).then(function (data) {
        if (data && data.images && data.images.length) {
          window.WALL_OF_MEMORIES = data.images;
          urlsCache = data.images.slice();
          cb && cb(data.images);
        } else {
          cb && cb(current);
        }
      }).catch(function () {
        cb && cb(current);
      });
    }

    function loadThree() {
      if (window.__wallThreePromise) return window.__wallThreePromise;
      window.__wallThreePromise = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = THREE_CDN;
        s.onload = function () { resolve(window.THREE); };
        s.onerror = function () { reject(new Error('Three.js failed to load')); };
        document.head.appendChild(s);
      });
      return window.__wallThreePromise;
    }

    function showHints() {
      if (!hintsEl) return;
      hintsEl.classList.remove('hidden');
      if (isTouch) {
        hintsEl.innerHTML = '<span class="hint-icon"><svg viewBox="0 0 24 24"><path d="M14 4l-8 8 8 8"/><path d="M20 4l-8 8 8 8"/></svg></span> Swipe to explore';
      } else {
        hintsEl.innerHTML = '<span class="hint-icon"><svg viewBox="0 0 24 24"><path d="M5 9l4-4 4 4"/><path d="M9 5v14"/></svg></span> Drag to rotate &middot; Scroll to scroll &middot; Endless moments';
      }
      hintsVisible = true;
      setTimeout(function () { hideHints(); }, 5000);
    }

    function hideHints() {
      if (!hintsEl || !hintsVisible) return;
      hintsVisible = false;
      hintsEl.classList.add('hidden');
    }

    function openWall() {
      if (isOpen) return;
      isOpen = true;
      try { requestOrientation(); } catch (e) { /* not supported */ }
      overlay.classList.add('open');
      showHints();
      document.body.style.overflow = 'hidden';
      if (loadingEl) loadingEl.style.display = 'block';
      var urls = getWallImages();
      urlsCache = urls.slice();
      var THREEp = loadThree();
      if (THREEp && THREEp.then) {
        THREEp.then(function (THREE) {
          if (loadingEl) loadingEl.style.display = 'none';
          refreshImages(function (list) {
            initScene(THREE, list);
          });
        }).catch(function () {
          if (loadingEl) loadingEl.style.display = 'none';
          renderFallback();
        });
      } else if (typeof THREE !== 'undefined') {
        if (loadingEl) loadingEl.style.display = 'none';
        refreshImages(function (list) { initScene(THREE, list); });
      } else {
        if (loadingEl) loadingEl.style.display = 'none';
        renderFallback();
      }
    }

    function closeWall() {
      if (!isOpen) return;
      isOpen = false;
      tiles.forEach(function (t) {
        t.mesh.geometry.dispose();
        t.mesh.material.dispose();
        if (t.mesh.material.map) t.mesh.material.map.dispose();
        t.border.geometry.dispose();
        t.border.material.dispose();
      });
      tiles = [];
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      if (renderer) {
        if (renderer.domElement && renderer.domElement.parentNode) {
          renderer.domElement.parentNode.removeChild(renderer.domElement);
        }
        renderer.dispose();
        renderer = null;
      }
      scene = null;
      camera = null;
      textureLoader = null;
      theta = 0; phi = 0;
      velocityTheta = 0; velocityPhi = 0;
      overlay.classList.remove('open');
      document.body.style.overflow = '';
      hintsVisible = false;
      if (hintsEl) { hintsEl.classList.remove('hidden'); }
    }

    function initScene(THREE, urls) {
      textureLoader = new THREE.TextureLoader();
      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x2b2118);
      camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
      camera.position.set(0, 0, 0.01);
      camera.rotation.order = 'YXZ';
      renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.domElement.style.touchAction = 'none';
      canvasWrap.appendChild(renderer.domElement);

      var count = Math.max(1, urls.length);
      var COLS = Math.min(24, count); // match live count for a seamless ring
      var colStep = (2 * Math.PI) / COLS;
      var tileW = 2.0, tileH = 1.3;
      var entranceStart = performance.now();
      for (var row = 0; row < ROWS; row++) {
        for (var col = 0; col < COLS; col++) {
          var angle = col * colStep;
          var x = RADIUS * Math.sin(angle);
          var z = -RADIUS * Math.cos(angle);
          var y = (row - (ROWS - 1) / 2) * 1.55;
          var geom = new THREE.PlaneGeometry(tileW, tileH);
          var imgUrl = urls[(row * COLS + col) % urls.length];
          var tex = textureLoader.load(imgUrl, function (t) {
            var img = t.image;
            if (!img || !img.width || !img.height) return;
            var a = img.width / img.height;
            var tw = tileW, th = tileH;
            if (a > tileW / tileH) { th = tileW / a; }
            else { tw = tileH * a; }
            geom.scale(tw / tileW, th / tileH, 1);
          });
          tex.minFilter = THREE.LinearFilter;
          tex.magFilter = THREE.LinearFilter;
          var mat = new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide, transparent: true, opacity: 0 });
          var mesh = new THREE.Mesh(geom, mat);
          mesh.position.set(x, y, z);
          mesh.rotation.y = -angle;
          mesh.scale.setScalar(0);
          var borderGeom = new THREE.PlaneGeometry(tileW + 0.12, tileH + 0.12);
          var borderMat = new THREE.MeshBasicMaterial({ color: 0xf4ece0, side: THREE.DoubleSide, transparent: true, opacity: 0 });
          var borderMesh = new THREE.Mesh(borderGeom, borderMat);
          borderMesh.position.set(x + Math.sin(angle) * 0.015, y, z + Math.cos(angle) * 0.015);
          borderMesh.rotation.y = -angle;
          borderMesh.scale.setScalar(0);
          scene.add(mesh);
          scene.add(borderMesh);
          tiles.push({ mesh: mesh, border: borderMesh, delay: (row * COLS + col) * 40, start: entranceStart });
        }
      }
      setupControls();
      renderLoop();
    }

    function renderLoop() {
      if (!isOpen || !renderer) return;
      var now = performance.now();
      if (!reducedMotion) {
        tiles.forEach(function (t) {
          var elapsed = now - t.start;
          if (elapsed < t.delay) return;
          var p = Math.min((elapsed - t.delay) / 500, 1);
          var ease = p < 0.5 ? 2 * p * p : -1 + (4 - 2 * p) * p;
          t.mesh.material.opacity = ease;
          t.border.material.opacity = ease * 0.35;
          t.mesh.scale.setScalar(ease);
          t.border.scale.setScalar(ease);
        });
      } else {
        tiles.forEach(function (t) {
          t.mesh.material.opacity = 1;
          t.border.material.opacity = 0.35;
          t.mesh.scale.setScalar(1);
          t.border.scale.setScalar(1);
        });
      }
      if (!isDragging) {
        velocityTheta *= DAMPING;
        velocityPhi *= DAMPING;
        if (Math.abs(velocityTheta) < EPS) velocityTheta = 0;
        if (Math.abs(velocityPhi) < EPS) velocityPhi = 0;
        theta += velocityTheta;
        phi += velocityPhi;
      }
      // Infinite ring: theta wraps around the full circle so the arc can keep
      // scrolling forever. A slow constant drift keeps it moving when idle.
      var DRIFT = 0.0011;
      if (!isDragging && Math.abs(velocityTheta) < 0.0006) {
        theta += DRIFT;
      }
      theta = ((theta + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
      phi = Math.max(PHI_MIN, Math.min(PHI_MAX, phi));
      camera.rotation.y = -theta;
      camera.rotation.x = -phi;
      renderer.render(scene, camera);
      rafId = requestAnimationFrame(renderLoop);
    }

    function setupControls() {
      if (!renderer) return;
      var el = renderer.domElement;
      el.addEventListener('pointerdown', function (e) {
        if ((e.pointerType === 'mouse' && e.button === 0) || e.pointerType === 'touch' || e.pointerType === 'pen') {
          isDragging = true;
          prevPointer.x = e.clientX;
          prevPointer.y = e.clientY;
          velocityTheta = 0;
          velocityPhi = 0;
          try { el.setPointerCapture(e.pointerId); } catch (err) {}
        }
      });
      el.addEventListener('pointermove', function (e) {
        if (isDragging) {
          var dx = e.clientX - prevPointer.x;
          var dy = e.clientY - prevPointer.y;
          velocityTheta = dx * DRAG_SENS;
          velocityPhi = dy * DRAG_SENS;
          theta += velocityTheta;
          phi -= velocityPhi;
          prevPointer.x = e.clientX;
          prevPointer.y = e.clientY;
        }
      });
      el.addEventListener('pointerup', function (e) {
        if (isDragging) { isDragging = false; try { el.releasePointerCapture(e.pointerId); } catch (err) {} }
      });
      el.addEventListener('wheel', function (e) {
        e.preventDefault();
        velocityTheta += e.deltaY * 0.00015;
        velocityTheta = Math.max(-0.02, Math.min(0.02, velocityTheta));
      }, { passive: false });

      function requestOrientation() {
        if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
          DeviceOrientationEvent.requestPermission().then(function (state) {
            if (state !== 'granted') return;
            window.addEventListener('deviceorientation', function (e) {
              if (!isOpen) return;
              var gamma = e.gamma || 0;
              if (!isDragging) { theta += gamma * 0.002; }
            });
          }).catch(function () {});
        }
      }

      var resizeTimer;
      window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
          if (!renderer || !camera) return;
          camera.aspect = window.innerWidth / window.innerHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(window.innerWidth, window.innerHeight);
        }, 150);
      });
      if (hintsEl) {
        function dismissHints() { hideHints(); }
        el.addEventListener('pointerdown', dismissHints, { once: true });
        el.addEventListener('wheel', dismissHints, { once: true });
        el.addEventListener('pointermove', dismissHints, { once: true });
      }
    }

    function renderFallback() {
      if (canvasWrap.getAttribute('data-fallback') === '1') return;
      canvasWrap.setAttribute('data-fallback', '1');
      canvasWrap.innerHTML = '';
      var grid = document.createElement('div');
      grid.className = 'wall-fallback-grid';
      (getWallImages()).forEach(function (u) {
        var tile = document.createElement('div');
        tile.className = 'wall-tile';
        var img = document.createElement('img');
        img.src = u;
        img.alt = 'Community moment';
        img.loading = 'lazy';
        tile.appendChild(img);
        grid.appendChild(tile);
      });
      canvasWrap.appendChild(grid);
    }

    trigger.addEventListener('click', function (e) { e.preventDefault(); openWall(); });
    trigger.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openWall(); } });
    closeBtn.addEventListener('click', closeWall);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeWall(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && isOpen) closeWall(); });
  })();
})();