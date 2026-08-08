/* Shared header / footer / mobile menu for Asa-OZ.
 * Load this on every page after the opening <div class="shell"> and before
 * closing </body>. It injects the header into [data-header], the footer into
 * [data-footer], and the mobile menu into [data-mobile-menu], then wires up
 * menu toggling and the footer year.
 */
(function () {
  'use strict';

  var SOCIAL_ICONS = [
    { label: 'Instagram', href: 'https://instagram.com/asa-oz', svg: '<rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>' },
    { label: 'Facebook', href: 'https://facebook.com/asa-oz', svg: '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>' },
    { label: 'X', href: 'https://x.com/asa-oz', svg: '<path d="M4 4l11.733 16h4.267l-11.733 -16z"/><path d="M4 20l11.733 -16h4.267l-11.733 16z"/>' },
    { label: 'TikTok', href: 'https://tiktok.com/@asa-oz', svg: '<path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5"/>' },
    { label: 'YouTube', href: 'https://youtube.com/@asa-oz', svg: '<path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19.1c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.43z"/><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02"/>' },
    { label: 'LinkedIn', href: 'https://linkedin.com/company/asa-oz', svg: '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/>' }
  ];

  function iconSvg(label, size) {
    var s = SOCIAL_ICONS.filter(function (i) { return i.label === label; })[0];
    if (!s) return '';
    return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + s.svg + '</svg>';
  }

  function socialLinks(size) {
    return SOCIAL_ICONS.map(function (s) {
      return '<a href="' + s.href + '" target="_blank" rel="noopener" aria-label="' + s.label + '">' + iconSvg(s.label, size) + '</a>';
    }).join('');
  }

  var NAV = [
    { href: '/index.html', label: 'Home' },
    { href: '/about.html', label: 'About' },
    { href: '/store.html', label: 'Store' },
    { href: '/faq.html', label: 'FAQ' },
    { href: '/contact.html', label: 'Contact' }
  ];

  // Determine the current page from the URL (works on localhost and subpaths).
  function currentPage() {
    var path = window.location.pathname;
    var name = path.split('/').pop() || 'index.html';
    if (!name) name = 'index.html';
    if (name === '' || name === 'index.html') return '/index.html';
    return '/' + name;
  }

  function navLinks(menuClass) {
    var current = currentPage();
    return NAV.map(function (n) {
      var cls = (n.href === current) ? ' class="active"' : '';
      return '<a href="' + n.href + '"' + cls + '>' + n.label + '</a>';
    }).join('');
  }

  var headerHTML =
    '<header>' +
      '<div class="brand">' +
        '<a href="/index.html" class="brand-link">' +
          '<span class="brand-logo-fallback">Asa-OZ</span>' +
          '<img class="brand-logo-img" src="/images/logo.svg" alt="Asa-OZ" onload="var f=this.previousElementSibling; if(f&&f.classList.contains(\'brand-logo-fallback\'))f.style.display=\'none\';" onerror="this.style.display=\'none\'">' +
        '</a>' +
      '</div>' +
      '<nav class="main-nav" aria-label="Main">' + navLinks('main-nav') + '</nav>' +
      '<div class="header-social" aria-label="Social media">' + socialLinks(16) + '</div>' +
      '<div class="header-actions">' +
        '<button type="button" class="header-booking" id="headerBookingTrigger">' +
          '<span class="header-booking-text">Book a discovery call</span>' +
          '<svg class="header-booking-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>' +
          '</svg>' +
        '</button>' +
        '<button class="menu-toggle" id="menuToggle" aria-label="Open menu" aria-expanded="false">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>' +
          '</svg>' +
        '</button>' +
        '<button class="cart-toggle" id="cartToggle" aria-label="Open cart">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>' +
          '</svg>' +
          '<span class="cart-count" id="cartCount">0</span>' +
        '</button>' +
      '</div>' +
    '</header>';

  var mobileMenuHTML =
    '<div class="mobile-menu" id="mobileMenu" aria-hidden="true">' +
      '<div class="mobile-menu-inner">' +
        '<div class="mobile-menu-header">' +
          '<a href="/index.html" class="brand-link">' +
            '<span class="brand-logo-fallback">Asa-OZ</span>' +
            '<img class="brand-logo-img" src="/images/logo.svg" alt="Asa-OZ" onload="var f=this.previousElementSibling; if(f&&f.classList.contains(\'brand-logo-fallback\'))f.style.display=\'none\';" onerror="this.style.display=\'none\'">' +
          '</a>' +
          '<button class="mobile-menu-close" id="menuClose" aria-label="Close menu">' +
            '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
              '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>' +
            '</svg>' +
          '</button>' +
        '</div>' +
        '<nav class="mobile-menu-nav" aria-label="Mobile">' + navLinks('mobile-menu-nav') + '</nav>' +
        '<div class="mobile-menu-social">' + socialLinks(20) + '</div>' +
      '</div>' +
    '</div>';

  var footerHTML =
    '<footer>' +
      '<div class="footer-grid">' +
        '<div class="footer-brand">' +
          '<b>Asa-OZ</b>' +
          '<p class="footer-tagline">A movement for identity, belonging &amp; renewal.</p>' +
          '<div class="social-icons" aria-label="Social media">' + socialLinks(18) + '</div>' +
        '</div>' +
        '<div class="footer-contact">' +
          '<h4>Contact</h4>' +
          '<p>Sole Trader: Ifeoma t/a Asa-OZ &middot; Ireland</p>' +
          '<p>RC No: Not applicable (sole trader)</p>' +
          '<p><a href="mailto:info@asa-oz.com">info@asa-oz.com</a></p>' +
          '<p>Phone: [to be added]</p>' +
        '</div>' +
        '<div class="footer-proof">' +
          '<h4>Explore</h4>' +
          '<a href="/about.html">About</a>' +
          '<a href="/faq.html">FAQ</a>' +
          '<a href="/contact.html">Contact</a>' +
          '<a href="/terms.html">Terms</a>' +
          '<a href="/privacy.html">Privacy</a>' +
        '</div>' +
        '<div class="footer-proof">' +
          '<h4>Community</h4>' +
          '<a href="/index.html#signup">Join the waitlist</a>' +
          '<a href="/index.html#testimonials">Read testimonials</a>' +
          '<a href="/about.html">Community stories</a>' +
        '</div>' +
      '</div>' +
      '<div class="footer-legal">' +
        '<p class="copy">&copy; <span id="year"></span> Asa-OZ. All rights reserved.</p>' +
      '</div>' +
    '</footer>';

  function inject(target, html) {
    if (!target) return;
    target.outerHTML = html;
  }

  inject(document.querySelector('[data-header]'), headerHTML);
  inject(document.querySelector('[data-mobile-menu]'), mobileMenuHTML);
  inject(document.querySelector('[data-footer]'), footerHTML);

  var yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Mobile menu wiring (shared behavior for all pages).
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
      if (menu.classList.contains('is-open')) { closeMenu(); } else { openMenu(); }
    });
    close.addEventListener('click', closeMenu);
    menu.addEventListener('click', function (e) {
      if (e.target === menu) closeMenu();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.classList.contains('is-open')) { closeMenu(); toggle.focus(); }
    });
    menu.querySelectorAll('.mobile-menu-nav a').forEach(function (link) {
      link.addEventListener('click', closeMenu);
    });
  })();
})();
